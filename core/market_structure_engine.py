#!/usr/bin/env python3
"""
Phase-2.7A Market Structure Engine
根据真实 K 线结构生成 support_price / pressure_price / structure_type / structure_confidence。
不再使用 MA20 简化推导（ma20 * 0.99 / ma20 * 1.05）。
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE = Path(__file__).parent.parent.resolve()

def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except:
        return default or {}

def find_swing_low(prices: list, window: int = 15) -> Optional[float]:
    """找最近 window 日内最低价（局部低点）。"""
    if len(prices) < 3:
        return None
    sub = prices[-window:]
    min_price = min(sub)
    min_idx_in_sub = sub.index(min_price)
    # 首日不算（除非最低点在子窗口中间位置）
    if min_idx_in_sub == 0 and len(sub) >= 5:
        # 检查次低点
        sub_without_first = sub[1:]
        if sub_without_first:
            second_min = min(sub_without_first)
            min_price = second_min
    return min_price

def find_swing_high(prices: list, window: int = 20) -> Optional[float]:
    """找最近 window 日内最高价（局部高点）。"""
    if len(prices) < 3:
        return None
    sub = prices[-window:]
    max_price = max(sub)
    max_idx_in_sub = sub.index(max_price)
    if max_idx_in_sub == 0:
        # 首日不算，检查次高点
        sub_without_first = sub[1:]
        if sub_without_first:
            second_max = max(sub_without_first)
            max_price = second_max
    return max_price

def detect_consolidation(prices: list, window: int = 15) -> Optional[tuple]:
    """检测横盘区间，返回 (low, high)。"""
    if len(prices) < window:
        return None
    sub = prices[-window:]
    avg = sum(sub) / len(sub)
    if max(sub) / min(sub) < 1.10:  # 10% 以内算横盘
        return min(sub), max(sub)
    return None

def detect_trend(prices: list, ma5: list, ma20: list) -> str:
    """判断趋势方向。"""
    if len(prices) < 5 or len(ma5) < 5 or len(ma20) < 5:
        return "unknown"
    p5 = ma5[-1]
    p20 = ma20[-1]
    p = prices[-1]
    if p > p5 > p20:
        return "uptrend"
    elif p < p5 < p20:
        return "downtrend"
    return "neutral"

def build_market_structure(symbol: str, kline_data: list = None, indicators: dict = None) -> dict:
    """
    根据真实 K 线生成市场结构。

    Args:
        symbol: 股票代码
        kline_data: K 线数据列表，每个元素 {open, high, low, close, volume, date}
        indicators: 技术指标 {ma5, ma10, ma20, close, data_as_of}

    Returns:
        {
            symbol, support_price, pressure_price, swing_low, swing_high,
            structure_type, structure_confidence, data_as_of,
            source, version
        }
    """
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # 默认兜底
    result = {
        "symbol": symbol,
        "support_price": 0.0,
        "pressure_price": 0.0,
        "swing_low": 0.0,
        "swing_high": 0.0,
        "structure_type": "invalid",
        "structure_confidence": 0.0,
        "data_as_of": now,
        "source": "market_structure_engine",
        "version": "phase_2_7a",
        "structure_source": "invalid",
        "structure_version": "2.7a",
    }

    # 如果没有 K 线数据，尝试加载
    if kline_data is None:
        kline_data = load_kline_data(symbol)

    if indicators is None:
        indicators = load_indicators(symbol)

    if not indicators or "close" not in indicators or not indicators["close"]:
        result["structure_type"] = "fallback_ma20"
        result["structure_confidence"] = 0.2
        result["source"] = "market_structure_engine_fallback"
        return result

    close_prices = indicators.get("close", [])
    ma5 = indicators.get("ma5", [])
    ma10 = indicators.get("ma10", [])
    ma20 = indicators.get("ma20", [])
    current_price = close_prices[-1] if close_prices else 0.0
    data_as_of = indicators.get("data_as_of", now)

    result["data_as_of"] = data_as_of

    if current_price <= 0:
        return result

    # ── 从 K 线提取 swing low / high（排除今日未完成K线）─────────
    if kline_data and len(kline_data) >= 5:
        lows = [k["low"] for k in kline_data]
        highs = [k["high"] for k in kline_data]

        # 找 swing low: 用全部数据
        swing_low = find_swing_low(lows)
        # 找 swing high: 排除最后一根K线（当日未完成，可能被突破）
        swing_high = find_swing_high(highs[:-1]) if len(highs) > 1 else None
        # 同时计算包含今日的版本（用于 breakout 判断）
        swing_high_today = find_swing_high(highs)
    else:
        swing_low = None
        swing_high = None
        swing_high_today = None

    # ── 结构类型判定 ────────────────────────────────────────────
    consolidation = detect_consolidation(close_prices) if close_prices else None
    trend = detect_trend(close_prices, ma5, ma20) if (close_prices and ma5 and ma20) else "unknown"

    ma20_val = ma20[-1] if ma20 else current_price
    ma5_val = ma5[-1] if ma5 else current_price

    # 初始计算
    support_price = 0.0
    pressure_price = 0.0
    confidence = 0.0
    structure_type = "invalid"
    structure_source = "invalid"

    # ── 结构类型判定（互斥，只进一个分支）────────────────────────────
    structure_type = "invalid"
    confidence = 0.0

    # ① 已突破前高 → breakout（优先判断）
    breakout = (
        (swing_high and current_price > swing_high) or
        (swing_high_today and current_price > swing_high_today)
    )
    if breakout:
        support_price = round(swing_low if swing_low else current_price * 0.93, 2)
        pressure_price = round(current_price * 1.10, 2)
        structure_type = "breakout"
        confidence = 0.60

    # ② swing_low ≥ current_price → invalid
    elif swing_low and swing_low >= current_price:
        support_price = round(current_price * 0.93, 2)
        pressure_price = round(current_price * 1.10, 2)
        structure_type = "invalid"
        confidence = 0.0

    # ③ 横盘结构
    elif consolidation:
        support_price = round(consolidation[0], 2)
        pressure_price = round(consolidation[1], 2)
        structure_type = "consolidation"
        confidence = 0.70

    # ④ 趋势延伸（价格在 MA5/MA10 上行）
    elif trend == "uptrend" and ma5_val > ma20_val:
        support_price = round(min(close_prices[-5:]) if len(close_prices) >= 5 else current_price * 0.95, 2)
        pressure_price = round(current_price * 1.10, 2)
        structure_type = "trend_extension"
        confidence = 0.55

    # ⑤ 正常回踩（价格在 MA20 上方，有清晰支撑）
    elif swing_low and swing_low < current_price:
        support_price = round(swing_low, 2)
        if swing_high and swing_high > current_price:
            pressure_price = round(swing_high, 2)
            structure_type = "pullback"
            confidence = 0.75
        else:
            pressure_price = round(current_price * 1.10, 2)
            structure_type = "consolidation"
            confidence = 0.60

    # ⑥ fallback MA20（数据不足）
    else:
        # Phase-2.7A: 无真实K线，MA20 推导的支撑无效
        # 判断：MA20 高于现价 → invalid（价格已跌破均线，无支撑）
        if ma20_val >= current_price:
            support_price = round(current_price * 0.93, 2)
            pressure_price = round(current_price * 1.10, 2)
            structure_type = "invalid"
            confidence = 0.0
        else:
            support_price = round(ma20_val * 0.97, 2)
            pressure_price = round(ma20_val * 1.03, 2)
            structure_type = "fallback_ma20"
            confidence = 0.30

    # ── 校验并修正 support/pressure ──────────────────────────────────
    # 如果之前判定了 invalid，在最后统一修正值
    if structure_type == "invalid":
        support_price = round(current_price * 0.93, 2)
        pressure_price = round(current_price * 1.10, 2)

    result.update({
        "support_price": support_price,
        "pressure_price": pressure_price,
        "swing_low": round(swing_low, 2) if swing_low else 0.0,
        "swing_high": round(swing_high, 2) if swing_high else 0.0,
        "structure_type": structure_type,
        "structure_confidence": round(confidence, 2),
        "data_as_of": data_as_of,
        "source": "market_structure_engine",
        "structure_source": structure_source or structure_type,
        "structure_version": "2.7a",
    })
    return result


def _score_confidence(base: float, swing_low, swing_high,
                      support_price, pressure_price, current_price,
                      data_as_of: str, indicator_data_as_of: str,
                      kline_data) -> float:
    """简单置信度评分。"""
    score = base
    # swing_low 清晰 +0.25
    if swing_low and swing_low < current_price:
        score = max(score, min(0.25 + score * 0.5, 0.90))
    # swing_high 清晰 +0.25
    if swing_high:
        score += 0.15
    # support <= current_price +0.20
    if support_price > 0 and support_price <= current_price:
        score += 0.20
    else:
        score -= 0.20
    # pressure > current_price +0.20
    if pressure_price > current_price:
        score += 0.20
    else:
        score -= 0.20
    # data_as_of 一致 +0.10
    if data_as_of and indicator_data_as_of and data_as_of == indicator_data_as_of:
        score += 0.10
    return min(1.0, max(0.0, score))


def load_kline_data(symbol: str) -> list:
    """从 mx_data_output/ 加载 K 线数据。"""
    import glob
    today = datetime.now().strftime("%Y-%m-%d")
    patterns = [
        BASE / "mx_data_output" / f"*{symbol}*raw.json",
        BASE / "mx_data_output" / f"*{symbol}*.json",
    ]
    for pat in patterns:
        files = glob.glob(str(pat))
        if files:
            data = load_json(files[0])
            if isinstance(data, dict) and "klines" in data:
                return data["klines"]
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "data" in data:
                return data["data"]
    return []


def load_indicators(symbol: str) -> dict:
    """加载技术指标。"""
    import glob
    today = datetime.now().strftime("%Y-%m-%d")
    patterns = [
        BASE / "features" / "cache" / f"*{symbol}*technical*factors*.json",
        BASE / "features" / "cache" / f"*{symbol}*.json",
    ]
    for pat in patterns:
        files = glob.glob(str(pat))
        if files:
            data = load_json(files[0])
            if isinstance(data, dict) and "ma20" in data:
                return data
            if isinstance(data, dict) and "ma5" in data:
                return data
    # 尝试从 daily_features.json 找
    df = load_json(BASE / "features" / "cache" / "daily_features.json")
    if isinstance(df, dict) and symbol in df:
        item = df[symbol]
        item["data_as_of"] = item.get("timestamp", df.get("timestamp", ""))
        return item
    return {}


# ══ Phase-2.7A 验收测试套件 ══════════════════════════════════════════════════
def test_suite():
    """
    Case 1: 正常回踩结构
    current_price=30.75, swing_low=29.80, swing_high=33.50
    → support=29.80, pressure=33.50, pullback/consolidation, confidence>0.7, risk_pass

    Case 2: 已突破前高
    current_price=23.50, swing_high=19.08
    → structure=breakout, pressure≈25.85, risk_pass

    Case 3: 错误结构
    support=36.53 > current_price=30.75
    → invalid, confidence=0, paper_skip

    Case 4: fallback MA20
    无足够K线数据
    → fallback_ma20, confidence<=0.45
    """
    print("=" * 60)
    print("Phase-2.7A Market Structure Engine — 验收测试")
    print("=" * 60)

    from unittest.mock import MagicMock

    # ── Case 1 ────────────────────────────────────────────────
    print("\n【Case 1】正常回踩结构")
    mock_kline = [
        {"date": "2026-05-06", "open": 32.0, "high": 33.5, "low": 29.8, "close": 30.2, "volume": 1000000},
        {"date": "2026-05-07", "open": 30.2, "high": 32.0, "low": 29.9, "close": 30.5, "volume": 900000},
        {"date": "2026-05-08", "open": 30.5, "high": 31.5, "low": 29.7, "close": 30.0, "volume": 1100000},
        {"date": "2026-05-09", "open": 30.0, "high": 31.0, "low": 29.8, "close": 30.3, "volume": 950000},
        {"date": "2026-05-12", "open": 30.3, "high": 32.0, "low": 29.8, "close": 30.75, "volume": 1200000},
        {"date": "2026-05-13", "open": 30.75, "high": 33.5, "low": 30.5, "close": 30.75, "volume": 1000000},
    ]
    mock_ind = {
        "close": [30.2, 30.5, 30.0, 30.3, 30.75, 30.75],
        "ma5": [30.3, 30.4, 30.3, 30.4, 30.52, 30.68],
        "ma10": [30.5, 30.4, 30.4, 30.4, 30.50, 30.55],
        "ma20": [31.0, 30.9, 30.9, 30.9, 30.90, 30.90],
        "data_as_of": "2026-05-13 17:01:17",
    }
    r = build_market_structure("TEST001", mock_kline, mock_ind)
    print(f"  support={r['support_price']} | pressure={r['pressure_price']}")
    print(f"  swing_low={r['swing_low']} | swing_high={r['swing_high']}")
    print(f"  type={r['structure_type']} | confidence={r['structure_confidence']}")
    ok1 = (r["support_price"] <= 30.75 and r["pressure_price"] > 30.75
           and r["structure_type"] in ("pullback", "consolidation", "breakout")
           and r["structure_confidence"] > 0.5)
    print(f"  ✅ PASS" if ok1 else f"  ❌ FAIL")

    # ── Case 2 ────────────────────────────────────────────────
    print("\n【Case 2】已突破前高")
    mock_kline2 = [
        {"date": "2026-05-06", "open": 18.0, "high": 19.0, "low": 17.5, "close": 18.5, "volume": 800000},
        {"date": "2026-05-07", "open": 18.5, "high": 19.1, "low": 18.2, "close": 19.0, "volume": 850000},
        {"date": "2026-05-08", "open": 19.0, "high": 20.0, "low": 18.8, "close": 19.5, "volume": 900000},
        {"date": "2026-05-09", "open": 19.5, "high": 21.0, "low": 19.2, "close": 20.8, "volume": 950000},
        {"date": "2026-05-12", "open": 20.8, "high": 22.5, "low": 20.5, "close": 22.0, "volume": 1000000},
        {"date": "2026-05-13", "open": 22.0, "high": 24.0, "low": 21.8, "close": 23.50, "volume": 1100000},
    ]
    mock_ind2 = {
        "close": [19.0, 19.5, 20.8, 22.0, 23.50],
        "ma5": [19.0, 19.8, 20.5, 21.3, 22.20],
        "ma10": [18.8, 19.2, 19.8, 20.4, 21.10],
        "ma20": [19.5, 19.6, 19.8, 20.0, 20.20],
        "data_as_of": "2026-05-13 17:01:17",
    }
    r2 = build_market_structure("TEST002", mock_kline2, mock_ind2)
    print(f"  support={r2['support_price']} | pressure={r2['pressure_price']}")
    print(f"  swing_high={r2['swing_high']} | current=23.50")
    print(f"  type={r2['structure_type']} | confidence={r2['structure_confidence']}")
    ok2 = (r2["structure_type"] == "breakout"
           and r2["pressure_price"] > 23.50
           and r2["pressure_price"] >= 23.50 * 1.08)
    print(f"  ✅ PASS" if ok2 else f"  ❌ FAIL")

    # ── Case 3 ────────────────────────────────────────────────
    print("\n【Case 3】错误结构（support > current_price）")
    mock_ind3 = {
        "close": [30.0, 30.2, 30.4, 30.5, 30.75],
        "ma5": [30.0, 30.1, 30.2, 30.3, 30.42],
        "ma10": [30.2, 30.2, 30.2, 30.3, 30.34],
        "ma20": [36.52, 36.52, 36.52, 36.52, 36.52],  # 远高于 current_price
        "data_as_of": "2026-05-13 17:01:17",
    }
    r3 = build_market_structure("TEST003", None, mock_ind3)
    print(f"  support={r3['support_price']} (should < 30.75)")
    print(f"  type={r3['structure_type']} | confidence={r3['structure_confidence']}")
    ok3 = (r3["structure_type"] == "invalid"
           and r3["structure_confidence"] == 0.0
           and r3["support_price"] <= 30.75)
    print(f"  ✅ PASS" if ok3 else f"  ❌ FAIL")

    # ── Case 4 ────────────────────────────────────────────────
    print("\n【Case 4】fallback MA20（数据不足）")
    mock_ind4 = {
        "close": [],
        "ma5": [],
        "ma10": [],
        "ma20": [31.0],
        "data_as_of": "2026-05-13 17:01:17",
    }
    r4 = build_market_structure("TEST004", None, mock_ind4)
    print(f"  type={r4['structure_type']} | confidence={r4['structure_confidence']}")
    ok4 = (r4["structure_type"] == "fallback_ma20"
           and r4["structure_confidence"] <= 0.45)
    print(f"  ✅ PASS" if ok4 else f"  ❌ FAIL")

    print("\n" + "=" * 60)
    passed = sum([ok1, ok2, ok3, ok4])
    print(f"测试结果: {passed}/4 通过")
    print("=" * 60)
    return passed == 4


if __name__ == "__main__":
    import sys
    ok = test_suite()
    sys.exit(0 if ok else 1)
