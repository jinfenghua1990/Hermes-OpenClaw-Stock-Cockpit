import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = BASE_DIR / "templates" / "daily_report_template.md"
SUMMARY_PATH = BASE_DIR / "data" / "market_summary.json"
EMOTION_SNAPSHOT_PATH = BASE_DIR.parent / "emotion_engine" / "cache" / "market_emotion_snapshot.json"
EMOTION_ANALYSIS_PATH = BASE_DIR.parent / "emotion_engine" / "analyzer" / "emotion_history_analysis.json"
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_emotion_snapshot() -> dict:
    """加载市场情绪快照数据"""
    if not EMOTION_SNAPSHOT_PATH.exists():
        print(f"[WARN] 情绪快照文件不存在: {EMOTION_SNAPSHOT_PATH}")
        return {}
    
    try:
        with open(EMOTION_SNAPSHOT_PATH, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
        
        # 提取情绪分析数据
        emotion_data = snapshot.get("emotion_analysis", {})
        metrics = snapshot.get("market_metrics", {})
        interpretation = snapshot.get("interpretation", {})
        
        # 构建情绪快照文本
        emotion_score = emotion_data.get("emotion_score", 0)
        market_phase = emotion_data.get("market_phase", "unknown")
        market_risk_level = emotion_data.get("market_risk_level", "unknown")
        strongest_mode = emotion_data.get("strongest_mode", "unknown")
        weakest_mode = emotion_data.get("weakest_mode", "unknown")
        
        # 情绪分数解释
        if emotion_score >= 80:
            emotion_interpretation = "市场情绪非常积极，多头氛围浓厚"
        elif emotion_score >= 60:
            emotion_interpretation = "市场情绪积极，多头占优"
        elif emotion_score >= 40:
            emotion_interpretation = "市场情绪中性，多空平衡"
        elif emotion_score >= 20:
            emotion_interpretation = "市场情绪谨慎，空头压力显现"
        else:
            emotion_interpretation = "市场情绪悲观，空头主导"
        
        # 市场阶段解释
        phase_map = {
            "breakout_phase": "突破阶段 - 市场处于突破行情，动量较强",
            "recovery_phase": "复苏阶段 - 市场正在从调整中恢复",
            "defensive_phase": "防御阶段 - 市场偏向防御，风险偏好降低",
            "trend_phase": "趋势阶段 - 市场处于趋势性行情",
            "consolidation_phase": "震荡阶段 - 市场处于区间震荡",
            "unknown": "未知阶段 - 数据不足无法判断"
        }
        phase_interpretation = phase_map.get(market_phase, "未知阶段")
        
        # 风险等级解释
        risk_map = {
            "low": "低风险 - 市场风险较低，适合积极操作",
            "medium": "中等风险 - 市场风险适中，需控制仓位",
            "medium_high": "中高风险 - 市场风险较高，需谨慎操作",
            "high": "高风险 - 市场风险很高，建议观望",
            "unknown": "未知风险 - 数据不足无法判断"
        }
        risk_interpretation = risk_map.get(market_risk_level, "未知风险")
        
        # 模式强度映射
        mode_map = {
            "mode1": "回踩止跌型",
            "mode2": "突破启动型", 
            "mode3": "小阳启动型",
            "mode4": "2波启动型",
            "unknown": "未知模式"
        }
        strongest_mode_cn = mode_map.get(strongest_mode, "未知模式")
        weakest_mode_cn = mode_map.get(weakest_mode, "未知模式")
        
        return {
            "emotion_snapshot": f"基于四模式扫描和市场情绪快照系统的量化分析",
            "emotion_score": emotion_score,
            "emotion_interpretation": emotion_interpretation,
            "market_phase": market_phase,
            "phase_interpretation": phase_interpretation,
            "market_risk_level": market_risk_level,
            "risk_interpretation": risk_interpretation,
            "strongest_mode": strongest_mode_cn,
            "weakest_mode": weakest_mode_cn,
            "snapshot_explanation": f"情绪分数基于四模式分布计算：突破启动型权重最高（+40），小阳启动型次之（+25），2波启动型（+20），回踩止跌型（+10）。市场阶段和风险等级根据模式分布和主导模式确定。"
        }
        
    except Exception as e:
        print(f"[ERROR] 加载情绪快照失败: {e}")
        return {}


def load_emotion_history_analysis() -> dict:
    """加载情绪历史分析数据"""
    if not EMOTION_ANALYSIS_PATH.exists():
        print(f"[WARN] 情绪历史分析文件不存在: {EMOTION_ANALYSIS_PATH}")
        return {
            "emotion_history_trend": "暂无历史趋势数据，请先运行情绪历史分析器",
            "recent_scores_chart": "数据不足",
            "trend_direction": "unknown",
            "trend_explanation": "数据不足，无法判断趋势",
            "history_statistics": "数据不足",
            "trend_interpretation": "请先运行情绪历史分析器以获取历史趋势数据"
        }
    
    try:
        with open(EMOTION_ANALYSIS_PATH, "r", encoding="utf-8") as f:
            analysis = json.load(f)
        
        basic = analysis.get("basic_statistics", {})
        trend = analysis.get("trend_analysis", {})
        mode_analysis = analysis.get("mode_dominance_analysis", {})
        
        # 构建趋势图表文本
        if trend.get("trend") == "insufficient_data":
            recent_scores_chart = "数据不足，无法显示图表"
            trend_direction = "unknown"
            trend_explanation = "数据不足，无法判断趋势"
        else:
            recent_scores = trend.get("recent_scores", [])
            recent_dates = trend.get("recent_dates", [])
            
            # 创建图表
            chart_lines = []
            for date, score in zip(recent_dates, recent_scores):
                # 简化为月-日格式
                date_display = date[-5:] if len(date) >= 5 else date
                bar_length = max(1, int(score / 2))  # 每2分显示1个字符
                bar = "█" * bar_length
                chart_lines.append(f"{date_display}: {bar} {score}")
            
            recent_scores_chart = "\n".join(chart_lines)
            
            # 趋势方向映射
            trend_map = {
                "rising": "上升",
                "falling": "下降", 
                "flat": "平缓",
                "volatile": "波动"
            }
            trend_direction = trend_map.get(trend.get("trend", "unknown"), "未知")
            
            # 趋势解释
            strength = trend.get("trend_strength", "")
            strength_map = {
                "strong": "强烈",
                "weak": "微弱",
                "stable": "稳定",
                "high_volatility": "高波动"
            }
            strength_cn = strength_map.get(strength, "")
            
            trend_explanation = f"趋势{trend_direction}{'（' + strength_cn + '）' if strength_cn else ''}"
        
        # 历史统计文本
        history_stats = []
        history_stats.append(f"• 历史平均情绪分数: {basic.get('average_emotion_score', 0)}/100")
        history_stats.append(f"• 最高情绪日: {basic.get('highest_emotion_day', {}).get('date', '未知')} ({basic.get('highest_emotion_day', {}).get('score', 0)}/100)")
        history_stats.append(f"• 最低情绪日: {basic.get('lowest_emotion_day', {}).get('date', '未知')} ({basic.get('lowest_emotion_day', {}).get('score', 0)}/100)")
        history_stats.append(f"• 最常见市场阶段: {basic.get('most_common_market_phase', 'unknown')}")
        history_stats.append(f"• 最常见风险等级: {basic.get('most_common_risk_level', 'unknown')}")
        
        # 模式主导历史
        mode_display = {
            "mode1": "回踩止跌型",
            "mode2": "突破启动型",
            "mode3": "小阳启动型", 
            "mode4": "2波启动型"
        }
        
        most_dominant_mode = mode_analysis.get("most_dominant_mode", "unknown")
        most_dominant_percentage = mode_analysis.get("most_dominant_percentage", 0)
        
        mode_stats = []
        for mode_name, percentage in mode_analysis.get("dominance_percentages", {}).items():
            mode_cn = mode_display.get(mode_name, mode_name)
            mode_stats.append(f"  - {mode_cn}: {percentage}%")
        
        history_stats.append(f"• 模式主导历史（{mode_display.get(most_dominant_mode, most_dominant_mode)} 主导 {most_dominant_percentage}% 天数）:")
        history_stats.extend(mode_stats)
        
        history_statistics = "\n".join(history_stats)
        
        # 趋势解读
        if trend.get("trend") == "rising":
            trend_interpretation = "情绪分数持续上升，表明市场情绪正在改善，投资者信心增强。"
        elif trend.get("trend") == "falling":
            trend_interpretation = "情绪分数持续下降，表明市场情绪正在恶化，投资者趋于谨慎。"
        elif trend.get("trend") == "flat":
            trend_interpretation = "情绪分数波动较小，市场情绪稳定，无明显趋势变化。"
        elif trend.get("trend") == "volatile":
            trend_interpretation = "情绪分数大幅波动，市场情绪不稳定，短期方向不明。"
        else:
            trend_interpretation = "基于历史情绪数据，市场情绪缺乏明确趋势方向。"
        
        # 添加数据不足时的额外解释
        if basic.get("total_days", 0) < 5:
            trend_interpretation += "（注：历史数据较少，趋势判断仅供参考）"
        
        return {
            "emotion_history_trend": "基于历史情绪快照数据的统计分析",
            "recent_scores_chart": recent_scores_chart,
            "trend_direction": trend_direction,
            "trend_explanation": trend_explanation,
            "history_statistics": history_statistics,
            "trend_interpretation": trend_interpretation
        }
        
    except Exception as e:
        print(f"[ERROR] 加载情绪历史分析失败: {e}")
        return {
            "emotion_history_trend": "加载历史趋势数据时出错",
            "recent_scores_chart": f"错误: {str(e)}",
            "trend_direction": "error",
            "trend_explanation": "数据加载失败",
            "history_statistics": "数据加载失败",
            "trend_interpretation": "请检查情绪历史分析器运行状态"
        }


def load_runtime_event_summary() -> dict:
    """加载 Runtime Event 汇总数据"""
    try:
        sys.path.insert(0, str(BASE_DIR.parent))
        from runtime_events.runtime_event_logger import summarize_events
        summary = summarize_events()
        
        # 构建最近事件文本
        latest_lines = []
        for evt in summary.get("latest_events", []):
            status_icon = "✅" if evt["status"] == "success" else "⚠️" if evt["status"] == "warning" else "❌"
            latest_lines.append(
                f"- {status_icon} [{evt.get('timestamp','')[:16]}] {evt.get('module','')} ({evt.get('layer','')}): {evt.get('message','')}"
            )
        latest_text = "\n".join(latest_lines) if latest_lines else "暂无事件记录"
        
        return {
            "runtime_total_modules": summary["total_modules"],
            "runtime_active_modules": summary["active_modules"],
            "runtime_exec_active": summary["layers"]["execution_layer"]["active"],
            "runtime_gov_active": summary["layers"]["governance_layer"]["active"],
            "runtime_cockpit_active": summary["layers"]["cockpit_layer"]["active"],
            "runtime_latest_events_text": latest_text,
        }
    except Exception as e:
        print(f"[WARN] 加载 Runtime Event 汇总失败: {e}")
        return {
            "runtime_total_modules": 17,
            "runtime_active_modules": 0,
            "runtime_exec_active": 0,
            "runtime_gov_active": 0,
            "runtime_cockpit_active": 0,
            "runtime_latest_events_text": f"加载失败: {e}",
        }


def load_runtime_event_health() -> dict:
    """加载 Runtime Event Health 数据"""
    try:
        sys.path.insert(0, str(BASE_DIR.parent / "system_health"))
        from runtime_event_health_check import check_runtime_event_health
        reh = check_runtime_event_health()
        return {
            "rehealth_active_today": reh["active_today"],
            "rehealth_total_modules": reh["total_modules"],
            "rehealth_missing_today": ", ".join(reh["missing_today"]) if reh["missing_today"] else "无",
            "rehealth_warning_modules": ", ".join(reh["warning_modules"]) if reh["warning_modules"] else "无",
            "rehealth_error_modules": ", ".join(reh["error_modules"]) if reh["error_modules"] else "无",
            "rehealth_status": reh["status"],
        }
    except Exception as e:
        print(f"[WARN] 加载 Runtime Event Health 失败: {e}")
        return {
            "rehealth_active_today": 0,
            "rehealth_total_modules": 17,
            "rehealth_missing_today": "检查失败",
            "rehealth_warning_modules": "检查失败",
            "rehealth_error_modules": "检查失败",
            "rehealth_status": "error",
        }


def generate_daily_report():
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")
    
    if not SUMMARY_PATH.exists():
        raise FileNotFoundError(f"Market summary not found: {SUMMARY_PATH}")
    
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    
    with open(SUMMARY_PATH, "r", encoding="utf-8") as f:
        summary = json.load(f)
    
    # 加载情绪快照数据
    emotion_data = load_emotion_snapshot()
    
    # 加载情绪历史分析数据
    history_data = load_emotion_history_analysis()
    
    # 添加时间戳
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary["timestamp"] = timestamp
    
    # 处理策略摘要（嵌套字典）
    if "strategy_summary" in summary:
        strategy = summary["strategy_summary"]
        # 将策略摘要的字段直接添加到替换字典中（使用简单名称）
        summary["mode_1_count"] = strategy.get("mode_1_count", 0)
        summary["mode_2_count"] = strategy.get("mode_2_count", 0)
        summary["mode_3_count"] = strategy.get("mode_3_count", 0)
        summary["mode_4_count"] = strategy.get("mode_4_count", 0)
        summary["any_mode_count"] = strategy.get("any_mode_count", 0)
        summary["total_symbols"] = strategy.get("total_symbols", 0)
        summary["hot_mode"] = strategy.get("hot_mode", "未知")
        summary["risk_note"] = strategy.get("risk_note", "")
        
        # 将策略摘要转为可显示的字符串（用于原始占位符）
        summary["strategy_summary"] = json.dumps(strategy, ensure_ascii=False, indent=2)
    
    # 合并情绪数据和历史分析数据
    summary.update(emotion_data)
    summary.update(history_data)
    
    # 加载 Runtime Event 汇总
    runtime_data = load_runtime_event_summary()
    summary.update(runtime_data)
    
    # 加载 Runtime Event Health
    rehealth_data = load_runtime_event_health()
    summary.update(rehealth_data)
    
    report = template
    for key, value in summary.items():
        placeholder = "{{" + key + "}}"
        if placeholder in template:
            report = report.replace(placeholder, str(value))
    
    date = summary.get("date", "unknown_date")
    output_path = OUTPUT_DIR / f"{date}.md"
    output_path.write_text(report, encoding="utf-8")
    
    print(f"[OK] daily report generated: {output_path}")
    
    # 验证关键内容是否存在
    required_keywords = [
        "回踩止跌型",
        "突破启动型",
        "小阳启动型",
        "2波启动型",
        "候选总数",
        "热门模式",
        "风险提示",
        "市场情绪快照",
        "情绪分数",
        "市场阶段",
        "风险等级",
        "情绪历史趋势",
        "Runtime Event Summary"
    ]
    report_text = output_path.read_text(encoding="utf-8")
    missing = []
    for keyword in required_keywords:
        if keyword not in report_text:
            missing.append(keyword)
    
    if missing:
        print(f"[WARN] 日报中缺少以下关键词: {missing}")
    else:
        print("[PASS] 日报包含所有必需内容")


if __name__ == "__main__":
    generate_daily_report()