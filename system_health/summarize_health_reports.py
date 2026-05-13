#!/usr/bin/env python3
"""
健康报告汇总脚本 - 生成Phase-2.4B-Stable运行统计
"""

import json
import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
HEALTH_HISTORY_DIR = BASE_DIR / "system_health" / "history"

def update_index():
    """更新健康报告历史索引"""
    index_file = HEALTH_HISTORY_DIR / "index.json"
    
    if not index_file.exists():
        print("错误: 索引文件不存在")
        return
    
    with open(index_file, 'r', encoding='utf-8') as f:
        index = json.load(f)
    
    # 收集所有报告
    report_files = list(HEALTH_HISTORY_DIR.glob("*.json"))
    report_files = [f for f in report_files if f.name != "index.json"]
    
    reports = []
    for report_file in report_files:
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                report = json.load(f)
                reports.append({
                    "date": report.get("date"),
                    "status": report.get("overall_status"),
                    "file": report_file.name
                })
        except:
            continue
    
    # 按日期排序
    reports.sort(key=lambda x: x["date"], reverse=True)
    
    # 计算统计信息
    total_days = len(reports)
    status_counts = {
        "success": 0,
        "warning": 0,
        "error": 0
    }
    
    # 计算连续成功天数
    current_streak = 0
    longest_streak = 0
    temp_streak = 0
    
    emotion_scores = []
    factor_counts = []
    
    for report in sorted(reports, key=lambda x: x["date"]):
        status = report["status"]
        status_counts[status] += 1
        
        if status == "success":
            temp_streak += 1
            longest_streak = max(longest_streak, temp_streak)
        else:
            temp_streak = 0
        
        # 尝试读取详细报告获取指标
        try:
            report_file_path = HEALTH_HISTORY_DIR / report["file"]
            with open(report_file_path, 'r', encoding='utf-8') as f:
                detailed = json.load(f)
                emotion_score = detailed.get("critical_metrics", {}).get("emotion_score")
                factor_count = detailed.get("critical_metrics", {}).get("factor_valid_count")
                
                if emotion_score is not None:
                    emotion_scores.append(emotion_score)
                if factor_count is not None:
                    factor_counts.append(factor_count)
        except:
            pass
    
    current_streak = temp_streak
    
    # 计算平均值
    avg_emotion_score = sum(emotion_scores) / len(emotion_scores) if emotion_scores else 0
    avg_factor_count = sum(factor_counts) / len(factor_counts) if factor_counts else 0
    
    # 更新索引
    index["reports"] = reports
    index["summary"] = {
        "total_days": total_days,
        "successful_days": status_counts["success"],
        "warning_days": status_counts["warning"],
        "error_days": status_counts["error"],
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "average_emotion_score": round(avg_emotion_score, 2),
        "average_factor_count": round(avg_factor_count, 2)
    }
    index["last_updated"] = datetime.datetime.now().isoformat()
    
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    
    return index

def generate_stability_report():
    """生成稳定性报告"""
    index_file = HEALTH_HISTORY_DIR / "index.json"
    
    if not index_file.exists():
        print("错误: 索引文件不存在")
        return
    
    with open(index_file, 'r', encoding='utf-8') as f:
        index = json.load(f)
    
    summary = index["summary"]
    
    report = {
        "timestamp": datetime.datetime.now().isoformat(),
        "phase": "Phase-2.4B-Stable",
        "stability_analysis": {
            "total_days": summary["total_days"],
            "success_rate": round(summary["successful_days"] / summary["total_days"] * 100, 1) if summary["total_days"] > 0 else 0,
            "current_streak": summary["current_streak"],
            "longest_streak": summary["longest_streak"],
            "days_to_goal": max(14 - summary["current_streak"], 0)
        },
        "key_metrics": {
            "average_emotion_score": summary["average_emotion_score"],
            "average_factor_count": summary["average_factor_count"],
            "factor_count_meets_standard": summary["average_factor_count"] >= 4000
        },
        "phase_completion_criteria": {
            "continuous_success_days_14": summary["current_streak"] >= 14,
            "all_metrics_meet_standards": summary["average_factor_count"] >= 4000 and summary["average_emotion_score"] > -20,
            "no_major_warnings": summary["warning_days"] / summary["total_days"] < 0.2 if summary["total_days"] > 0 else True,
            "system_monitoring_stable": True  # 需要从实际检查中获取
        },
        "recommendation": {
            "can_proceed_to_next_phase": summary["current_streak"] >= 14 and summary["average_factor_count"] >= 4000,
            "next_phase_mode": "SOUL_INSIGHT_MODE",
            "recommended_actions": [
                "继续稳定运行直到达到30天" if summary["current_streak"] < 30 else "准备进入下一阶段评估",
                "确保所有关键指标持续达标",
                "保持禁止自动学习和AI自治"
            ]
        }
    }
    
    return report

def main():
    print("正在更新健康报告历史索引...")
    index = update_index()
    
    print("\n正在生成稳定性报告...")
    stability_report = generate_stability_report()
    
    print("\n" + "=" * 60)
    print("Phase-2.4B-Stable 稳定性报告")
    print("=" * 60)
    
    stability = stability_report["stability_analysis"]
    print(f"总运行天数: {stability['total_days']}")
    print(f"成功率: {stability['success_rate']}%")
    print(f"当前连续成功天数: {stability['current_streak']}")
    print(f"最长连续成功天数: {stability['longest_streak']}")
    print(f"距离目标还差: {stability['days_to_goal']}天")
    
    print("\n关键指标:")
    metrics = stability_report["key_metrics"]
    print(f"  平均情绪分数: {metrics['average_emotion_score']}")
    print(f"  平均因子数量: {metrics['average_factor_count']}")
    print(f"  因子数量达标: {'✅' if metrics['factor_count_meets_standard'] else '❌'}")
    
    print("\n阶段完成标准:")
    criteria = stability_report["phase_completion_criteria"]
    for key, value in criteria.items():
        emoji = "✅" if value else "❌"
        print(f"  {emoji} {key}: {value}")
    
    print("\n建议:")
    recommendation = stability_report["recommendation"]
    print(f"  可以进入下一阶段: {'✅' if recommendation['can_proceed_to_next_phase'] else '❌'}")
    print(f"  下一阶段模式: {recommendation['next_phase_mode']}")
    for action in recommendation["recommended_actions"]:
        print(f"  • {action}")
    
    # 保存稳定性报告
    report_file = BASE_DIR / "system_health" / f"stability_report_{datetime.datetime.now().strftime('%Y%m%d')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(stability_report, f, ensure_ascii=False, indent=2)
    
    print(f"\n稳定性报告已保存到: {report_file}")

if __name__ == "__main__":
    main()