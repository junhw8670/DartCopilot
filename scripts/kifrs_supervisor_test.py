import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from app.main import app
from scripts.kifrs_search_test import REALISTIC_PARAGRAPH_QUERIES


TARGET_IDS = {"R01", "R03", "R05", "R12", "R14", "R16"}

targets = [
    item
    for item in REALISTIC_PARAGRAPH_QUERIES
    if item["id"] in TARGET_IDS
]


with TestClient(app) as client:
    for item in targets:
        result = client.portal.call(
            app.state.graph.ainvoke,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": item["query"],
                    }
                ]
            },
        )

        messages = result["messages"]

        call_count = sum(
            getattr(message, "name", None) == "search_kifrs"
            for message in messages
        )

        print(f"\n========== {item['id']} ==========")
        print(f"search_kifrs 호출: {call_count}회")
        print(messages[-1].content)
        for message in messages:
            for call in getattr(message, "tool_calls", []) or []:
                if call.get("name") == "search_kifrs":
                    print(
                        "검색 주체:",
                        getattr(message, "name", None),
                    )
                    print(
                        "검색어:",
                        call.get("args", {}).get("query"),
                    )