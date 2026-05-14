#!/usr/bin/env python3
"""
Phase-2.8C AI Arbitration Runtime

职责：
- Runtime 多信号仲裁
- 第一阶段仅使用 rule-based arbitration
- 不使用自动学习
- 不使用自动调参

System Mode:
- PAPER_ONLY
- OBSERVE_ONLY
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
EMOTION_FILE = BASE_DIR / "runtime_data" / "market_emotion_runtime.json"
SECTOR_FILE = BASE_DIR / "runtime_data" / "sector_runtime.json"
STRUCTURE_FILE = BASE_DIR / "intraday_runtime" / "realtime_structure_runtime.json"
OUT_FILE = BASE_DIR / "runtime_data" / "ai_arbitration_runtime.json"


def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def build_runtime():
    now = datetime.now().isoformat()

    emotion = _load(EMOTION_FILE, {})
    sector = _load(SECTOR_FILE, {})
    structure = _load(STRUCTURE_FILE, {})

    bullish_score = 50
    bearish_score = 50
    confidence = 50
    risk_override = False
    traces = []

    market_emotion = emotion.get("market_emotion", "UNKNOWN")

    if market_emotion == "HOT":
        bullish_score += 20
        confidence += 15
        traces.append("market_emotion_hot")

    elif market_emotion == "WARM":
        bullish_score += 10
        confidence += 5
        traces.append("market_emotion_warm")

    elif market_emotion == "COLD":
        bearish_score += 25
        confidence -= 20
        risk_override = True
        traces.append("market_emotion_cold")

    sector_count = sector.get("sector_count", 0)
    if sector_count >= 5:
        bullish_score += 10
        traces.append("sector_rotation_active")

    stale_count = structure.get("stale_count", 0)
    if stale_count > 0:
        bearish_score += 15
        confidence -= 15
        risk_override = True
        traces.append("structure_runtime_stale")

    if bullish_score > bearish_score:
        arbitration_result = "BULLISH"
    elif bearish_score > bullish_score:
        arbitration_result = "BEARISH"
    else:
        arbitration_result = "NEUTRAL"

    payload = {
        "phase": "Phase-2.8C",
        "runtime_type": "ai_arbitration_runtime",
        "system_mode": "PAPER_ONLY_OBSERVE_ONLY",
        "generated_at": now,
        "arbitration_result": arbitration_result,
        "bullish_score": bullish_score,
        "bearish_score": bearish_score,
        "confidence": max(0, min(100, confidence)),
        "risk_override": risk_override,
        "trace": traces,
        "status": "PASS",
        "governance_constraints": {
            "auto_trade": False,
            "auto_learning": False,
            "baseline_mutation": False,
        }
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"AI Arbitration Runtime generated: {arbitration_result}")
    return payload


if __name__ == "__main__":
    build_runtime()
