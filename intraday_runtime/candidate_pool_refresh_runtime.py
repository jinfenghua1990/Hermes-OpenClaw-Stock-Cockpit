#!/usr/bin/env python3
"""
Phase-2.8D Candidate Pool Refresh Runtime

职责：
- 从 scanner_to_candidate_rankings_adapter 读取全市场候选池（461只）
- 不再从 daily_features.json 生成候选池
- 盘中刷新/校验/标记 Runtime Candidate Pool

数据源优先级：
1. portfolio/candidate_rankings.json (adapter 输出，全市场461只)
2. features/daily_features.json (watchlist 快速候选，回退)

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


def _normalize_symbol(value):
    if value in (None, "", "--"):
        return ""
    symbol = str(value).strip()
    if symbol.isdigit() and len(symbol) <= 6:
        return symbol.zfill(6)
    return symbol


def _to_float(value, default=0.0):
    try:
        if value in (None, "", "--"):
            return default
        return float(value)
    except Exception:
        return default


def _first(row, keys, default=0):
    for key in keys:
        value = row.get(key)
        if value not in (None, "", "--"):
            return value
    return default


def _flatten_row(row):
    """Flatten common nested feature blocks such as indicators."""
    if not isinstance(row, dict):
        return {}

    flat = dict(row)
    for nested_key in ("indicators", "features", "metrics", "runtime_indicators"):
        nested = row.get(nested_key)
        if isinstance(nested, dict):
            for key, value in nested.items():
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

        # symbol keyed: {"000001": {indicators...}}
        symbol_keyed_rows = []
        for key, value in data.items():
            if isinstance(value, dict):
                row = _flatten_row(value)
                row.setdefault("stock_code", key)
                symbol_keyed_rows.append(row)
        if symbol_keyed_rows:
            return symbol_keyed_rows

    return []


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
    change_pct = _to_float(_first(row, ("涨跌幅", "日涨幅", "change_pct", "pct_chg", "pct_change"), 0))
    rsi = _to_float(_first(row, ("RSI", "rsi"), 0))
    vol_ratio_raw = _first(row, ("量比", "vol_ratio", "volume_ratio"), 0)
    vol_ratio_pct = _normalize_vol_ratio(vol_ratio_raw)
    ma20_slope = _to_float(_first(row, ("MA20日升", "MA20斜率", "ma20_slope", "ma20_delta"), 0))
    lower_shadow = _to_float(_first(row, ("下影线", "下影线长度", "lower_shadow", "lower_shadow_length"), 0))

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


def refresh_candidate_pool():
    """
    Phase-2.8D: 优先从 scanner adapter 输出的 candidate_rankings.json 读取全市场候选池。
    adapter 在 scanner_to_candidate_rankings_adapter.py 中完成：
      original_four_modes_scanner.json (4788只扫描) → candidate_rankings.json (461只候选)
    本函数只负责读取 + Runtime 包装（标记/刷新时间/runtime 元数据）。
    唯一回退：adapter 输出不存在，才走旧版 daily_features.json 评分路径。
    """
    now = datetime.now()
    status = {
        "phase": "Phase-2.8D",
        "generated_at": now.isoformat(),
        "runtime_type": "candidate_pool_refresh_runtime",
        "system_mode": "PAPER_ONLY_OBSERVE_ONLY",
        "candidate_file": str(CANDIDATE_FILE),
        "data_source": "scanner_adapter",
    }

    # === 主路径：scanner adapter 输出 ===
    if CANDIDATE_FILE.exists():
        try:
            adapter_data = _load(CANDIDATE_FILE, {})
            candidates = adapter_data.get("candidates", [])
            scanner_stats = adapter_data.get("scanner_stats", {})
            total_universe = adapter_data.get("total_universe", 0)
            source_file = adapter_data.get("source_file", "")

            # Runtime 包装：添加刷新时间 + runtime 元数据
            runtime_candidates = []
            for c in candidates:
                item = dict(c)
                item["runtime_fresh"] = True
                item["runtime_refreshed_at"] = now.isoformat()
                item["source_module"] = "candidate_pool_refresh_runtime"
                item["source_agent"] = "robot_1"
                runtime_candidates.append(item)

            payload = {
                "phase": "Phase-2.8D",
                "generated_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "source": "candidate_pool_refresh_runtime",
                "source_file": source_file,
                "candidate_count": len(runtime_candidates),
                "candidate_quality": "SCANNER_ADAPTER",
                "field_quality": {
                    "dynamic_quality": "SCANNER_DYNAMIC",
                    "total_universe": total_universe,
                    "scanner_stats": scanner_stats,
                },
                "candidates": runtime_candidates,
                "top_candidates": runtime_candidates[:50],
                "runtime_fresh": True,
                "governance_constraints": {
                    "auto_trade": False,
                    "auto_learning": False,
                    "baseline_mutation": False,
                },
            }

            CANDIDATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            CANDIDATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            runtime_status = "PASS_DYNAMIC"
            reason = "scanner_adapter_candidate_pool"

            print(f"Candidate Pool refreshed: {len(runtime_candidates)} candidates status={runtime_status}")
            print(f"  [adapter] universe={total_universe} scanner_stats={scanner_stats}")

            status.update({
                "status": runtime_status,
                "reason": reason,
                "refreshed": True,
                "candidate_count": len(runtime_candidates),
                "field_quality": payload["field_quality"],
                "candidate_file_updated_at": now.isoformat(),
            })
            OUT_STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
            return status

        except Exception as e:
            print(f"[adapter fallback] 读取失败: {e}，回退到 daily_features.json")
            # fall through to fallback

    # === 回退路径：daily_features.json 评分（仅当 adapter 不存在时）===
    print("[fallback] 从 daily_features.json 生成候选池")
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

    candidates = []
    for row in rows:
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
        item["runtime_fresh"] = True
        item["runtime_refreshed_at"] = now.isoformat()
        item["source_agent"] = "robot_1"
        candidates.append(item)

    candidates = sorted(candidates, key=lambda x: x.get("runtime_candidate_score", 0), reverse=True)

    payload = {
        "phase": "Phase-2.8D",
        "generated_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "source": "candidate_pool_refresh_runtime",
        "source_file": str(FEATURES_FILE),
        "candidate_count": len(candidates),
        "candidate_quality": "FALLBACK_FEATURES",
        "field_quality": {"dynamic_quality": "STATIC_FALLBACK"},
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

    if candidates:
        runtime_status = "PASS_STATIC_FALLBACK"
        reason = "fallback_features_only"
    else:
        runtime_status = "WARNING"
        reason = "no_candidates_after_scoring"

    print(f"Candidate Pool refreshed: {len(candidates)} candidates status={runtime_status}")

    status.update({
        "status": runtime_status,
        "reason": reason,
        "refreshed": True,
        "candidate_count": len(candidates),
        "field_quality": payload["field_quality"],
        "candidate_file_updated_at": now.isoformat(),
    })
    OUT_STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return status


if __name__ == "__main__":
    refresh_candidate_pool()
