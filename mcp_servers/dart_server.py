from mcp.server.fastmcp import FastMCP
import requests
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional
import os
from dotenv import load_dotenv
import re
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher

load_dotenv()

mcp = FastMCP("DartOpenAPI")

API_KEY = os.getenv("OPENDART_API_KEY")
BASE_URL = "https://opendart.fss.or.kr/api"
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"

_companies: list[dict] | None = None

_NORMALIZE_RE = re.compile(r"\s+|주식회사|\(주\)|㈜")

def _normalize(name:str) -> str:
    """Strip whitespace and corporate suffix variations for tolerant matching."""
    return _NORMALIZE_RE.sub("", name)

def _download_corpcode_zip(dst: Path) -> None:
    """Download OpenDART's corp_code master list and extract CORPCODE.xml to disk."""
    url = f"{BASE_URL}/corpCode.xml"
    params = {"crtfc_key": API_KEY}

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()

    if r.content[:2] != b"PK":
        raise RuntimeError(
            f"OpenDART corpCode.xml 응답이 ZIP이 아님: "
            f"{r.content[:200]!r}"
        )
    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(BytesIO(r.content)) as zf:
        zf.extract("CORPCODE.xml", dst.parent)

def _parse_corpcode_xml(path: Path) -> list[dict]:
    """Parse CORPCODE.xml into a list of dicts for listed companies."""
    tree = ET.parse(path)
    root = tree.getroot()

    companies: list[dict] = []
    for item in root.findall("list"):
        stock_code = (item.findtext("stock_code") or "").strip()

        if not stock_code:
            continue

        companies.append({
            "corp_code": (item.findtext("corp_code") or "").strip(),
            "corp_name": (item.findtext("corp_name") or "").strip(),
            "stock_code": stock_code,
        })
    return companies

def _load_companies() -> list[dict]:
    """Lazy-load the corp code master list (download + parse on first call)."""
    global _companies
    if _companies is None:
        cache_path = CACHE_DIR / "CORPCODE.xml"
        if not cache_path.exists():
            _download_corpcode_zip(cache_path)
        _companies = _parse_corpcode_xml(cache_path)
    return _companies


@mcp.tool()
def search_company(name: str) -> dict:
    """Resolve a Korean company name to its DART corp_code, stock code, and canonical name.
    
    This is the FIRST tool every company-analysis agent should call. Internally caches
    corpCode.xml (the master list of all listed Korean companies) and performs
    partial-match search by company name.

    Args:
        name: Company name to search. Korean names accepted(e.g. "삼성전자", "현대자동차", "카카오").
              Partial matches supported. Whitespace and corporate suffix variations((주), 주식회사) are tolerated.

    Returns:
        {
            "corp_code": "00126380",
            "stock_code": "005930",
            "corp_name": "삼성전자",
            "match_score": 1.0
        }

        On failure: {"error": "No matching company found for <name>."}
    """
    query = _normalize(name)
    if not query:
        return {"error": "Empty company name."}
    companies = _load_companies()

    candidates: list[tuple[float, dict]] = []

    for c in companies:
        target = _normalize(c["corp_name"])
        if not target:
            continue
        if target == query:
            score = 1.0
        elif query in target or target in query:
            score = 0.6 + 0.4 * min(len(query), len(target)) / max(len(query), len(target))
        else:
            ratio = SequenceMatcher(None, query, target).ratio()
            if ratio < 0.6:
                continue
            score = ratio
        candidates.append((score, c))

    if not candidates:
        return {"error": f"No matching company found for {name}."}
    
    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best = candidates[0]

    return {
        "corp_code": best["corp_code"],
        "stock_code": best["stock_code"],
        "corp_name": best["corp_name"],
        "match_score": round(best_score, 4),
    }


@mcp.tool()
def list_disclosures(
    corp_code: str,
    bgn_de: str,
    end_de: str,
    pblntf_ty: str = "A",
) -> dict:
    """List disclosures filed by a specific company within a date range.

    Wraps OpenDART /api/list.json endpoint.

    Args:
        corp_code: 8-digit DART corp_code (obtain via search_company first)
        bgn_de: Start date YYYYMMDD (e.g. "20230101")
        end_de: End date YYYYMMDD (e.g. "20231231")
        pblntf_ty: Disclosure type. 'A'=periodic (사업보고서, 반기보고서, 분기보고서),
        'B'=major matters, 'C'=issuance, 'D'=equity, 'E'=other. Default 'A'.

    Returns:
        {
            "status": "000",
            "total_count": 4,
            "list": [
                {
                    "rcept_no": "20240312000736",
                    "rcept_dt": "20240312",
                    "report_nm": "사업보고서 (2023.12)"
                    "corp_name": "삼성전자",
                    "is_amendment": false
                },
                ...
            ]
        }
    """
    url = f"{BASE_URL}/list.json"
    params = {
        "crtfc_key": API_KEY,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "pblntf_ty": pblntf_ty,
        "page_count": "100",
    }
    
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    status = data.get("status")
    if status == "013":
        return {"status": "013", "total_count": 0, "list": []}
    if status != "000":
        return {
            "error": f"OpenDART status={status}, message={data.get('message')}"
        }
    
    items = []
    for raw in data.get("list", []):
        report_nm = (raw.get("report_nm") or "").strip()
        is_amendment = (
            report_nm.startswith("[") and "정정" in report_nm.split("]")[0]
        )

        items.append({
            "rcept_no": raw.get("rcept_no"),
            "rcept_dt": raw.get("rcept_dt"),
            "report_nm": report_nm,
            "corp_name": raw.get("corp_name"),
            "is_amendment": is_amendment,
        })
    
    return {
        "status": status,
        "total_count": data.get("total_count", len(items)),
        "list": items,
    }


@mcp.tool()
def fetch_report(rcept_no: str) -> dict:
    """Download a disclosure's original document ZIP and extract its XML files.
    
    Wraps OpenDART /api/document.xml endpoint. Korean business reports are delivered as XML(dart4.xsd schema), NOT PDF.
    The ZIP contains a main XML plus optional attachment XMLs.

    Files are cached at cache/{corp_code}/{rcept_no}/ for instant re-access.

    Args:
        rcept_no: 14-digit DART receipt number (e.g. "20240312000736").
        Obtain via list_disclosures first.

    Returns:
        {
            "rcept_no": "20240312000736",
            "xml_paths": [
                "/.../20240312000736.xml",
                "/.../20240312000736_00760.xml",
                "/.../20240312000736_00761.xml"
                ],
                "main_xml": "/.../20240312000736.xml",
                "size_bytes": 6150873
        }
    """

@mcp.tool()
def parse_business_report_xml(xml_path: str, sections: Optional[list[str]] = None)  -> dict:
    """Parse a DART business report XML into a section-wise dict using BeautifulSoup.

    Handles dart4.xsd-schema XML, extracting section text and structured table data
    (rows where <TU AUNIT=... AUNITVALUE=...> attributes carry the canonical values).

    Args:
        xml_path: Absolute path to main_xml returned by fetch_report.
        sections: Section names to extract. If None, extracts all. 
        Examples: ["회사의 개요", "사업의 내용", "재무에 관한 사항", "임원 및 직원에 관한 사항"]

    Returns:
        {
            "company_name": "삼성전자주식회사",
            "report_name": "사업보고서",
            "period_from": "20230101",
            "period_to": "20231231",
            "sections": {
                "회사의 개요": "...text body...",
                "사업의 내용": "...text body...",
                ...
            },
            "tables": [
                {"section": "재무에 관한 사항",
                 "rows": [["항목", "당기", "전기"], ["매출액","302231360", "279060475"], ...]}
            ]
        }
    """

@mcp.tool()
def fetch_financial(corp_code: str, year: int, report_code: str = "11011") -> dict:
    """Fetch a single company's full-account financial statements from OpenDART JSON API.

    Wraps OpenDART /api/fnlttSinglAcntAll.json endpoint.

    Args:
        corp_code: 8-digit DART corp_code.
        year: Fiscal year(e.g. 2023).
        report_code: '11011'=annual business report, '11012'=half-year, '11013'=Q1, '11014'=Q3. Default '11011'.

    Returns:
        {
            "corp_code": "00126380",
            "year": 2023,
            "fs_type": "CFS",
            "accounts": [
                {"account_nm": "매출액", "thstrm_amount": "302231360000000",
                 "frmtrm_amount": "279060475000000", "bfefrmtrm_amount": "..."},
                {"account_nm": "영업이익", ...},
                ...
            ]
        }

        Use these accounts to compute ratios:
        - 부채비율 = 부채총계 / 자기자본총계
        - ROE = 당기순이익 / 자기자본총계
        - 영업이익률 = 영업이익 / 매출액
    """

@mcp.tool()
def fetch_peers(corp_code: str, top_k: int = 10) -> dict:
    """Return listed companies sharing the same industry code as the target.

    Retrieves the target's industry code via /api/company.json, 
    then filters the corpCode.xml cache for other listed companies with the same code.

    Args:
        corp_code: Reference company's 8-digit DART corp_code.
        top_k: Max number of peers to return. Default 10.
    
    Returns:
        {
            "base_corp_code": "00126380",
            "base_corp_name": "삼성전자",
            "industry_code": "26",
            "industry_name": "전자제품 제조업",
            "total_peers_in_industry": 2,
            "peers": [
                {"corp_code": "00164779", "corp_name": "SK하이닉스", "stock_code": "000660"},
                ...
            ]
        }
    """

@mcp.tool()
def fetch_multi_company(corp_codes: list[str], year: int, report_code: str = "11011") -> dict:
    """Fetch key accounts (revenue, operating profit, net income, assets, equity)
    for multiple companies in a single call.

    Wraps OpenDART /api/fnlttMultiAcnt.json endpoint, which is optimized for cross-company comparison.
    This is dramatically more efficient than calling fetch_report N times.

    Args:
        corp_codes: List of corp_codes (up to 10 recommended)
        year: Fiscal year
        report_code: Report code. Default '11011' (annual).

    Returns:
        {
            "year": 2024,
            "companies": [
                {
                    "corp_code": "00126380",
                    "corp_name": "삼성전자",
                    "매출액": 302231360000000,
                    "영업이익": 6566976000000,
                    "당기순이익": ...,
                    ...
                },
                ...
            ]
        }
    """

@mcp.tool()
def fetch_multi_years(corp_code: str, start_year: int, end_year: int) -> dict:
    """Fetch a single company's financial statements across multiple years.

    Internally calls fnlttSinglAcntAll.json for each year in [start_year, end_year] and aggregates results.
    Cached calls return instantly.

    Args:
        corp_code: Company's corp_code.
        start_year: First year(inclusive)
        end_year: Last year(inclusive)

    Returns:
        {
            "corp_code": "00126380",
            "years": [2020, 2021, 2022, 2023, 2024],
            "by_year": {
                2020: {"매출액": ..., "영업이익": ..., ...},
                2021: {...},
                ...
            },
            "growth_rates": {
                "매출액": [None, 18.1, 8.1, -14.6, 16.1],
                ...
            }
        }

        Use this for trend, volatility, CAGR analysis.
    """

@mcp.tool()
def fetch_amendments(corp_code: str, year: int) -> dict:
    """Fetch a company's amendment disclosures (정정공시) for a given year.

    Filters disclosures from list_disclosures where is_amendment=true.
    For each amendment, includes a pointer to the original disclosure it amends.

    Args:
        corp_code: Company's corp_code.
        year: Fiscal year.

    Returns:
        {
            "corp_code": "00126380",
            "amendments": [
                {
                    "rcept_no": "20240312000736",
                    "rcept_dt": "20240312",
                    "report_nm": "[기재정정]사업보고서(2023.12)",
                    "original_rcept_no": "20240215000001",
                    "amendment_reason": "..."
                }
            ]
        }
    """

@mcp.tool()
def diff_documents(rcept_no_old: str, rcept_no_new: str) -> dict:
    """Compare two disclosures (original vs amended) and extract changed sections/paragraphs.

    Internally fetches both via fetch_report, parses with parse_business_report_xml, then runs difflib.unified_diff per section.
    Args:
        rcept_no_old: Original report receipt number.
        rcept_no_new: Amended report receipt number.

    Returns:
        {
            "old_rcept_no": "20240312000736",
            "new_rcept_no": "20240520001234",
            "changed_sections": [
                {
                    "section": "재무에 관한 사항",
                    "diff_text": "- 매출액 302조원 \n+ 매출액 301조원\n...",
                    "change_summary": "매출액 1조원 하향 수정"
                }
            ]
        }
    """

if __name__ == "__main__":
    mcp.run(transport="stdio")