import requests
from pathlib import Path


def load_env(env_path: Path) -> dict:
    env = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, val = line.partition("=")
        env[key.strip()] = val.strip()
    return env


env = load_env(Path(__file__).parent / ".env")
API_KEY = env.get("OPENDART_API_KEY")
if not API_KEY:
    raise RuntimeError(".env에 OPENDART_API_KEY가 없습니다.")

url = "https://opendart.fss.or.kr/api/list.json"
params = {
    "crtfc_key": API_KEY,
    "corp_code": "00126380",   
    "bgn_de": "20240101",
    "end_de": "20241231",
    "pblntf_ty": "A", 
    "page_count": "10",
}

print("=" * 60)
print("[Day 1] OpenDART API 호출 테스트")
print("=" * 60)
print(f"대상: 삼성전자 / 기간: 2024-01-01 ~ 2024-12-31 / 유형: 정기공시")
print(f"호출 URL: {url}")
print()

try:
    r = requests.get(url, params=params, timeout=10)
except Exception as e:
    print(f"[연결 오류] {e}")
    raise

print(f"HTTP 상태: {r.status_code}")
print(f"응답 크기: {len(r.text):,} 문자")
print("-" * 60)

if r.status_code != 200:
    print(f"[비정상 응답] {r.text[:500]}")
    raise SystemExit(1)

data = r.json()
status = data.get("status")
message = data.get("message")
total = data.get("total_count")

print(f"OpenDART 상태코드: {status}")
print(f"메시지: {message}")
print(f"총 검색건수: {total}")

if status != "000":
    print(f"\n[키 또는 요청 문제] status={status} → 위 메시지 참고")
    raise SystemExit(1)

print()
print("[검색된 공시 목록]")
print("-" * 60)
for i, item in enumerate(data.get("list", []), 1):
    print(f"{i:2}. {item.get('rcept_dt')} | {item.get('report_nm')}")
    print(f"    접수번호: {item.get('rcept_no')} | 공시구분: {item.get('pblntf_detail_ty')}")

print()
print("[응답 첫 항목 전체 구조 — 어떤 필드가 있는지]")
print("-" * 60)
if data.get("list"):
    first = data["list"][0]
    for k, v in first.items():
        print(f"  {k:25} : {v}")