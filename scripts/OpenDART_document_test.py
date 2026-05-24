import zipfile
from io import BytesIO
from pathlib import Path
import requests

def load_env(env_path: Path) -> dict:
    env = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, val = line.partition("=")
        env[key.strip()] = val.strip()
    return env

env = load_env(Path(__file__).parent.parent / ".env")
API_KEY = env.get("OPENDART_API_KEY")
if not API_KEY:
    raise RuntimeError(".env에 OPENDART_API_KEY가 없습니다.")

CORP_CODE = "00126380"
RCEPT_NO = "20240312000736"

cache_dir = Path(__file__).parent.parent / "cache" / CORP_CODE / RCEPT_NO
cache_dir.mkdir(parents=True, exist_ok=True)

url = "https://opendart.fss.or.kr/api/document.xml"
params = {"crtfc_key": API_KEY, "rcept_no": RCEPT_NO}

print("공시 원본문서 다운로드 테스트")
print('-' * 60)

r = requests.get(url, params=params, timeout=120)

print(f"HTTP 상태 코드: {r.status_code}")
print(f"응답 크기: {len(r.content):,} 바이트 ({len(r.content)/1024/1024:.2f} MB)")
print(f"Content-Type: {r.headers.get('Content-Type')}")
print(f"Content-Disposition: {r.headers.get('Content-Disposition')}")
print('-' * 60)

if r.content[:2] != b"PK":
    try:
        data = r.json()
        print(f"  [오류 응답 - JSON]")
        print(f"  status: {data.get('status')}")
        print(f"  message: {data.get('message')}")
    except Exception:
        print(f"[응답 본문 처음 500자]")
        print(r.content[:500])
    raise SystemExit(1)

zip_path = cache_dir.parent / f"{RCEPT_NO}.zip"
zip_path.write_bytes(r.content)
print(f"ZIP 저장: {zip_path}")
print()

with zipfile.ZipFile(BytesIO(r.content)) as zf:
    files = zf.namelist()
    print(f"[ZIP 내부 파일 - 총 {len(files)}개]")
    print("-" * 40)

    ext_counts = {}
    total_size = 0
    for name in files:
        info = zf.getinfo(name)
        total_size += info.file_size
        ext = Path(name).suffix.lower() or "(확장자 없음)"
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    print("[확장자별 파일 수]")
    for ext, cnt in sorted(ext_counts.items(), key=lambda x: -x[1]):
        print(f" {ext:20} {cnt:>4}개")
    print(f"  (압축 해제 시 총 {total_size/1024/1024:.2f} MB)")
    print()

    print("[파일 목록 - 상위 30개]")
    for name in files[:30]:
        info = zf.getinfo(name)
        size_kb = info.file_size / 1024
        print(f"  {name:60} {size_kb:>10.1f} KB")
    if len(files) > 30:
        print(f"  ... (이하 {len(files)-30}개 생략)")
    print()

    zf.extractall(cache_dir)
    print(f"압축 해제 완료: {cache_dir}")
    print()

    xml_files = sorted([n for n in files if n.endswith(".xml")])
    if xml_files:
        first_xml = xml_files[0]
        with zf.open(first_xml) as f:
            raw = f.read(3000)
            content = raw.decode('utf-8', errors='replace')
            print(f"[{first_xml}] - 처음 3000자 미리보기]")
            print("-" * 40)
            print(content)