import json
from pathlib import Path

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
    
    report = template
    for key, value in summary.items():
        report = report.replace("{{" + key + "}}", str(value))
    
    date = summary.get("date", "unknown_date")
    output_path = OUTPUT_DIR / f"{date}.md"
    output_path.write_text(report, encoding="utf-8")
    
    print(f"[OK] daily report generated: {output_path}")

if __name__ == "__main__":
    generate_daily_report()
