from dotenv import load_dotenv; load_dotenv()
from mcp_servers.dart_server import fetch_amendment_details
import json
print(json.dumps(fetch_amendment_details("20260629801230"), ensure_ascii=False, indent=2)[:1200])