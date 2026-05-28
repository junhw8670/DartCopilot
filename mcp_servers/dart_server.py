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
import json
from bs4 import BeautifulSoup
import difflib

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

def _parse_amount(s: str | None) -> int | None:
    """Convert an OpenDART amount string (e.g. "302,231,000,000") to int."""
    if not s:
        return None
    s = s.replace(",", "").strip()
    if not s or s == "-":
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _extract_rows(table_elem) -> list[list[str]]:
    """Extract rows from a <TABLE> as [[cell_text, ...], ...]."""
    rows: list[list[str]] = []
    for section in table_elem.find_all(["THEAD", "TBODY"], recursive=False):
        for tr in section.find_all("TR", recursive=False):
            cells = [
                cell.get_text(separator=" ", strip=True)
                for cell in tr.find_all(["TD", "TH", "TU", "TE"], recursive=False)
            ]
            if any(c for c in cells):
                rows.append(cells)
    return rows


def _read_xml(xml_path: str) -> str:
    """Read DART XML with utf-8 -> cp 949 fallback."""
    try:
        with open(xml_path, encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(xml_path, encoding="cp949") as f:
            return f.read()


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
def list_disclosures(corp_code: str, bgn_de: str, end_de: str, pblntf_ty: str = "A") -> dict:
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

    Files are cached at cache/{rcept_no}/ for instant re-access.

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
    cache_dir = CACHE_DIR / rcept_no

    if not (cache_dir.exists() and any(cache_dir.glob("*.xml"))):
        r = requests.get(
            f"{BASE_URL}/document.xml",
            params={"crtfc_key": API_KEY, "rcept_no": rcept_no},
            timeout=120
        )
        r.raise_for_status()
        if r.content[:2] != b"PK":
            try:
                data = r.json()
                return {"error": f"OpenDART status={data.get('status')}, message={data.get('message')}"}
            except Exception:
                return {"error": f"Invalid response: {r.content[:200]!r}"}
        
        cache_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(BytesIO(r.content)) as zf:
            zf.extractall(cache_dir)

    xml_paths = sorted(str(p) for p in cache_dir.glob("*.xml"))

    return {
        "rcept_no": rcept_no,
        "xml_paths": xml_paths,
        "main_xml": xml_paths[0] if xml_paths else "",
        "size_bytes": sum(Path(p).stat().st_size for p in xml_paths),
    }


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
    raw = _read_xml(xml_path)
    
    head = BeautifulSoup(raw[:10000], "lxml-xml")
    company_tag = head.find("COMPANY-NAME")
    document_tag = head.find("DOCUMENT-NAME")
    pf_tag = head.find("TU", {"AUNIT": "PERIODFROM"})
    pt_tag = head.find("TU", {"AUNIT": "PERIODTO"})

    title_pat = re.compile(r'<TITLE\b[^>]*>\s*([IVX]+\.\s+[^<]+?)\s*</TITLE>')
    matches = list(title_pat.finditer(raw))

    all_sections: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        clean_name = re.sub(r'^[IVX]+\.\s+', '', m.group(1).strip())
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        all_sections.append((clean_name, raw[start:end]))

    if sections is not None:
        all_sections = [
            (name, body) for name, body in all_sections
            if any(req in name for req in sections)
        ]

    result_sections: dict[str, str] = {}
    result_tables: list[dict] = []

    for name, body in all_sections:
        soup = BeautifulSoup(f"<root>{body}</root>", "lxml-xml")

        paragraphs = [
            p.get_text(strip=True)
            for p in soup.find_all("P")
            if not p.find_parent("TABLE") and p.get_text(strip=True)
        ]
        result_sections[name] = " ".join(paragraphs)

        for table in soup.find_all("TABLE"):
            rows = _extract_rows(table)
            if rows:
                result_tables.append({"section": name, "rows": rows})

    return {
        "company_name": company_tag.get_text(strip=True) if company_tag else "",
        "report_name": document_tag.get_text(strip=True) if document_tag else "",
        "period_from": pf_tag.get("AUNITVALUE", "") if pf_tag else "",
        "period_to": pt_tag.get("AUNITVALUE", "") if pt_tag else "",
        "sections": result_sections,
        "tables": result_tables,
    }


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
                {"sj_nm": "재무상태표", "account_nm": "매출액", "thstrm_amount": "302231360000000",
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
    url = (f"{BASE_URL}/fnlttSinglAcntAll.json")
    params ={
        "crtfc_key": API_KEY,
        "corp_code": corp_code,
        "bsns_year": str(year),
        "reprt_code": report_code,
        "fs_div": "CFS",
    }

    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    if data.get("status") == "013":
        params["fs_div"] = "OFS"
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    
    status = data.get("status")
    if status != "000":
        return {
            "error": f"OpenDART status={status}, message={data.get('message')}",
            "corp_code": corp_code,
            "year": year,
        }
    
    fs_type = params["fs_div"]
    
    accounts = []
    for raw in data.get("list", []):
        accounts.append({
            "sj_nm": raw.get("sj_nm"),
            "account_nm": raw.get("account_nm"),
            "thstrm_amount": _parse_amount(raw.get("thstrm_amount")),
            "frmtrm_amount": _parse_amount(raw.get("frmtrm_amount")),
            "bfefrmtrm_amount": _parse_amount(raw.get("bfefrmtrm_amount")),
        })

    return {
        "corp_code": corp_code,
        "year": year,
        "fs_type": fs_type,
        "accounts": accounts,
    }


@mcp.tool()
def fetch_peers(corp_code: str, top_k: int = 10, industry_override: Optional[str] = None) -> dict:
    """Return listed companies sharing the same KRX industry as the target.

    Looks up the target's KRX industry classification from a precomputed cache
    (cache/industry_codes.json), then filters for other listed companies with
    the same industry name. The cache is built by scripts/build_industry_cache.py
    using FinanceDataReader (KRX descriptive listing). 
    If industry_override is provided, search the industry which best matches the industry_override, and then return companies in *that* industry.

    Args:
        corp_code: Reference company's 8-digit DART corp_code.
        top_k: Max number of peers to return. Default 10.

    Returns:
        {
            "base_corp_code": "00126380",
            "base_corp_name": "삼성전자",
            "industry_name": "반도체와관련장비",
            "market": "KOSPI",
            "total_peers_in_industry": 12,
            "peers": [
                {
                    "corp_code": "00164779",
                    "corp_name": "SK하이닉스",
                    "stock_code": "000660",
                    "market": "KOSPI"
                },
                ...
            ]
        }

        On failure: {"error": "..."} (missing cache, unlisted company, or no industry data).
    """
    cache_path = CACHE_DIR /"industry_codes.json"
    if not cache_path.exists():
        return {"error": "industry_codes.json cache missing."}

    industry_map: dict[str, dict] = json.loads(
        cache_path.read_text(encoding="utf-8")
    )
    
    target = industry_map.get(corp_code)
    if target is None:
        return {"error": f"{corp_code} missing in industry cache." }

    target_industry = industry_override or target.get("industry")
    if not target_industry:
        return {"error": f"{target.get('corp_name')} missing an industry info."}

    peers: list[dict] = []
    for cc, info in industry_map.items():
        if cc == corp_code:
            continue
        if info.get("industry") == target_industry:
            peers.append({
                "corp_code": cc,
                "corp_name": info.get("corp_name"),
                "stock_code": info.get("stock_code"),
                "market": info.get("market"),
            })
    return {
        "base_corp_code": corp_code,
        "base_corp_name": target.get("corp_name"),
        "industry_name": target_industry,
        "market": target.get("market"),
        "total_peers_in_industry": len(peers),
        "peers": peers[:top_k],
    }


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
    BATCH_SIZE = 10
    url = f"{BASE_URL}/fnlttMultiAcnt.json"

    all_rows: list[dict] = []

    for i in range(0, len(corp_codes), BATCH_SIZE):
        batch = corp_codes[i : i + BATCH_SIZE]

        params = {
            "crtfc_key": API_KEY,
            "corp_code": ",".join(batch),
            "bsns_year": str(year),
            "reprt_code": report_code,
        }

        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        status = data.get("status")
        if status == "013":
            continue
        if status != "000":
            return {
                "error": f"OpenDART status={status}, message={data.get('message')}",
                "year": year,
            }
        all_rows.extend(data.get("list", []))

    by_corp: dict[str, dict] = {}
    for raw in all_rows:
        cc = raw.get("corp_code")
        if cc is None:
            continue
        if cc not in by_corp:
            by_corp[cc] = {
                "corp_code": cc,
                "corp_name": raw.get("corp_name"),
                "stock_code": raw.get("stock_code"),
            }
        account_nm = raw.get("account_nm")
        if account_nm:
            by_corp[cc][account_nm] = _parse_amount(raw.get("thstrm_amount"))

    return {
        "year": year,
        "report_code": report_code,
        "companies": list(by_corp.values())
    }    
    


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
    if start_year > end_year:
        return {"error": f"start_year({start_year}) > end_year({end_year})"}

    years = list(range(start_year, end_year + 1))

    KEY_ACCOUNTS = {
        "매출액", "수익(매출액)", "영업수익", "수익", "영업이익", "당기순이익", "법인세차감전순이익", "자산총계", "부채총계", "자본총계",
    }
    
    by_year: dict[int, dict[str, int | None]] = {}
    for year in years:
        fin = fetch_financial(corp_code=corp_code, year=year, report_code="11011")
        if "error" in fin:
            by_year[year] = {}
            continue
        
        year_data: dict[str, int | None] = {}
        for a in fin.get("accounts", []):
            nm = a.get("account_nm")
            if nm in KEY_ACCOUNTS:
                year_data[nm] = a.get("thstrm_amount")
        by_year[year] = year_data

    all_accounts: set[str] = set()
    for year_data in by_year.values():
        all_accounts.update(year_data.keys())

    growth_rates: dict[str, list[float | None]] = {}
    for acc in all_accounts:
        rates: list[float | None] = []
        prev: int | None = None
        for year in years:
            current = by_year.get(year, {}).get(acc)
            if current is None or prev is None or prev == 0:
                rates.append(None)
            else:
                pct = (current - prev) / abs(prev) * 100
                rates.append(round(pct, 2))
            prev = current
        growth_rates[acc] = rates

    return {
        "corp_code": corp_code,
        "years": years,
        "by_year": by_year,
        "growth_rates": growth_rates,
    }


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
    disclosures = list_disclosures(
        corp_code=corp_code,
        bgn_de=f"{year -1}0101",
        end_de=f"{year}1231",
        pblntf_ty="A",
    )
    if "error" in disclosures:
        return disclosures

    items = disclosures.get("list", [])
    
    prefix_pat = re.compile(r'^\[[^\]]+\]\s*')

    amendments = []
    for amend in items:
        if not amend.get("is_amendment"):
            continue
        if str(amend.get("rcept_dt", ""))[:4] != str(year):
            continue
        
        amend_name = prefix_pat.sub('', amend.get("report_nm", "")).strip()

        original_rcept_no = None
        for d in items:
            if d.get("is_amendment"):
                continue
            if (d.get("report_nm", "").strip() == amend_name and d.get("rcept_dt", "") <= amend.get("rcept_dt", "")):
                original_rcept_no = d.get("rcept_no")
                break

        amendments.append({
            "rcept_no": amend.get("rcept_no"),
            "rcept_dt": amend.get("rcept_dt"),
            "report_nm": amend.get("report_nm"),
            "original_rcept_no": original_rcept_no,
            "amendment_reason": None,
        })
    
    return {
        "corp_code": corp_code,
        "year":year,
        "amendments": amendments,
    }



@mcp.tool()
def fetch_amendment_details(rcept_no: str) -> dict:
    """Extract before/after comparison tables from an amendment disclosure.
       
    Args:
        rcept_no: Amendment disclosure's 14-digit receipt number.

    Returns:
        {
            "rcept_no": "20240520001234",
            "comparison_tables": [
                {"rows": [["항목", "정정전", "정정후"], [...], ...]},
                ...
            ]
        }
    """
    report = fetch_report(rcept_no)
    if "error" in report:
        return {"error": f"report fetch failed: {report['error']}"}

    raw = _read_xml(report["main_xml"])

    head = raw[:300000]
    soup = BeautifulSoup(head, "lxml-xml")

    comparison_tables = []
    for table in soup.find_all("TABLE"):
        rows = _extract_rows(table)
        if not rows:
            continue
        flat = "".join(c for row in rows for c in row).replace(" ", "")
        if "정정전" in flat and "정정후" in flat:
            comparison_tables.append({"rows": rows})

    return {
        "rcept_no": rcept_no,
        "comparison_tables": comparison_tables,
    }

if __name__ == "__main__":
    mcp.run(transport="stdio")