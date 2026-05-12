import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = BASE_DIR / "templates" / "daily_report_template.md"
SUMMARY_PATH = BASE_DIR / "data" / "market_summary.json"
EMOTION_SNAPSHOT_PATH = BASE_DIR.parent / "emotion_engine" / "cache" / "market_emotion_snapshot.json"
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
    
    # 合并情绪数据
    summary.update(emotion_data)
    
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
        "风险等级"
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