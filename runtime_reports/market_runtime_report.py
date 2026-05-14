#!/usr/bin/env python3
"""
Phase-2.8C Market Runtime Report
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
EMOTION_FILE = BASE_DIR / "runtime_data" / "market_emotion_runtime.json"
SECTOR_FILE = BASE_DIR / "runtime_data" / "sector_runtime.json"
OUT_FILE = BASE_DIR / "runtime_reports" / "market_runtime_report.md"


def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception:
        return default if default is not None else {}


def build_report():
    emotion = _load(EMOTION_FILE, {})
    sector = _load(SECTOR_FILE, {})

    top_sector = "UNKNOWN"
    if sector.get("sectors"):
        top_sector = sector["sectors"][0].get("sector_name", "UNKNOWN")

    report = f'''# Market Runtime Report

Generated At: {datetime.now().isoformat()}

## Market Emotion

- Emotion: {emotion.get("market_emotion", "UNKNOWN")}
- Risk Level: {emotion.get("risk_level", "UNKNOWN")}
- Dominant Theme: {emotion.get("dominant_theme", top_sector)}
- Turnover Status: {emotion.get("turnover_status", "UNKNOWN")}

## Sector Rotation

- Top Sector: {top_sector}
- Sector Count: {sector.get("sector_count", 0)}

## Runtime Freshness

- Runtime Status: {emotion.get("status", "UNKNOWN")}
- Updated At: {emotion.get("updated_at", "UNKNOWN")}

## System Mode

- PAPER_ONLY
- OBSERVE_ONLY
'''

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(report, encoding='utf-8')

    print("Market Runtime Report generated")
    return report


if __name__ == '__main__':
    build_report()
