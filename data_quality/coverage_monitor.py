import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).resolve().parents[1]))
from core.symbol_normalizer import normalize_symbol

KLINE_DIR = Path("data/kline_daily")
OUTPUT_DIR = Path("data_quality")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]


def check_csv_valid(path: Path) -> bool:
    try:
        import pandas as pd
        df = pd.read_csv(path)
        if len(df) < 200:
            return False
        for col in REQUIRED_COLUMNS:
            if col not in df.columns:
                return False
        return True
    except Exception:
        return False


def run_coverage_monitor(stock_pool_path="data/stock_pool.json"):
    stock_pool_file = Path(stock_pool_path)
    if not stock_pool_file.exists():
        raise FileNotFoundError(f"stock pool not found: {stock_pool_file}")
    
    with open(stock_pool_file, "r", encoding="utf-8") as f:
        stock_pool = json.load(f)
    
    total = len(stock_pool)
    valid = 0
    missing = []
    invalid = []
    
    for item in stock_pool:
        raw_symbol = item.get("symbol") or item.get("code")
        if not raw_symbol:
            continue
        symbol = normalize_symbol(str(raw_symbol).zfill(6))
        csv_path = KLINE_DIR / f"{symbol}.csv"
        if not csv_path.exists():
            # 尝试不带后缀的格式
            csv_path = KLINE_DIR / f"{symbol.split('.')[0]}.csv"
            if not csv_path.exists():
                missing.append(symbol)
                continue
        if check_csv_valid(csv_path):
            valid += 1
        else:
            invalid.append(symbol)
    
    coverage = round(valid / total * 100, 2) if total else 0
    
    result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": total,
        "valid": valid,
        "missing": len(missing),
        "invalid": len(invalid),
        "coverage": coverage,
        "missing_symbols": missing,
        "invalid_symbols": invalid[:500]
    }
    
    output_path = OUTPUT_DIR / "coverage_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    run_coverage_monitor()
