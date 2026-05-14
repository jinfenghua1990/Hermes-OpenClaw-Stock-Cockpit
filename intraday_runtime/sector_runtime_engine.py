#!/usr/bin/env python3
"""
Phase-2.8C Sector Runtime Engine

职责：
- 生成盘中板块 Runtime 快照
- 仅做结构化 Runtime 数据，不做 AI 自动解释、不做自动调参
- 服务后续 market_runtime_report / ai_arbitration_runtime

System Mode:
- PAPER_ONLY
- OBSERVE_ONLY
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "runtime_data"
OUT_FILE = OUT_DIR / "sector_runtime.json"
CANDIDATE_FILE = BASE_DIR / "portfolio" / "candidate_rankings.json"
TOP_PICKS_FILE = BASE_DIR / "reports" / "top_picks.json"


def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def _rows_from_payload(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("top_candidates", "candidates", "top_picks", "rows", "data", "stocks"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _float(value, default=0.0):
    try:
        if value in (None, "", "--"):
            return default
        return float(value)
    except Exception:
        return default


def _sector_name(row):
    return (
        row.get("板块")
        or row.get("所属板块")
        or row.get("行业")
        or row.get("sector")
        or row.get("industry")
        or "UNKNOWN"
    )


def _symbol(row):
    return row.get("股票代码") or row.get("symbol") or row.get("code") or ""


def _name(row):
    return row.get("股票名称") or row.get("name") or row.get("stock_name") or ""


def _change_pct(row):
    return _float(row.get("涨跌幅", row.get("change_pct", row.get("pct_chg", 0))))


def _volume_ratio(row):
    return _float(row.get("量比", row.get("vol_ratio", row.get("volume_ratio", 0))))


def build_sector_runtime():
    now = datetime.now().isoformat()
    candidate_payload = _load(CANDIDATE_FILE, {})
    top_picks_payload = _load(TOP_PICKS_FILE, {})

    rows = _rows_from_payload(candidate_payload)
    if not rows:
        rows = _rows_from_payload(top_picks_payload)

    sectors = defaultdict(list)
    for row in rows:
        sectors[_sector_name(row)].append(row)

    sector_items = []
    for sector, items in sectors.items():
        changes = [_change_pct(item) for item in items]
        vols = [_volume_ratio(item) for item in items]
        avg_change = sum(changes) / len(changes) if changes else 0.0
        avg_vol = sum(vols) / len(vols) if vols else 0.0
        positive_count = sum(1 for x in changes if x > 0)

        strength_score = round(max(0, min(100, 50 + avg_change * 5 + positive_count * 3 + avg_vol * 0.8)), 2)
        if strength_score >= 75:
            momentum = "UP"
        elif strength_score <= 40:
            momentum = "DOWN"
        else:
            momentum = "NEUTRAL"

        volume_status = "EXPANDING" if avg_vol >= 1.2 else "NORMAL" if avg_vol > 0 else "UNKNOWN"
        leaders = sorted(
            [
                {
                    "symbol": _symbol(item),
                    "name": _name(item),
                    "change_pct": _change_pct(item),
                    "runtime_candidate_score": item.get("runtime_candidate_score", 0),
                }
                for item in items
            ],
            key=lambda x: (x.get("runtime_candidate_score") or 0, x.get("change_pct") or 0),
            reverse=True,
        )[:5]

        sector_items.append({
            "sector_name": sector,
            "strength_score": strength_score,
            "momentum": momentum,
            "volume_status": volume_status,
            "leaders": leaders,
            "risk_flag": avg_change <= -3 or strength_score <= 30,
            "member_count": len(items),
            "updated_at": now,
        })

    sector_items = sorted(sector_items, key=lambda x: x["strength_score"], reverse=True)
    payload = {
        "phase": "Phase-2.8C",
        "runtime_type": "sector_runtime_engine",
        "system_mode": "PAPER_ONLY_OBSERVE_ONLY",
        "generated_at": now,
        "updated_at": now,
        "source": "candidate_rankings_or_top_picks",
        "sector_count": len(sector_items),
        "status": "PASS" if sector_items else "WARNING",
        "reason": "sector_runtime_generated" if sector_items else "no_sector_source_rows",
        "sectors": sector_items,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Sector Runtime generated: sectors={len(sector_items)}")
    return payload


if __name__ == "__main__":
    build_sector_runtime()
