from dotenv import load_dotenv; load_dotenv()
from mcp_servers.dart_server import search_company, list_disclosures, fetch_report, _read_xml, parse_business_report_xml
cc = search_company("현대자동차")["corp_code"]
dl = list_disclosures(cc, "20250101", "20251231", "A")
rno = next(d["rcept_no"] for d in dl["list"] if "사업보고서" in d["report_nm"] and not d["is_amendment"])
rep = fetch_report(rno)
raw = _read_xml(rep["main_xml"])
print("원문 raw 길이:", len(raw), "자")
p = parse_business_report_xml(rep["main_xml"])
print("섹션수:", len(p["sections"]), "| 섹션 본문 총길이:", sum(len(v) for v in p["sections"].values()))
print("표 개수:", len(p["tables"]), "| 표 총 행수:", sum(len(t["rows"]) for t in p["tables"]))