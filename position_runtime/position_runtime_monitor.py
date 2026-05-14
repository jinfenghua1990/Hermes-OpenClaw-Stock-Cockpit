#!/usr/bin/env python3
"""
Phase-2.8B Position Runtime Monitor

目标：
- 持仓优先于 Top Picks
- 生成 position runtime summary
- 生成 position risk alerts

仅允许：
PAPER_ONLY
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
POSITION_FILE = BASE_DIR / "position_runtime" / "position_registry.json"
OUT_FILE = BASE_DIR / "position_runtime" / "position_runtime_summary.json"


def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default or {}


def build_runtime_summary():
    registry = _load(POSITION_FILE, {})
    positions = registry.get("positions", [])

    alerts = []

    for p in positions:
        symbol = p.get("symbol")
        name = p.get("name")
        current_price = p.get("current_price")
        stop_loss = p.get("stop_loss")
        take_profit = p.get("take_profit")

        if current_price and stop_loss and current_price <= stop_loss:
            alerts.append({
                "symbol": symbol,
                "name": name,
                "type": "stop_loss_triggered",
                "current_price": current_price,
                "stop_loss": stop_loss,
            })

        if current_price and take_profit and current_price >= take_profit:
            alerts.append({
                "symbol": symbol,
                "name": name,
                "type": "take_profit_watch",
                "current_price": current_price,
                "take_profit": take_profit,
            })

    summary = {
        "phase": "Phase-2.8B",
        "generated_at": datetime.now().isoformat(),
        "account_mode": "PAPER_ONLY",
        "position_count": len(positions),
        "positions": positions,
        "alerts": alerts,
        "alert_count": len(alerts),
        "position_runtime_active": True,
    }

    OUT_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Position Runtime Summary generated")
    print(f"   positions={len(positions)} alerts={len(alerts)}")

    return summary


if __name__ == "__main__":
    build_runtime_summary()
