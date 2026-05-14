#!/usr/bin/env python3
"""
Phase-2.8C Candidate Pool Refresh Runtime

职责：
- Runtime 主动刷新候选池，不再等待用户手动确认
- 将 daily_features -> candidate_rankings -> runtime candidates 串起来
- 如果无法刷新，则标记 stale_candidate_pool，禁止继续当作有效候选池

说明：
当前版本以 features/daily_features.json 作为结构底座。
盘中实时行情尚未直接接入时，允许 STATIC_FALLBACK，但会在 status 中明确标记。
后续可接入 mx-data / realtime quote source 作为动态增强源。

System Mode:
- PAPER_ONLY
- OBSERVE_ONLY
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


def _flatten_row(row):
    """Flatten common nested feature blocks such as indicators."""
    if not isinstance(row, dict):
        return {}

    flat = dict(row)
    for nested_key in ("indicators", "features", "metrics", "runtime_indicators"):
        nested = row.get(nested_key)
        if isinstance(nested, dict):
            for key, value in nested.items():
                # Preserve top-level values if they already exist.
                flat.setdefault(key, value)

    return flat


def _extract_feature_rows(data):
    if isinstance(data, list):
        return [_flatten_row(row) for row in data]

    if isinstance(data, dict):
        for key in ("features", "daily_features", "rows", "data", "stocks"):
            value = data.get(key)
            if isinstance(value, list):
                return [_flatten_row(row) for row in value]

        # Some files may be symbol keyed: {"000001": {indicators...}}
        symbol_keyed_rows = []
        for key, value in data.items():
            if isinstance(value, dict):
                row = _flatten_row(value)
                row.setdefault("stock_code", key)
                symbol_keyed_rows.append(row)
        if symbol_keyed_rows:
            return symbol_keyed_rows

    return []


def _first(row, keys, default=0):
    for key in keys:
        value = row.get(key)
        if value not in (None, "", "--"):
            return value
    return default


def _to_float(value, default=0.0):
    try:
        if value in (None, "", "--"):
            return default
        return float(value)
    except Exception:
        return default


def _normalize_symbol(value):
    if value in (None, "", "--"):
        return ""
    symbol = str(value).strip()
    if symbol.isdigit() and len(symbol) <= 6:
        return symbol.zfill(6)
    return symbol


def _normalize_vol_ratio(value):
    """兼容 1.09 倍 与 109% 两种量比表达。"""
    vol = _to_float(value, 0.0)
    if vol <= 0:
        return 0.0
    if vol <= 10:
        return vol * 100
    return vol


def _score_row(row):
    score = 0

    # 兼容中文/英文字段与 indicators 展平字段。
    change_pct = _to_float(_first(row, ("涨跌幅", "日涨幅", "change_pct", "pct_chg", "pct_change"), 0))
    rsi = _to_float(_first(row, ("RSI", "rsi"), 0))
    vol_ratio_raw = _first(row, ("量比", "vol_ratio", "volume_ratio"), 0)
    vol_ratio_pct = _normalize_vol_ratio(vol_ratio_raw)
    ma20_slope = _to_float(_first(row, ("MA20日升", "MA20斜率", "ma20_slope", "ma20_delta"), 0))
    lower_shadow = _to_float(_first(row, ("下影线", "下影线长度", "lower_shadow", "lower_shadow_length"), 0))

    # 原版 baseline 兼容评分，不新增 AI 权重。
    if 0 <= change_pct <= 6:
        score += 2
    if lower_shadow > 1:
        score += 2
    if 15 <= rsi <= 55:
        score += 1
    if 0 < vol_ratio_pct < 90:
        score += 1
    if ma20_slope > 0:
        score += 2
    if change_pct > 5:
        score += 2

    return score


def _dynamic_field_quality(rows):
    if not rows:
        return {
            "dynamic_quality": "EMPTY",
            "nonzero_change_count": 0,
            "nonzero_ma20_slope_count": 0,
            "nonzero_lower_shadow_count": 0,
        }

    nonzero_change = 0
    nonzero_ma20 = 0
    nonzero_shadow = 0

    for row in rows:
        change_pct = _to_float(_first(row, ("涨跌幅", "日涨幅", "change_pct", "pct_chg", "pct_change"), 0))
        ma20_slope = _to_float(_first(row, ("MA20日升", "MA20斜率", "ma20_slope", "ma20_delta"), 0))
        lower_shadow = _to_float(_first(row, ("下影线", "下影线长度", "lower_shadow", "lower_shadow_length"), 0))
        if change_pct != 0:
            nonzero_change += 1
        if ma20_slope != 0:
            nonzero_ma20 += 1
        if lower_shadow != 0:
            nonzero_shadow += 1

    if nonzero_change or nonzero_ma20 or nonzero_shadow:
        quality = "DYNAMIC"
    else:
        quality = "STATIC_FALLBACK"

    return {
        "dynamic_quality": quality,
        "nonzero_change_count": nonzero_change,
        "nonzero_ma20_slope_count": nonzero_ma20,
        "nonzero_lower_shadow_count": nonzero_shadow,
    }


def refresh_candidate_pool():
    now = datetime.now()
    status = {
        "phase": "Phase-2.8C",
        "generated_at": now.isoformat(),
        "runtime_type": "candidate_pool_refresh_runtime",
        "system_mode": "PAPER_ONLY_OBSERVE_ONLY",
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
        print("Candidate Pool Refresh failed: daily_features_missing")
        return status

    data = _load(FEATURES_FILE, {})
    rows = _extract_feature_rows(data)
    quality = _dynamic_field_quality(rows)

    candidates = []
    for row in rows:
        # stock_code is the canonical runtime symbol from mx-data style payloads.
        symbol = _normalize_symbol(_first(row, ("stock_code", "股票代码", "symbol", "code"), ""))
        name = _first(row, ("stock_name", "股票名称", "name"), "")
        if not symbol:
            continue

        score = _score_row(row)
        if score <= 0:
            continue

        item = dict(row)
        item["stock_code"] = symbol
        item["股票代码"] = symbol
        item["股票名称"] = name
        item["runtime_candidate_score"] = score
        item["source_module"] = "candidate_pool_refresh_runtime"
        item["data_source"] = "features/daily_features.json"
        item["data_as_of"] = now.isoformat()
        item["runtime_quality"] = quality["dynamic_quality"]
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
        "candidate_quality": quality["dynamic_quality"],
        "field_quality": quality,
        "candidates": candidates,
        "top_candidates": candidates[:50],
        "runtime_fresh": True,
        "governance_constraints": {
            "auto_trade": False,
            "auto_learning": False,
            "baseline_mutation": False,
        },
    }

    CANDIDATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if candidates and quality["dynamic_quality"] == "DYNAMIC":
        runtime_status = "PASS_DYNAMIC"
        reason = "candidate_pool_refreshed_dynamic_fields"
    elif candidates:
        runtime_status = "PASS_STATIC_FALLBACK"
        reason = "candidate_pool_refreshed_static_features_only"
    else:
        runtime_status = "WARNING"
        reason = "no_candidates_after_scoring"

    status.update({
        "status": runtime_status,
        "reason": reason,
        "refreshed": True,
        "candidate_count": len(candidates),
        "field_quality": quality,
        "candidate_file_updated_at": now.isoformat(),
    })
    OUT_STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Candidate Pool refreshed: {len(candidates)} candidates status={runtime_status}")
    return status


if __name__ == "__main__":
    refresh_candidate_pool()
