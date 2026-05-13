import json
from pathlib import Path
from datetime import datetime
import pandas as pd

KLINE_DIR = Path("data/kline_daily")
CACHE_DIR = Path("features/cache")
LOG_DIR = Path("features/logs")

CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calc_ma20_trend(df):
    ma20 = df["close"].rolling(20).mean()
    if len(ma20.dropna()) < 5:
        return "flat"
    recent = ma20.dropna().tail(5)
    if recent.iloc[-1] > recent.iloc[0]:
        return "up"
    if recent.iloc[-1] < recent.iloc[0]:
        return "down"
    return "flat"

def valid_csv(df):
    if len(df) < 200:
        return False
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            return False
    return True

def build_factor_for_symbol(path: Path):
    df = pd.read_csv(path)
    if not valid_csv(df):
        raise ValueError("invalid csv")
    df = df.sort_values("date") if "date" in df.columns else df
    df = df.reset_index(drop=True)
    for col in REQUIRED_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=REQUIRED_COLUMNS)
    if len(df) < 200:
        raise ValueError("not enough valid rows")
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    close = float(latest["close"])
    open_ = float(latest["open"])
    high = float(latest["high"])
    low = float(latest["low"])
    volume = float(latest["volume"])
    prev_close = float(prev["close"])
    ma5 = float(df["close"].rolling(5).mean().iloc[-1])
    ma10 = float(df["close"].rolling(10).mean().iloc[-1])
    ma20 = float(df["close"].rolling(20).mean().iloc[-1])
    rsi14 = float(calc_rsi(df["close"], 14).iloc[-1])
    volume_ma5 = float(df["volume"].rolling(5).mean().iloc[-1])
    volume_ratio = volume / volume_ma5 if volume_ma5 > 0 else 0
    pct_chg = (close - prev_close) / prev_close * 100 if prev_close > 0 else 0
    upper_shadow_pct = (high - max(open_, close)) / close * 100 if close > 0 else 0
    lower_shadow_pct = (min(open_, close) - low) / close * 100 if close > 0 else 0
    distance_to_ma20_pct = (close - ma20) / ma20 * 100 if ma20 > 0 else 0
    return {
        "latest_close": round(close, 4),
        "latest_open": round(open_, 4),
        "latest_high": round(high, 4),
        "latest_low": round(low, 4),
        "latest_volume": round(volume, 2),
        "prev_close": round(prev_close, 4),
        "pct_chg": round(pct_chg, 2),
        "ma5": round(ma5, 4),
        "ma10": round(ma10, 4),
        "ma20": round(ma20, 4),
        "rsi14": round(rsi14, 2),
        "volume_ratio": round(volume_ratio, 2),
        "upper_shadow_pct": round(upper_shadow_pct, 2),
        "lower_shadow_pct": round(lower_shadow_pct, 2),
        "distance_to_ma20_pct": round(distance_to_ma20_pct, 2),
        "ma20_trend": calc_ma20_trend(df)
    }

def main():
    factors = {}
    invalid = []
    csv_files = sorted(KLINE_DIR.glob("*.csv"))
    for path in csv_files:
        symbol = path.stem
        try:
            factors[symbol] = build_factor_for_symbol(path)
            print(f"[OK] {symbol}")
        except Exception as e:
            invalid.append({
                "symbol": symbol,
                "reason": str(e)
            })
            print(f"[FAIL] {symbol}: {e}")
    result = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(csv_files),
        "valid": len(factors),
        "invalid": len(invalid),
        "factors": factors
    }
    output_path = CACHE_DIR / "daily_technical_factors.json"
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    invalid_path = LOG_DIR / "invalid_factor_symbols.json"
    invalid_path.write_text(
        json.dumps(invalid, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print("=" * 60)
    print(f"[DONE] total={result['total']} valid={result['valid']} invalid={result['invalid']}")
    print(f"[OUTPUT] {output_path}")
    print(f"[INVALID] {invalid_path}")

if __name__ == "__main__":
    main()