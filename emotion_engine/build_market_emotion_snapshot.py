#!/usr/bin/env python3
"""
市场情绪快照系统 Phase-2.4B
建立市场情绪量化系统，不做AI自治，不修改baseline，不做强化学习
所有结果必须可解释
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Any, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
STRATEGIES_DIR = BASE_DIR / "strategies" / "outputs"
HISTORY_INDEX = BASE_DIR / "reports" / "history" / "index.json"
CACHE_DIR = BASE_DIR / "emotion_engine" / "cache"
HISTORY_DIR = BASE_DIR / "emotion_engine" / "history"
SNAPSHOT_CACHE = CACHE_DIR / "market_emotion_snapshot.json"


def load_four_modes_data(target_date: str = None) -> Dict[str, Any]:
    """
    加载四模式扫描数据
    如果未指定日期，使用最新日期
    """
    if target_date:
        # 使用指定日期
        file_pattern = f"original_four_modes_{target_date}.json"
    else:
        # 查找最新文件
        json_files = list(STRATEGIES_DIR.glob("original_four_modes_*.json"))
        if not json_files:
            raise FileNotFoundError("未找到四模式扫描数据文件")
        
        # 按日期排序取最新
        json_files.sort(key=lambda x: x.stem.split("_")[-1], reverse=True)
        file_pattern = json_files[0].name
    
    file_path = STRATEGIES_DIR / file_pattern
    if not file_path.exists():
        raise FileNotFoundError(f"四模式文件不存在: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise ValueError(f"无法加载四模式数据 {file_path}: {e}")


def load_history_index() -> Dict[str, Any]:
    """加载历史日报索引"""
    if not HISTORY_INDEX.exists():
        raise FileNotFoundError(f"历史索引文件不存在 {HISTORY_INDEX}")
    
    try:
        with open(HISTORY_INDEX, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise ValueError(f"无法加载索引文件: {e}")


def calculate_mode_counts(four_modes_data: Dict[str, Any]) -> Dict[str, int]:
    """
    计算四模式数量
    返回: {mode1: count, mode2: count, mode3: count, mode4: count}
    """
    # 从statistics字段获取统计数据
    statistics = four_modes_data.get("statistics", {})
    
    # 从列表长度获取各模式数量
    return {
        "mode1": len(four_modes_data.get("mode_1_revert", [])),
        "mode2": len(four_modes_data.get("mode_2_breakout", [])),
        "mode3": len(four_modes_data.get("mode_3_xiaoyang", [])),
        "mode4": len(four_modes_data.get("mode_4_second_wave", []))
    }


def determine_strongest_weakest_mode(mode_counts: Dict[str, int]) -> Tuple[str, str]:
    """
    确定最强和最弱模式
    规则：数量最多为最强，数量最少为最弱（排除0的情况）
    """
    # 过滤掉数量为0的模式
    valid_modes = {mode: count for mode, count in mode_counts.items() if count > 0}
    
    if not valid_modes:
        return "unknown", "unknown"
    
    # 最强模式：数量最大
    strongest = max(valid_modes.items(), key=lambda x: x[1])[0]
    
    # 最弱模式：数量最小（但大于0）
    weakest = min(valid_modes.items(), key=lambda x: x[1])[0]
    
    return strongest, weakest


def calculate_emotion_score(mode_counts: Dict[str, int]) -> int:
    """
    计算情绪分数 (0~100)
    规则：
    - mode2 高：+40
    - mode3 高：+25
    - mode4 高：+20
    - mode1 高：+10
    - 基础分数：20
    """
    base_score = 20
    
    # 获取总数用于计算相对比例
    total = sum(mode_counts.values())
    if total == 0:
        return 0
    
    # 计算各模式占比
    mode1_ratio = mode_counts["mode1"] / total
    mode2_ratio = mode_counts["mode2"] / total
    mode3_ratio = mode_counts["mode3"] / total
    mode4_ratio = mode_counts["mode4"] / total
    
    # 根据规则计算分数
    score = base_score
    score += mode2_ratio * 40  # mode2 高：+40
    score += mode3_ratio * 25  # mode3 高：+25
    score += mode4_ratio * 20  # mode4 高：+20
    score += mode1_ratio * 10  # mode1 高：+10
    
    # 确保分数在0-100之间
    score = max(0, min(100, int(score)))
    
    return score


def determine_market_phase(mode_counts: Dict[str, int], strongest_mode: str) -> str:
    """
    确定市场阶段
    规则：
    - mode2 dominant → breakout_phase
    - mode3 dominant → recovery_phase
    - mode1 dominant → defensive_phase
    - mode4 dominant → trend_phase
    """
    total = sum(mode_counts.values())
    if total == 0:
        return "unknown"
    
    # 计算各模式占比
    mode2_ratio = mode_counts["mode2"] / total
    mode3_ratio = mode_counts["mode3"] / total
    mode1_ratio = mode_counts["mode1"] / total
    mode4_ratio = mode_counts["mode4"] / total
    
    # 根据规则判断
    if strongest_mode == "mode2" and mode2_ratio > 0.3:
        return "breakout_phase"
    elif strongest_mode == "mode3" and mode3_ratio > 0.3:
        return "recovery_phase"
    elif strongest_mode == "mode1" and mode1_ratio > 0.3:
        return "defensive_phase"
    elif strongest_mode == "mode4" and mode4_ratio > 0.3:
        return "trend_phase"
    else:
        # 如果没有明显的主导模式
        if mode2_ratio > 0.2:
            return "breakout_phase"
        elif mode3_ratio > 0.25:
            return "recovery_phase"
        elif mode4_ratio > 0.25:
            return "trend_phase"
        elif mode1_ratio > 0.3:
            return "defensive_phase"
        else:
            return "consolidation_phase"


def determine_market_risk_level(mode_counts: Dict[str, int]) -> str:
    """
    确定市场风险等级
    规则：
    - mode2 = 0 → high
    - mode3 dominant → medium
    - mode2 + mode4 high → low
    """
    total = sum(mode_counts.values())
    if total == 0:
        return "unknown"
    
    # 规则1: mode2 = 0 → high
    if mode_counts["mode2"] == 0:
        return "high"
    
    # 计算各模式占比
    mode2_ratio = mode_counts["mode2"] / total
    mode3_ratio = mode_counts["mode3"] / total
    mode4_ratio = mode_counts["mode4"] / total
    
    # 规则2: mode3 dominant → medium
    if mode3_ratio > 0.4:
        return "medium"
    
    # 规则3: mode2 + mode4 high → low
    if (mode2_ratio + mode4_ratio) > 0.5:
        return "low"
    
    # 默认情况
    if mode_counts["mode1"] > mode_counts["mode3"]:
        return "medium_high"
    else:
        return "medium"


def build_market_emotion_snapshot(target_date: str = None) -> Dict[str, Any]:
    """
    构建市场情绪快照
    """
    print(f"构建市场情绪快照...")
    
    # 1. 加载数据
    four_modes_data = load_four_modes_data(target_date)
    history_index = load_history_index()
    
    # 从文件名提取日期
    if target_date:
        snapshot_date = target_date
    else:
        # 从最新文件名提取日期
        json_files = list(STRATEGIES_DIR.glob("original_four_modes_*.json"))
        json_files.sort(key=lambda x: x.stem.split("_")[-1], reverse=True)
        latest_file = json_files[0]
        snapshot_date = latest_file.stem.split("_")[-1]
    
    # 2. 计算模式数量
    mode_counts = calculate_mode_counts(four_modes_data)
    
    # 3. 确定最强最弱模式
    strongest_mode, weakest_mode = determine_strongest_weakest_mode(mode_counts)
    
    # 4. 计算情绪分数
    emotion_score = calculate_emotion_score(mode_counts)
    
    # 5. 确定市场阶段
    market_phase = determine_market_phase(mode_counts, strongest_mode)
    
    # 6. 确定风险等级
    market_risk_level = determine_market_risk_level(mode_counts)
    
# 从statistics字段获取统计数据
    statistics = four_modes_data.get("statistics", {})
    
    # 7. 构建快照
    snapshot = {
        "snapshot_date": snapshot_date,
        "generated_at": datetime.now().isoformat(),
        "emotion_engine_version": "2.4B",
        "data_source": {
            "four_modes_file": f"original_four_modes_{snapshot_date}.json",
            "history_index": "reports/history/index.json"
        },
        "market_metrics": {
            "mode1_count": mode_counts["mode1"],
            "mode2_count": mode_counts["mode2"],
            "mode3_count": mode_counts["mode3"],
            "mode4_count": mode_counts["mode4"],
            "total_candidates": statistics.get("any_mode_count", 0),
            "total_symbols": statistics.get("total_symbols", 0)
        },
        "emotion_analysis": {
            "strongest_mode": strongest_mode,
            "weakest_mode": weakest_mode,
            "emotion_score": emotion_score,
            "market_phase": market_phase,
            "market_risk_level": market_risk_level
        },
        "interpretation": {
            "emotion_score_explanation": "情绪分数 (0-100): 基于四模式分布计算，分数越高表示市场情绪越积极",
            "market_phase_explanation": f"市场阶段: {market_phase}",
            "risk_level_explanation": f"风险等级: {market_risk_level}"
        }
    }
    
    return snapshot


def save_snapshot_to_cache(snapshot: Dict[str, Any]):
    """保存快照到缓存"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(SNAPSHOT_CACHE, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        print(f"快照缓存已保存: {SNAPSHOT_CACHE}")
    except Exception as e:
        print(f"警告: 无法保存缓存 {e}")


def save_snapshot_to_history(snapshot: Dict[str, Any]):
    """保存快照到历史目录"""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    
    date_str = snapshot["snapshot_date"]
    history_file = HISTORY_DIR / f"{date_str}.json"
    
    try:
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        print(f"历史快照已保存: {history_file}")
    except Exception as e:
        print(f"警告: 无法保存历史快照 {e}")


def print_human_readable(snapshot: Dict[str, Any]):
    """打印人类可读的输出"""
    metrics = snapshot["market_metrics"]
    analysis = snapshot["emotion_analysis"]
    
    print("\n" + "="*60)
    print("市场情绪快照系统 Phase-2.4B")
    print("="*60)
    
    print(f"📅 快照日期: {snapshot['snapshot_date']}")
    print(f"🕒 生成时间: {snapshot['generated_at']}")
    
    print("\n📊 四模式统计:")
    print(f"  • 回踩止跌型 (M1): {metrics['mode1_count']} 只")
    print(f"  • 突破启动型 (M2): {metrics['mode2_count']} 只")
    print(f"  • 小阳启动型 (M3): {metrics['mode3_count']} 只")
    print(f"  • 2波启动型 (M4): {metrics['mode4_count']} 只")
    print(f"  • 候选总数: {metrics['total_candidates']} / {metrics['total_symbols']}")
    
    print("\n🎭 情绪分析:")
    print(f"  • 最强模式: {analysis['strongest_mode']}")
    print(f"  • 最弱模式: {analysis['weakest_mode']}")
    print(f"  • 情绪分数: {analysis['emotion_score']}/100")
    print(f"  • 市场阶段: {analysis['market_phase']}")
    print(f"  • 风险等级: {analysis['market_risk_level']}")
    
    print("\n📝 解释说明:")
    print(f"  • {snapshot['interpretation']['emotion_score_explanation']}")
    print(f"  • {snapshot['interpretation']['market_phase_explanation']}")
    print(f"  • {snapshot['interpretation']['risk_level_explanation']}")
    
    print("="*60)


def main():
    """主函数"""
    try:
        # 解析命令行参数
        target_date = None
        if len(sys.argv) > 1:
            target_date = sys.argv[1]
            print(f"使用指定日期: {target_date}")
        
        # 构建市场情绪快照
        snapshot = build_market_emotion_snapshot(target_date)
        
        # 保存到缓存
        save_snapshot_to_cache(snapshot)
        
        # 保存到历史
        save_snapshot_to_history(snapshot)
        
        # 打印结果
        print_human_readable(snapshot)
        
        # 返回成功
        return 0
        
    except FileNotFoundError as e:
        print(f"错误: {e}")
        return 1
    except Exception as e:
        print(f"未知错误: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())