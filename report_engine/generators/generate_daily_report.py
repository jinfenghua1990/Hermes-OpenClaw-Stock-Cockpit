import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = BASE_DIR / "templates" / "daily_report_template.md"
SUMMARY_PATH = BASE_DIR / "data" / "market_summary.json"
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_daily_report():
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")
    
    if not SUMMARY_PATH.exists():
        raise FileNotFoundError(f"Market summary not found: {SUMMARY_PATH}")
    
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    
    with open(SUMMARY_PATH, "r", encoding="utf-8") as f:
        summary = json.load(f)
    
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
        "风险提示"
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