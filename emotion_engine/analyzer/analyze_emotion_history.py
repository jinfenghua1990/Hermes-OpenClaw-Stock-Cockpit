#!/usr/bin/env python3
"""
Emotion History Analyzer
分析历史市场情绪变化，输出统计指标和趋势分析
原则：不做预测，不做AI学习，只做历史统计分析，所有结果必须可解释
"""

import json
import os
import glob
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

def load_emotion_history(history_dir: str = "emotion_engine/history") -> List[Dict[str, Any]]:
    """
    加载历史情绪快照数据
    """
    history_files = glob.glob(os.path.join(history_dir, "*.json"))
    history_data = []
    
    for file_path in history_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 从文件名提取日期
                date_str = Path(file_path).stem
                data["date"] = date_str
                history_data.append(data)
        except Exception as e:
            print(f"⚠️ 加载文件 {file_path} 失败: {e}")
    
    # 按日期排序
    history_data.sort(key=lambda x: x["date"])
    return history_data

def calculate_basic_statistics(history_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    计算基本统计指标
    """
    if not history_data:
        return {}
    
    emotion_scores = [item["emotion_analysis"]["emotion_score"] for item in history_data]
    dates = [item["date"] for item in history_data]
    
    # 平均情绪分数
    avg_score = sum(emotion_scores) / len(emotion_scores)
    
    # 最高/最低情绪分数及对应日期
    max_score = max(emotion_scores)
    min_score = min(emotion_scores)
    max_score_date = dates[emotion_scores.index(max_score)]
    min_score_date = dates[emotion_scores.index(min_score)]
    
    # 最常见的市场阶段
    market_phases = [item["emotion_analysis"]["market_phase"] for item in history_data]
    most_common_phase = max(set(market_phases), key=market_phases.count)
    
    # 最常见的风险等级
    risk_levels = [item["emotion_analysis"]["market_risk_level"] for item in history_data]
    most_common_risk = max(set(risk_levels), key=risk_levels.count)
    
    return {
        "average_emotion_score": round(avg_score, 2),
        "highest_emotion_day": {
            "date": max_score_date,
            "score": max_score,
            "market_phase": history_data[emotion_scores.index(max_score)]["emotion_analysis"]["market_phase"],
            "risk_level": history_data[emotion_scores.index(max_score)]["emotion_analysis"]["market_risk_level"]
        },
        "lowest_emotion_day": {
            "date": min_score_date,
            "score": min_score,
            "market_phase": history_data[emotion_scores.index(min_score)]["emotion_analysis"]["market_phase"],
            "risk_level": history_data[emotion_scores.index(min_score)]["emotion_analysis"]["market_risk_level"]
        },
        "most_common_market_phase": most_common_phase,
        "most_common_risk_level": most_common_risk,
        "total_days": len(history_data),
        "date_range": {
            "start": dates[0],
            "end": dates[-1]
        }
    }

def analyze_emotion_trend(history_data: List[Dict[str, Any]], window_days: int = 5) -> Dict[str, Any]:
    """
    分析情绪趋势（最近N日）
    """
    if len(history_data) < window_days:
        return {
            "trend": "insufficient_data",
            "message": f"数据不足 {len(history_data)} 天，需要至少 {window_days} 天分析趋势",
            "recent_scores": [item["emotion_analysis"]["emotion_score"] for item in history_data],
            "dates": [item["date"] for item in history_data]
        }
    
    # 取最近N天数据
    recent_data = history_data[-window_days:]
    recent_scores = [item["emotion_analysis"]["emotion_score"] for item in recent_data]
    recent_dates = [item["date"] for item in recent_data]
    
    # 计算趋势
    score_changes = [recent_scores[i] - recent_scores[i-1] for i in range(1, len(recent_scores))]
    
    # 判断趋势
    all_positive = all(change > 0 for change in score_changes)
    all_negative = all(change < 0 for change in score_changes)
    max_change = max(abs(change) for change in score_changes)
    
    if all_positive:
        trend = "rising"
        trend_strength = "strong" if max_change > 10 else "weak"
    elif all_negative:
        trend = "falling"
        trend_strength = "strong" if max_change > 10 else "weak"
    elif max_change <= 5:
        trend = "flat"
        trend_strength = "stable"
    else:
        trend = "volatile"
        trend_strength = "high_volatility"
    
    return {
        "trend": trend,
        "trend_strength": trend_strength,
        "window_days": window_days,
        "recent_scores": recent_scores,
        "recent_dates": recent_dates,
        "score_changes": score_changes,
        "average_change": round(sum(score_changes) / len(score_changes), 2) if score_changes else 0
    }

def analyze_mode_dominance_history(history_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    分析模式主导历史
    """
    mode_dominance = []
    
    for item in history_data:
        emotion_analysis = item["emotion_analysis"]
        market_metrics = item["market_metrics"]
        
        # 找出最强模式
        strongest_mode = emotion_analysis["strongest_mode"]
        mode_counts = {
            "mode1": market_metrics["mode1_count"],
            "mode2": market_metrics["mode2_count"],
            "mode3": market_metrics["mode3_count"],
            "mode4": market_metrics["mode4_count"]
        }
        
        mode_dominance.append({
            "date": item["date"],
            "strongest_mode": strongest_mode,
            "mode_counts": mode_counts,
            "emotion_score": emotion_analysis["emotion_score"],
            "market_phase": emotion_analysis["market_phase"]
        })
    
    # 统计各模式成为最强模式的次数
    mode_names = ["mode1", "mode2", "mode3", "mode4"]
    dominance_counts = {mode: 0 for mode in mode_names}
    
    for record in mode_dominance:
        dominance_counts[record["strongest_mode"]] += 1
    
    # 计算占比
    total_days = len(mode_dominance)
    dominance_percentages = {
        mode: round((count / total_days) * 100, 2) if total_days > 0 else 0
        for mode, count in dominance_counts.items()
    }
    
    # 找出最常主导的模式
    most_dominant_mode = max(dominance_counts, key=dominance_counts.get)
    
    return {
        "mode_dominance_history": mode_dominance,
        "dominance_summary": {
            "total_days": total_days,
            "dominance_counts": dominance_counts,
            "dominance_percentages": dominance_percentages,
            "most_dominant_mode": most_dominant_mode,
            "most_dominant_percentage": dominance_percentages[most_dominant_mode]
        }
    }

def generate_analysis_report(history_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    生成完整分析报告
    """
    # 基本统计
    basic_stats = calculate_basic_statistics(history_data)
    
    # 趋势分析
    trend_analysis = analyze_emotion_trend(history_data, window_days=5)
    
    # 模式主导历史分析
    mode_analysis = analyze_mode_dominance_history(history_data)
    
    # 构建完整报告
    report = {
        "analysis_date": datetime.now().strftime("%Y-%m-%d"),
        "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_source": {
            "history_dir": "emotion_engine/history",
            "files_count": len(history_data),
            "date_range": basic_stats.get("date_range", {})
        },
        "basic_statistics": basic_stats,
        "trend_analysis": trend_analysis,
        "mode_dominance_analysis": mode_analysis["dominance_summary"],
        "interpretation": {
            "average_emotion_score_explanation": "历史平均情绪分数，范围0-100，分数越高表示历史平均情绪越积极",
            "trend_explanation": "基于最近5日情绪分数变化判断趋势：rising=持续上升，falling=持续下降，flat=波动小于5，volatile=大幅波动",
            "market_phase_explanation": "最常见的市场阶段：breakout_phase=突破期，recovery_phase=复苏期，defensive_phase=防守期，trend_phase=趋势期",
            "risk_level_explanation": "最常见的风险等级：high=高风险，medium=中风险，low=低风险"
        }
    }
    
    return report

def save_analysis_report(report: Dict[str, Any], output_path: str = "emotion_engine/analyzer/emotion_history_analysis.json"):
    """
    保存分析报告
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 情绪历史分析报告已保存: {output_path}")
    return output_path

def print_human_readable_summary(report: Dict[str, Any]):
    """
    打印人类可读的摘要
    """
    print("\n" + "="*60)
    print("情绪历史分析摘要")
    print("="*60)
    
    basic = report["basic_statistics"]
    trend = report["trend_analysis"]
    mode = report["mode_dominance_analysis"]
    
    print(f"📅 分析日期: {report['analysis_date']}")
    print(f"📊 数据范围: {basic['date_range']['start']} 至 {basic['date_range']['end']} ({basic['total_days']} 天)")
    print()
    
    print("📈 情绪分数统计:")
    print(f"  • 平均情绪分数: {basic['average_emotion_score']}/100")
    print(f"  • 最高情绪日: {basic['highest_emotion_day']['date']} ({basic['highest_emotion_day']['score']}/100)")
    print(f"  • 最低情绪日: {basic['lowest_emotion_day']['date']} ({basic['lowest_emotion_day']['score']}/100)")
    print()
    
    print("🎭 市场阶段与风险:")
    print(f"  • 最常见市场阶段: {basic['most_common_market_phase']}")
    print(f"  • 最常见风险等级: {basic['most_common_risk_level']}")
    print()
    
    print("📉 趋势分析:")
    if trend["trend"] == "insufficient_data":
        print(f"  • {trend['message']}")
    else:
        print(f"  • 最近{trend['window_days']}日趋势: {trend['trend']} ({trend['trend_strength']})")
        print(f"  • 情绪分数变化: {' → '.join(map(str, trend['recent_scores']))}")
        print(f"  • 平均每日变化: {trend['average_change']}")
    print()
    
    print("🔢 模式主导历史:")
    print(f"  • 总分析天数: {mode['total_days']}")
    for mode_name, percentage in mode["dominance_percentages"].items():
        mode_display = {
            "mode1": "回踩止跌型",
            "mode2": "突破启动型", 
            "mode3": "小阳启动型",
            "mode4": "2波启动型"
        }
        print(f"  • {mode_display.get(mode_name, mode_name)}: {percentage}%")
    print(f"  • 最常主导模式: {mode['most_dominant_mode']} ({mode['most_dominant_percentage']}%)")
    print("="*60)

def main():
    """
    主函数
    """
    print("="*60)
    print("情绪历史分析器 - Phase-2.4B 扩展")
    print("="*60)
    print("原则：不做预测，不做AI学习，只做历史统计分析，所有结果必须可解释")
    print()
    
    # 1. 加载历史数据
    print("📂 加载历史情绪数据...")
    history_data = load_emotion_history()
    
    if not history_data:
        print("⚠️ 没有找到历史情绪数据，请先运行市场情绪快照系统")
        return
    
    print(f"✅ 加载了 {len(history_data)} 天的历史数据")
    print(f"📅 日期范围: {history_data[0]['date']} 至 {history_data[-1]['date']}")
    print()
    
    # 2. 生成分析报告
    print("📊 分析历史情绪变化...")
    report = generate_analysis_report(history_data)
    
    # 3. 保存报告
    output_path = save_analysis_report(report)
    
    # 4. 打印摘要
    print_human_readable_summary(report)
    
    # 5. 生成日报需要的趋势文本
    if report["trend_analysis"]["trend"] != "insufficient_data":
        recent_scores = report["trend_analysis"]["recent_scores"]
        trend = report["trend_analysis"]["trend"]
        
        print("\n📋 日报趋势文本:")
        print(f"最近{len(recent_scores)}日情绪: {' → '.join(map(str, recent_scores))}")
        print(f"当前趋势: {trend}")
    
    print("\n✅ 情绪历史分析完成!")

if __name__ == "__main__":
    main()