import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_servers.dart_server import (
    search_company, list_disclosures, fetch_report, parse_business_report_xml
)

# 캐시에 이미 있는 삼성전자 2023 사업보고서 사용
samsung = search_company("삼성전자")
disclosures = list_disclosures(samsung["corp_code"], "20240101", "20241231")
# 정기공시 중 사업보고서 찾기
rcept_no = next(d["rcept_no"] for d in disclosures["list"] if "사업보고서" in d["report_nm"])
report = fetch_report(rcept_no)

# "회사의 개요"만 추출해서 본문 앞부분 + 표 개수 확인
parsed = parse_business_report_xml(
    xml_path=report["main_xml"],
    sections=["회사의 개요"],
)
print(f"회사: {parsed['company_name']}")
print(f"보고서: {parsed['report_name']}")
print(f"기간: {parsed['period_from']} ~ {parsed['period_to']}")
print()
for name, text in parsed["sections"].items():
    print(f"=== {name} ===")
    print(text[:500], "...")
    print()
print(f"표 총 {len(parsed['tables'])}개")
if parsed["tables"]:
    print("첫 표의 첫 3행:")
    for row in parsed["tables"][0]["rows"][:3]:
        print("  |", " | ".join(row))