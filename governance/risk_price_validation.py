#!/usr/bin/env python3
"""
Phase-2.6D Risk Price Validation Gate
统一校验所有风险价格结构，在进入 paper_trade_executor 前拦截无效价格结构。

职责：
- validate_risk_price_structure(payload) 统一入口
- 校验 current_price / support / pressure / stop_loss / take_profit / entry_zone
- 校验 data_as_of 时间一致性
- 返回标准化校验结果

禁止：
- 修改任何 baseline
- 自动学习
- 实盘交易
"""
import json
from datetime import datetime
from typing import Optional, Dict, List, Any

NOW       = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
TODAY_S   = datetime.now().strftime('%Y-%m-%d')


def validate_risk_price_structure(payload: dict) -> dict:
    """
    校验风险价格结构。

    Args:
        payload: {
            "symbol": str,
            "name": str,
            "current_price": float,
            "support_price": float,
            "pressure_price": float,
            "stop_loss": float,
            "take_profit_watch": float,
            "entry_zone_min": float,
            "entry_zone_max": float,
            "data_as_of": str,          # current_price 时间戳
            "support_data_as_of": str,  # support_price 时间戳
            "pressure_data_as_of": str, # pressure_price 时间戳
            "risk_data_as_of": str,     # stop_loss/take_profit 时间戳
        }

    Returns:
        {
            "validation_passed": bool,
            "decision": "paper_observe" | "paper_skip",
            "reason": None | "invalid_price_structure",
            "errors": [str, ...],
            "warnings": [str, ...],
            "risk_data_as_of": str,
            "validator": "risk_price_validation",
            "version": "phase_2_6d",
            "timestamp": str,
            "corrected_values": dict | None,
        }
    """
    symbol  = payload.get('symbol', 'UNKNOWN')
    name    = payload.get('name', symbol)
    cp      = payload.get('current_price', 0)
    support = payload.get('support_price', 0)
    press   = payload.get('pressure_price', 0)
    sl      = payload.get('stop_loss', 0)
    tp      = payload.get('take_profit_watch', 0)
    zone_min= payload.get('entry_zone_min', 0)
    zone_max= payload.get('entry_zone_max', 0)

    da      = payload.get('data_as_of', '')
    da_sup  = payload.get('support_data_as_of', da)
    da_press= payload.get('pressure_data_as_of', da)
    da_risk = payload.get('risk_data_as_of', da)

    errors  : List[str] = []
    warnings: List[str] = []
    corrected = {}

    # ── 规则0：价格必须 > 0 ───────────────────────────────────────────
    if cp <= 0:
        errors.append(f"current_price({cp}) <= 0，无效价格")
    if support <= 0:
        errors.append(f"support_price({support}) <= 0，无效价格")
    if press <= 0:
        errors.append(f"pressure_price({press}) <= 0，无效价格")
    if sl <= 0:
        errors.append(f"stop_loss({sl}) <= 0，无效价格")
    if tp <= 0:
        warnings.append(f"take_profit_watch({tp}) <= 0，止盈位未设置")

    # ── 规则1：support_price <= current_price ─────────────────────────
    if cp > 0 and support > 0:
        if support > cp:
            errors.append(f"support_price({support}) > current_price({cp})，支撑已破")
            # 修正：用 cp × 0.92 作为支撑
            corrected['support_price'] = round(cp * 0.92, 2)

    # ── 规则2：stop_loss < current_price ──────────────────────────────
    if cp > 0 and sl > 0:
        if sl >= cp:
            errors.append(f"stop_loss({sl}) >= current_price({cp})，止损方向错误")
            # 修正：cp × 0.92
            corrected['stop_loss'] = round(cp * 0.92, 2)
        elif sl < cp * 0.70:
            warnings.append(f"stop_loss({sl}) < current_price({cp})×0.70，止损过于激进")

    # ── 规则3：pressure_price > current_price ─────────────────────────
    if cp > 0 and press > 0:
        if press <= cp:
            errors.append(f"pressure_price({press}) <= current_price({cp})，已突破压力位")
            # 修正：cp × 1.10
            corrected['pressure_price'] = round(cp * 1.10, 2)
        elif press < cp * 1.01:
            warnings.append(f"pressure_price({press}) 接近当前价，突破概率低")

    # ── 规则4：support <= current_price <= pressure ───────────────────
    if cp > 0 and support > 0 and press > 0:
        if support > cp:
            errors.append(f"support({support}) > current_price({cp})，已跌破支撑")
        if cp > press:
            errors.append(f"current_price({cp}) > pressure({press})，已突破压力")

    # ── 规则5：take_profit_watch > current_price ──────────────────────
    if cp > 0 and tp > 0:
        if tp <= cp:
            errors.append(f"take_profit_watch({tp}) <= current_price({cp})，止盈位错误")
            # 修正：cp × 1.15
            corrected['take_profit_watch'] = round(cp * 1.15, 2)

    # ── 规则6：entry_zone 偏离 current_price <= 15% ───────────────────
    if cp > 0 and zone_min > 0 and zone_max > 0:
        zone_mid = (zone_min + zone_max) / 2
        deviation = abs(zone_mid - cp) / cp * 100
        if deviation > 15:
            warnings.append(f"entry_zone({zone_min}~{zone_max}) 偏离现价{cp} {deviation:.1f}% > 15%")
        if zone_max < cp:
            warnings.append(f"entry_zone_max({zone_max}) < current_price({cp})，区间设置错误")
            # 修正
            corrected['entry_zone_min'] = round(cp * 0.97, 2)
            corrected['entry_zone_max'] = round(cp * 1.03, 2)

    # ── 规则7：所有价格 data_as_of 必须一致 ────────────────────────────
    timestamps = [
        ('current_price', da),
        ('support_price', da_sup),
        ('pressure_price', da_press),
        ('risk_data', da_risk),
    ]
    seen = {}
    for field, ts in timestamps:
        if ts and ts != da:
            seen[field] = ts
    if seen:
        errors.append(f"data_as_of 时间戳不一致: {seen}")
        warnings.append(f"price timestamps: current={da}, support={da_sup}, pressure={da_press}, risk={da_risk}")

    # ── 判定 ───────────────────────────────────────────────────────────
    validation_passed = len(errors) == 0

    result = {
        "validation_passed": validation_passed,
        "decision": "paper_observe" if validation_passed else "paper_skip",
        "reason": None if validation_passed else "invalid_price_structure",
        "errors": errors if errors else [],
        "warnings": warnings if warnings else [],
        "risk_data_as_of": da_risk or NOW,
        "validator": "risk_price_validation",
        "version": "phase_2_6d",
        "timestamp": NOW,
        "corrected_values": corrected if corrected else None,
    }

    return result


def validate_batch(payloads: List[dict]) -> List[dict]:
    """批量校验多个股票"""
    return [validate_risk_price_structure(p) for p in payloads]


# ── CLI 演示 ─────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=== Phase-2.6D Risk Price Validation Gate ===\n")

    # Case 1：stop_loss > current_price → 必须 FAIL
    case1 = {
        "symbol": "301282",
        "name": "金禄电子",
        "current_price": 30.75,
        "support_price": 36.53,
        "pressure_price": 38.00,
        "stop_loss": 35.43,
        "take_profit_watch": 0,
        "entry_zone_min": 0,
        "entry_zone_max": 0,
        "data_as_of": "2026-05-13T15:00:00",
        "support_data_as_of": "2026-05-13T15:00:00",
        "pressure_data_as_of": "2026-05-13T15:00:00",
        "risk_data_as_of": "2026-05-13T15:00:00",
    }

    # Case 2：正常结构 → 必须 PASS
    case2 = {
        "symbol": "301283",
        "name": "测试股票",
        "current_price": 30.75,
        "support_price": 29.80,
        "pressure_price": 33.50,
        "stop_loss": 28.91,
        "take_profit_watch": 33.50,
        "entry_zone_min": 30.20,
        "entry_zone_max": 31.00,
        "data_as_of": "2026-05-13T15:00:00",
        "support_data_as_of": "2026-05-13T15:00:00",
        "pressure_data_as_of": "2026-05-13T15:00:00",
        "risk_data_as_of": "2026-05-13T15:00:00",
    }

    # Case 3：data_as_of 不一致 → 必须 FAIL
    case3 = {
        "symbol": "301284",
        "name": "时间冲突股票",
        "current_price": 30.75,
        "support_price": 29.80,
        "pressure_price": 33.50,
        "stop_loss": 28.91,
        "take_profit_watch": 33.50,
        "entry_zone_min": 30.20,
        "entry_zone_max": 31.00,
        "data_as_of": "2026-05-13T15:00:00",
        "support_data_as_of": "2026-05-12T15:00:00",
        "pressure_data_as_of": "2026-05-13T15:00:00",
        "risk_data_as_of": "2026-05-13T15:00:00",
    }

    for i, case in enumerate([case1, case2, case3], 1):
        result = validate_risk_price_structure(case)
        status = "✅ PASS" if result['validation_passed'] else "❌ FAIL"
        print(f"Case {i}: {case['name']} ({case['symbol']}) — {status}")
        if result['errors']:
            for e in result['errors']:
                print(f"   ❌ {e}")
        if result['warnings']:
            for w in result['warnings']:
                print(f"   ⚠️  {w}")
        if result['corrected_values']:
            print(f"   🔧 修正值: {result['corrected_values']}")
        print(f"   decision: {result['decision']}, reason: {result['reason']}")
        print()
