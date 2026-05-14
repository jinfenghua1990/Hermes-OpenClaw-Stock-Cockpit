#!/usr/bin/env python3
"""
Phase-2.8C Realtime Structure Refresh

职责：
- 盘中实时刷新结构数据
- 检测 stale runtime data
- 输出 structure/support/pressure freshness 状态

注意：
此模块先负责 runtime freshness 检测与结构缓存刷新入口；真实行情抓取由 intraday_market_data_runtime.py 提供。
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_FILE = BASE_DIR / "intraday_runtime" / "realtime_structure_runtime.json"

STALE_MINUTES = 20


def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default or {}


def _is_unknown(value):
    return value in (None, "", "unknown", "UNKNOWN", 0, 0.0)


def refresh_runtime():
    top_picks = _load(BASE_DIR / "reports" / "top_picks.json", {})
    market_data = _load(BASE_DIR / "intraday_runtime" / "intraday_market_data_runtime.json", {})
    latest_quotes = {
        item.get("symbol"): item
        for item in market_data.get("quotes", [])
        if item.get("symbol")
    }

    refreshed = []
    stale_count = 0

    for item in top_picks.get("top_picks", []):
        symbol = item.get("股票代码") or item.get("symbol")
        quote = latest_quotes.get(symbol, {})
        structure_type = item.get("structure_type", "unknown")
        support = item.get("support_price") or item.get("support")
        pressure = item.get("pressure_price") or item.get("pressure")
        current_price = quote.get("current_price") or item.get("最新价") or item.get("价格")

        stale = _is_unknown(structure_type) or _is_unknown(current_price)
        if stale:
            stale_count += 1

        refreshed.append({
            "symbol": symbol,
            "name": item.get("股票名称") or item.get("name"),
            "current_price": current_price,
            "structure_type": structure_type,
            "support": support,
            "pressure": pressure,
            "runtime_refreshed_at": datetime.now().isoformat(),
            "runtime_data_stale_or_missing": stale,
            "stale_reason": "structure_or_price_missing" if stale else "",
            "source_agent": "robot_2",
            "source_module": "realtime_structure_refresh",
            "data_source": quote.get("data_source", "intraday_market_data_runtime"),
        })

    runtime = {
        "phase": "Phase-2.8C",
        "generated_at": datetime.now().isoformat(),
        "runtime_type": "realtime_structure_refresh",
        "stale_threshold_minutes": STALE_MINUTES,
        "total": len(refreshed),
        "stale_count": stale_count,
        "status": "WARNING" if stale_count else "PASS",
        "structures": refreshed,
    }

    OUT_FILE.write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding="utf-8")

    print("✅ Realtime Structure Runtime refreshed")
    print(f"   structures={len(refreshed)} stale={stale_count}")
    return runtime


if __name__ == "__main__":
    refresh_runtime()
