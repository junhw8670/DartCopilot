import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\DartCopilot\mcp_servers")

from dart_server import (
    search_company,
    list_disclosures,
    fetch_report,
    parse_business_report_xml,
    fetch_financial,
    fetch_peers,
    fetch_multi_company,
    fetch_multi_years,
    fetch_amendments,
    fetch_amendment_details,
)


OUTPUT_DIR = Path("results/dart_tool_validation")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


COMPANIES = [
    {
        "name": "삼성전자",
        "corp_code": "00126380",
    },
    {
        "name": "현대자동차",
        "corp_code": "00164742",
    },
    {
        "name": "NAVER",
        "corp_code": "00266961",
    },
]


def run_tool(tool_name, function, arguments):
    try:
        result = function(**arguments)

        return {
            "input": arguments,
            "result": result,
        }

    except Exception as error:
        return {
            "input": arguments,
            "error": str(error),
        }


def save_result(tool_name, results):
    output_path = OUTPUT_DIR / f"{tool_name}.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            results,
            file,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    print(f"저장 완료: {output_path}")


# 1. search_company

search_results = []

for company in COMPANIES:
    search_results.append(
        run_tool(
            "search_company",
            search_company,
            {"name": company["name"]},
        )
    )

save_result("search_company", search_results)


# 2. list_disclosures

disclosure_results = []

for company in COMPANIES:
    disclosure_results.append(
        run_tool(
            "list_disclosures",
            list_disclosures,
            {
                "corp_code": company["corp_code"],
                "bgn_de": "20250101",
                "end_de": "20250430",
                "pblntf_ty": "A",
            },
        )
    )

save_result("list_disclosures", disclosure_results)



report_receipts = []

for item in disclosure_results:
    result = item.get("result", {})
    disclosures = result.get("list", [])

    business_report = next(
        (
            disclosure
            for disclosure in disclosures
            if "사업보고서" in disclosure.get("report_nm", "")
        ),
        None,
    )

    report_receipts.append(
        business_report.get("rcept_no")
        if business_report else None
    )


# 3. fetch_report

report_results = []

for company, rcept_no in zip(COMPANIES, report_receipts):
    if rcept_no:
        report_results.append(
            run_tool(
                "fetch_report",
                fetch_report,
                {"rcept_no": rcept_no},
            )
        )
    else:
        report_results.append({
            "input": {"company": company["name"]},
            "error": "사업보고서 접수번호를 찾지 못했습니다.",
        })

save_result("fetch_report", report_results)


# 4. parse_business_report_xml

parse_results = []

for company, report_item in zip(COMPANIES, report_results):
    report_result = report_item.get("result", {})
    xml_path = report_result.get("main_xml")

    if xml_path:
        parse_results.append(
            run_tool(
                "parse_business_report_xml",
                parse_business_report_xml,
                {
                    "xml_path": xml_path,
                    "sections": ["재무에 관한 사항"],
                },
            )
        )
    else:
        parse_results.append({
            "input": {"company": company["name"]},
            "error": "사업보고서 XML 경로가 없습니다.",
        })

save_result("parse_business_report_xml", parse_results)


# 5. fetch_financial

financial_results = []

for company in COMPANIES:
    financial_results.append(
        run_tool(
            "fetch_financial",
            fetch_financial,
            {
                "corp_code": company["corp_code"],
                "year": 2024,
                "report_code": "11011",
            },
        )
    )

save_result("fetch_financial", financial_results)


# 6. fetch_peers

peer_results = []

for company in COMPANIES:
    peer_results.append(
        run_tool(
            "fetch_peers",
            fetch_peers,
            {
                "corp_code": company["corp_code"],
                "top_k": 5,
            },
        )
    )

save_result("fetch_peers", peer_results)


# 7. fetch_multi_company

multi_company_inputs = [
    {
        "corp_codes": [
            "00126380",
            "00164742",
            "00266961",
        ],
        "year": 2024,
        "report_code": "11011",
    },
    {
        "corp_codes": [
            "00126380",
            "00164742",
        ],
        "year": 2023,
        "report_code": "11011",
    },
    {
        "corp_codes": [
            "00126380",
            "00266961",
        ],
        "year": 2022,
        "report_code": "11011",
    },
]

multi_company_results = [
    run_tool(
        "fetch_multi_company",
        fetch_multi_company,
        arguments,
    )
    for arguments in multi_company_inputs
]

save_result("fetch_multi_company", multi_company_results)


# 8. fetch_multi_years

multi_year_results = []

for company in COMPANIES:
    multi_year_results.append(
        run_tool(
            "fetch_multi_years",
            fetch_multi_years,
            {
                "corp_code": company["corp_code"],
                "start_year": 2022,
                "end_year": 2024,
            },
        )
    )

save_result("fetch_multi_years", multi_year_results)


# 9. fetch_amendments

amendment_results = []

for company in COMPANIES:
    amendment_results.append(
        run_tool(
            "fetch_amendments",
            fetch_amendments,
            {
                "corp_code": company["corp_code"],
                "year": 2024,
                "pblntf_ty": None,
            },
        )
    )

save_result("fetch_amendments", amendment_results)


# 정정공시 접수번호를 회사별로 하나씩 가져온다.

amendment_receipts = []

for item in amendment_results:
    result = item.get("result", {})
    amendments = result.get("amendments", [])

    amendment_receipts.append(
        amendments[0].get("rcept_no")
        if amendments else None
    )


# 10. fetch_amendment_details

amendment_detail_results = []

for company, rcept_no in zip(COMPANIES, amendment_receipts):
    if rcept_no:
        amendment_detail_results.append(
            run_tool(
                "fetch_amendment_details",
                fetch_amendment_details,
                {"rcept_no": rcept_no},
            )
        )
    else:
        amendment_detail_results.append({
            "input": {"company": company["name"]},
            "error": "2024년 정정공시가 없습니다.",
        })

save_result(
    "fetch_amendment_details",
    amendment_detail_results,
)


print()
print("전체 DART 툴 실행 완료")
print(f"결과 폴더: {OUTPUT_DIR.resolve()}")