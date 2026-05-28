import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_servers.dart_server import fetch_amendment_details

result = fetch_amendment_details("20170511004410")
print(f"rcept_no: {result['rcept_no']}")
print(f"비교 표 수: {len(result['comparison_tables'])}")

for i, t in enumerate(result["comparison_tables"]):
    print(f"\n========= 표 {i+1} (행 {len(t['rows'])}개) =========")
print('-'*70)
print(t["rows"][1])           # 두 번째 행(첫 데이터 행)의 모든 셀 그대로
print('-'*70)
print(t["rows"][1][1])  