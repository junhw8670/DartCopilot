import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_servers.dart_server import search_company, list_disclosures

samsung = search_company("삼성전자")
print(samsung)

# search_company 결과의 corp_code를 그대로 list_disclosures에 넘김
disclosures = list_disclosures(
    corp_code=samsung["corp_code"],
    bgn_de="20240101",
    end_de="20241231",
    pblntf_ty="A",   # 정기공시만 (사업·반기·분기보고서)
)
print(f"총 {disclosures['total_count']}건")
for d in disclosures["list"][:10]:
    amend = " [정정]" if d["is_amendment"] else ""
    print(f"  {d['rcept_dt']} | {d['report_nm']}{amend} (rcept_no={d['rcept_no']})")