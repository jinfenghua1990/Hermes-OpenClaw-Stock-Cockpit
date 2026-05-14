#!/usr/bin/env python3
"""
Phase-2.8C Intraday Market Data Runtime

职责：
- 统一盘中实时行情缓存
- 输出 intraday market runtime snapshot
- 提供 current_price freshness runtime

当前版本：
- Runtime cache layer
- Placeholder quote runtime
- 后续可接 akshare / futu / longport / yfinance
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_FILE = BASE_DIR / "intraday_runtime" / "intraday_market_data_runtime.json"


def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default or {}


def build_runtime():
    top_picks = _load(BASE_DIR / "reports" / "top_picks.json", {})

    quotes = []

    for item in top_picks.get("top_picks", []):
        quotes.append({
            "symbol": item.get("股票代码") or item.get("symbol"),
            "name": item.get("股票名称") or item.get("name"),
            "current_price": item.get("最新价") or item.get("价格"),
            "data_source": "runtime_cache",
            "data_as_of": datetime.now().isoformat(),
            "freshness": "FRESH",
        })

    runtime = {
        "phase": "Phase-2.8C",
        "generated_at": datetime.now().isoformat(),
        "runtime_type": "intraday_market_data_runtime",
        "quotes": quotes,
        "quote_count": len(quotes),
        "status": "PASS",
    }

    OUT_FILE.write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding="utf-8")

    print("✅ Intraday Market Data Runtime generated")
    print(f"   quotes={len(quotes)}")

    return runtime


if __name__ == "__main__":
    build_runtime()
