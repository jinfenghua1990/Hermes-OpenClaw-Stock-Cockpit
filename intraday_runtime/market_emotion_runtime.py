#!/usr/bin/env python3
"""
Phase-2.8C Market Emotion Runtime

职责：
- 生成市场情绪 Runtime
- 提供 Runtime 风险温度
- 服务 Runtime Reports / AI Arbitration

System Mode:
- PAPER_ONLY
- OBSERVE_ONLY
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "runtime_data"
OUT_FILE = OUT_DIR / "market_emotion_runtime.json"
SECTOR_RUNTIME = OUT_DIR / "sector_runtime.json"
CANDIDATE_FILE = BASE_DIR / "portfolio" / "candidate_rankings.json"


def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def _rows(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("top_candidates", "candidates", "rows", "data"):
        if isinstance(payload.get(key), list):
            return payload.get(key)
    return []


def _float(v, default=0):
    try:
        return float(v)
    except Exception:
        return default


def build_market_emotion_runtime():
    now = datetime.now().isoformat()
    sector_runtime = _load(SECTOR_RUNTIME, {})
    candidate_payload = _load(CANDIDATE_FILE, {})
    candidates = _rows(candidate_payload)

    changes = [
        _float(item.get("涨跌幅", item.get("change_pct", item.get("pct_chg", 0))))
        for item in candidates
    ]

    positive = sum(1 for x in changes if x > 0)
    negative = sum(1 for x in changes if x < 0)
    limit_up = sum(1 for x in changes if x >= 9.5)
    limit_down = sum(1 for x in changes if x <= -9.5)

    avg_change = sum(changes) / len(changes) if changes else 0

    sectors = sector_runtime.get("sectors", [])
    dominant_theme = sectors[0].get("sector_name") if sectors else "UNKNOWN"

    if avg_change >= 4:
        market_emotion = "HOT"
        risk_level = 0.75
    elif avg_change >= 1:
        market_emotion = "WARM"
        risk_level = 0.45
    elif avg_change <= -2:
        market_emotion = "COLD"
        risk_level = 0.88
    else:
        market_emotion = "NEUTRAL"
        risk_level = 0.55

    payload = {
        "phase": "Phase-2.8C",
        "runtime_type": "market_emotion_runtime",
        "system_mode": "PAPER_ONLY_OBSERVE_ONLY",
        "generated_at": now,
        "updated_at": now,
        "market_emotion": market_emotion,
        "risk_level": round(risk_level, 2),
        "limit_up_count": limit_up,
        "limit_down_count": limit_down,
        "positive_count": positive,
        "negative_count": negative,
        "turnover_status": "ACTIVE" if positive > negative else "WEAK",
        "dominant_theme": dominant_theme,
        "rotation_speed": "FAST" if len(sectors) >= 5 else "NORMAL",
        "status": "PASS",
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Market Emotion Runtime generated: {market_emotion}")
    return payload


if __name__ == "__main__":
    build_market_emotion_runtime()
