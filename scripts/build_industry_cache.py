from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import FinanceDataReader as fdr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mcp_servers.dart_server import _load_companies

OUTPUT = Path(__file__).resolve().parent.parent / "cache" / "industry_codes.json"


def main():
    if OUTPUT.exists():
        print(f"이미 존재:{OUTPUT} (재빌드하려면 삭제 후 재실행)")
        return
    stock_to_corp = {c["stock_code"]: c for c in _load_companies() if c["stock_code"]}

    df = fdr.StockListing("KRX-DESC")

    result: dict[str, dict] = {}
    for _, row in df.iterrows():
        industry = row.get("Industry")
        if pd.isna(industry):
            continue

        stock_code = str(row["Code"]).zfill(6)
        corp = stock_to_corp.get(stock_code)
        if corp is None:
            continue

        result[corp["corp_code"]] = {
            "corp_name": corp["corp_name"],
            "stock_code": stock_code,
            "market": row.get("Market"),
            "industry": industry,
        }
        
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(len(result))

if __name__ == "__main__":
    main()
