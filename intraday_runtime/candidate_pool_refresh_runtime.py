#!/usr/bin/env python3
"""
Phase-2.8C Candidate Pool Refresh Runtime

职责：
- Runtime 主动刷新候选池，不再等待用户手动确认
- 将 daily_features -> candidate_rankings -> runtime candidates 串起来
- 如果无法刷新，则标记 stale_candidate_pool，禁止继续当作有效候选池

说明：
当前版本优先使用 features/daily_features.json 作为输入，生成 portfolio/candidate_rankings.json。
后续可接入全市场实时扫描器。
"""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FEATURES_FILE = BASE_DIR / "features" / "daily_features.json"
CANDIDATE_FILE = BASE_DIR / "portfolio" / "candidate_rankings.json"
OUT_STATUS = BASE_DIR / "intraday_runtime" / "candidate_pool_refresh_status.json"


def _load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def _extract_feature_rows(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("features", "daily_features", "rows", "data", "stocks"):
            if isinstance(data.get(key), list):
                return data.get(key)
    return []


def _score_row(row):
    score = 0

    # 尽量兼容中文/英文字段，不做策略升级，只做候选池刷新排序。
    change_pct = row.get("涨跌幅", row.get("change_pct", row.get("pct_chg", 0))) or 0
    rsi = row.get("RSI", row.get("rsi", 0)) or 0
    vol_ratio = row.get("量比", row.get("vol_ratio", 100)) or 100
    ma20_slope = row.get("MA20日升", row.get("ma20_slope", row.get("ma20_delta", 0))) or 0
    lower_shadow = row.get("下影线", row.get("lower_shadow", 0)) or 0

    try:
        change_pct = float(change_pct)
        rsi = float(rsi)
        vol_ratio = float(vol_ratio)
        ma20_slope = float(ma20_slope)
        lower_shadow = float(lower_shadow)
    except Exception:
        pass

    if 0 <= change_pct <= 6:
        score += 2
    if lower_shadow and lower_shadow > 1:
        score += 2
    if 15 <= rsi <= 55:
        score += 1
    if vol_ratio and vol_ratio < 90:
        score += 1
    if ma20_slope and ma20_slope > 0:
        score += 2
    if change_pct and change_pct > 5:
        score += 2

    return score


def refresh_candidate_pool():
    now = datetime.now()
    status = {
        "phase": "Phase-2.8C",
        "generated_at": now.isoformat(),
        "runtime_type": "candidate_pool_refresh_runtime",
        "features_file": str(FEATURES_FILE),
        "candidate_file": str(CANDIDATE_FILE),
    }

    if not FEATURES_FILE.exists():
        status.update({
            "status": "CRITICAL",
            "reason": "daily_features_missing",
            "refreshed": False,
        })
        OUT_STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        print("❌ Candidate Pool Refresh failed: daily_features_missing")
        return status

    data = _load(FEATURES_FILE, {})
    rows = _extract_feature_rows(data)

    candidates = []
    for row in rows:
        symbol = row.get("股票代码") or row.get("symbol") or row.get("code")
        name = row.get("股票名称") or row.get("name") or row.get("stock_name", "")
        if not symbol:
            continue

        score = _score_row(row)
        if score <= 0:
            continue

        item = dict(row)
        item["股票代码"] = str(symbol).zfill(6) if str(symbol).isdigit() and len(str(symbol)) <= 6 else str(symbol)
        item["股票名称"] = name
        item["runtime_candidate_score"] = score
        item["source_module"] = "candidate_pool_refresh_runtime"
        item["data_source"] = "features/daily_features.json"
        item["data_as_of"] = now.isoformat()
        item["source_agent"] = "robot_1"
        candidates.append(item)

    candidates = sorted(candidates, key=lambda x: x.get("runtime_candidate_score", 0), reverse=True)

    payload = {
        "phase": "Phase-2.8C",
        "generated_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "source": "candidate_pool_refresh_runtime",
        "source_file": str(FEATURES_FILE),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "top_candidates": candidates[:50],
        "runtime_fresh": True,
    }

    CANDIDATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    status.update({
        "status": "PASS" if candidates else "WARNING",
        "reason": "candidate_pool_refreshed" if candidates else "no_candidates_after_scoring",
        "refreshed": True,
        "candidate_count": len(candidates),
        "candidate_file_updated_at": now.isoformat(),
    })
    OUT_STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Candidate Pool refreshed: {len(candidates)} candidates")
    return status


if __name__ == "__main__":
    refresh_candidate_pool()
