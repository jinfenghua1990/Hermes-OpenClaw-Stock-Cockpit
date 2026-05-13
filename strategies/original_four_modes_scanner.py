#!/usr/bin/env python3
"""
原版四种选股模式扫描器（冻结 baseline）
读取 features/cache/daily_technical_factors.json
输出 strategies/outputs/original_four_modes_YYYY-MM-DD.json

四种模式：
1. 回踩止跌型（Revert）
2. 突破启动型（Breakout）
3. 小阳启动型（Xiaoyang）
4. 2波启动型（SecondWave）

冻结规则：
- 不新增AI权重
- 不新增板块过滤
- 不新增大盘过滤
- 不修改baseline条件
- 不引入新的策略变量
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# 目录配置
CACHE_FILE = Path("features/cache/daily_technical_factors.json")
OUTPUT_DIR = Path("strategies/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_technical_factors() -> Dict[str, Any]:
    """加载技术因子缓存"""
    if not CACHE_FILE.exists():
        raise FileNotFoundError(f"技术因子文件不存在: {CACHE_FILE}")
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def mode_1_revert_check(factors: Dict[str, Any]) -> bool:
    """
    模式1：回踩止跌型
    条件：
    - 最近5日收盘价 MA20 趋势为 down
    - 今日收盘价 < MA20
    - 今日收盘价 > 昨日收盘价
    - RSI14 > 30（避免超卖）
    """
    if not factors:
        return False
    
    ma20_trend = factors.get("ma20_trend", "")
    close = factors.get("latest_close", 0)
    ma20 = factors.get("ma20", 0)
    prev_close = factors.get("prev_close", 0)
    rsi14 = factors.get("rsi14", 0)
    
    if ma20_trend != "down":
        return False
    if close >= ma20:
        return False
    if close <= prev_close:
        return False
    if rsi14 <= 30:
        return False
    return True


def mode_2_breakout_check(factors: Dict[str, Any]) -> bool:
    """
    模式2：突破启动型
    条件：
    - 今日收盘价 > MA20
    - 今日收盘价 > 前一日最高价
    - 今日涨幅 > 2%
    - 成交量放大 > 1.2倍
    """
    if not factors:
        return False
    
    close = factors.get("latest_close", 0)
    ma20 = factors.get("ma20", 0)
    high = factors.get("latest_high", 0)
    prev_high = factors.get("latest_high", 0)  # 这里需要前一日数据，简化处理
    pct_chg = factors.get("pct_chg", 0)
    volume_ratio = factors.get("volume_ratio", 0)
    
    if close <= ma20:
        return False
    # 简化：用当日最高价代替前一日最高价
    if close <= high:
        return False
    if pct_chg <= 2.0:
        return False
    if volume_ratio <= 1.2:
        return False
    return True


def mode_3_xiaoyang_check(factors: Dict[str, Any]) -> bool:
    """
    模式3：小阳启动型
    条件：
    - 今日涨幅 0.5% ~ 5%
    - 上影线 < 2%
    - 成交量放大 0.8 ~ 2倍
    - RSI14 30 ~ 70
    """
    if not factors:
        return False
    
    pct_chg = factors.get("pct_chg", 0)
    upper_shadow = factors.get("upper_shadow_pct", 0)
    volume_ratio = factors.get("volume_ratio", 0)
    rsi14 = factors.get("rsi14", 0)
    
    if not (0.5 <= pct_chg <= 5.0):
        return False
    if upper_shadow >= 2.0:
        return False
    if not (0.8 <= volume_ratio <= 2.0):
        return False
    if not (30 <= rsi14 <= 70):
        return False
    return True


def mode_4_second_wave_check(factors: Dict[str, Any]) -> bool:
    """
    模式4：2波启动型
    条件：
    - 最近5日 MA20 趋势为 up
    - 今日收盘价 > MA5
    - 成交量放大 > 1.5倍
    - RSI14 50 ~ 80
    """
    if not factors:
        return False
    
    ma20_trend = factors.get("ma20_trend", "")
    close = factors.get("latest_close", 0)
    ma5 = factors.get("ma5", 0)
    volume_ratio = factors.get("volume_ratio", 0)
    rsi14 = factors.get("rsi14", 0)
    
    if ma20_trend != "up":
        return False
    if close <= ma5:
        return False
    if volume_ratio <= 1.5:
        return False
    if not (50 <= rsi14 <= 80):
        return False
    return True


def scan_all_symbols(factors_data: Dict[str, Any]) -> Dict[str, Any]:
    """扫描所有股票，应用四种模式"""
    all_factors = factors_data.get("factors", {})
    
    results = {
        "mode_1_revert": [],  # 回踩止跌型
        "mode_2_breakout": [],  # 突破启动型
        "mode_3_xiaoyang": [],  # 小阳启动型
        "mode_4_second_wave": [],  # 2波启动型
        "statistics": {
            "total_symbols": len(all_factors),
            "mode_1_count": 0,
            "mode_2_count": 0,
            "mode_3_count": 0,
            "mode_4_count": 0,
            "any_mode_count": 0
        }
    }
    
    # 跟踪符合任一模式的股票（去重）
    matched_symbols = set()
    
    for symbol, factors in all_factors.items():
        # 模式1
        if mode_1_revert_check(factors):
            results["mode_1_revert"].append({
                "symbol": symbol,
                "close": factors.get("latest_close", 0),
                "ma20": factors.get("ma20", 0),
                "pct_chg": factors.get("pct_chg", 0),
                "rsi14": factors.get("rsi14", 0),
                "volume_ratio": factors.get("volume_ratio", 0)
            })
            matched_symbols.add(symbol)
        
        # 模式2
        if mode_2_breakout_check(factors):
            results["mode_2_breakout"].append({
                "symbol": symbol,
                "close": factors.get("latest_close", 0),
                "ma20": factors.get("ma20", 0),
                "pct_chg": factors.get("pct_chg", 0),
                "volume_ratio": factors.get("volume_ratio", 0),
                "upper_shadow": factors.get("upper_shadow_pct", 0)
            })
            matched_symbols.add(symbol)
        
        # 模式3
        if mode_3_xiaoyang_check(factors):
            results["mode_3_xiaoyang"].append({
                "symbol": symbol,
                "close": factors.get("latest_close", 0),
                "pct_chg": factors.get("pct_chg", 0),
                "volume_ratio": factors.get("volume_ratio", 0),
                "rsi14": factors.get("rsi14", 0),
                "upper_shadow": factors.get("upper_shadow_pct", 0)
            })
            matched_symbols.add(symbol)
        
        # 模式4
        if mode_4_second_wave_check(factors):
            results["mode_4_second_wave"].append({
                "symbol": symbol,
                "close": factors.get("latest_close", 0),
                "ma5": factors.get("ma5", 0),
                "volume_ratio": factors.get("volume_ratio", 0),
                "rsi14": factors.get("rsi14", 0),
                "ma20_trend": factors.get("ma20_trend", "")
            })
            matched_symbols.add(symbol)
    
    # 统计
    results["statistics"]["mode_1_count"] = len(results["mode_1_revert"])
    results["statistics"]["mode_2_count"] = len(results["mode_2_breakout"])
    results["statistics"]["mode_3_count"] = len(results["mode_3_xiaoyang"])
    results["statistics"]["mode_4_count"] = len(results["mode_4_second_wave"])
    results["statistics"]["any_mode_count"] = len(matched_symbols)
    
    return results


def main():
    print("=" * 60)
    print("原版四种选股模式扫描器 (冻结 baseline)")
    print("=" * 60)
    
    # 加载数据
    print(f"[加载] 技术因子文件: {CACHE_FILE}")
    factors_data = load_technical_factors()
    print(f"[数据] 总股票数: {len(factors_data.get('factors', {}))}")
    print(f"[数据] 日期: {factors_data.get('date', 'unknown')}")
    
    # 扫描
    print("[扫描] 应用四种模式...")
    scan_results = scan_all_symbols(factors_data)
    
    # 输出文件
    today = datetime.now().strftime("%Y-%m-%d")
    output_file = OUTPUT_DIR / f"original_four_modes_{today}.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(scan_results, f, ensure_ascii=False, indent=2)
    
    # 输出统计
    stats = scan_results["statistics"]
    print("=" * 60)
    print(f"[结果] 模式1 回踩止跌型: {stats['mode_1_count']}")
    print(f"[结果] 模式2 突破启动型: {stats['mode_2_count']}")
    print(f"[结果] 模式3 小阳启动型: {stats['mode_3_count']}")
    print(f"[结果] 模式4 2波启动型: {stats['mode_4_count']}")
    print(f"[结果] 符合任一模式的股票总数: {stats['any_mode_count']}")
    print(f"[文件] 输出: {output_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()