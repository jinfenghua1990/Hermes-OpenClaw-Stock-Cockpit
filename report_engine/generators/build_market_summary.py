import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def build_market_summary():
    today = datetime.now().strftime("%Y-%m-%d")
    
    summary = {
        "date": today,
        "northbound": "待接入北向资金数据，目前先占位。",
        "main_sector": "待接入板块强度数据，目前先占位。",
        "institution": "待接入龙虎榜/机构净买数据，目前先占位。",
        "emotion": "待接入 Emotion Layer 输出，目前先占位。",
        "tomorrow_focus": "待接入 Decision Layer 输出，目前先占位。"
    }
    
    output_path = DATA_DIR / "market_summary.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"[OK] market_summary generated: {output_path}")

if __name__ == "__main__":
    build_market_summary()
