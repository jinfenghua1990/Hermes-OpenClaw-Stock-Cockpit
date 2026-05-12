#!/usr/bin/env python3
"""
使用 efinance 尝试获取缺失的股票数据
"""

import json
import time
import sys
from pathlib import Path

PROJECT_ROOT = Path.cwd().parent if Path.cwd().name == "scripts" else Path.cwd()
sys.path.append(str(PROJECT_ROOT))

KLINE_DIR = PROJECT_ROOT / "data" / "kline_daily"
LOG_DIR = PROJECT_ROOT / "data_pipeline" / "logs"
FAILED_LOG = LOG_DIR / "failed_symbols.json"
EFINANCE_LOG = LOG_DIR / "efinance_retry.json"

KLINE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def fetch_via_efinance(symbol: str):
    """通过 efinance 获取 K 线"""
    try:
        import efinance as ef
        code = symbol.split(".")[0]
        
        # efinance 需要市场前缀
        if symbol.endswith(".SH"):
            full_code = f"{code}.SH"
        else:
            full_code = f"{code}.SZ"
        
        df = ef.stock.get_quote_history(full_code, beg="20200101")
        
        if df is None or len(df) < 200:
            return {"success": False, "reason": "insufficient data"}
        
        # 重命名列
        df = df.rename(columns={
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume"
        })
        
        # 确保有需要的列
        required_cols = ["date", "open", "high", "low", "close", "volume"]
        for col in required_cols:
            if col not in df.columns:
                return {"success": False, "reason": f"missing column {col}"}
        
        df = df[required_cols]
        return {"success": True, "data": df}
    except ImportError:
        return {"success": False, "reason": "efinance not installed"}
    except Exception as e:
        return {"success": False, "reason": f"efinance error: {str(e)}"}


def save_csv(symbol: str, df) -> bool:
    """保存为 CSV"""
    try:
        csv_path = KLINE_DIR / f"{symbol}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save {symbol}: {e}")
        return False


def main():
    if not FAILED_LOG.exists():
        print("[ERROR] No failed symbols file found")
        return
    
    failed = json.loads(FAILED_LOG.read_text(encoding="utf-8"))
    print(f"[INFO] Found {len(failed)} still failed symbols")
    
    results = {
        "total": len(failed),
        "success": [],
        "still_failed": [],
        "start_time": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    success_count = 0
    
    for i, item in enumerate(failed):
        symbol = item["symbol"]
        market = item.get("market", "unknown")
        
        print(f"[EFINANCE] {symbol} ({i+1}/{len(failed)})")
        
        result = fetch_via_efinance(symbol)
        if result["success"]:
            if save_csv(symbol, result["data"]):
                print(f"[OK] {symbol} (via efinance)")
                success_count += 1
                results["success"].append({
                    "symbol": symbol,
                    "market": market,
                    "source": "efinance"
                })
                continue
        
        # 仍然失败
        print(f"[FAIL] {symbol} ({result['reason']})")
        results["still_failed"].append(item)
        
        # 每 10 只休息 1 秒
        if (i + 1) % 10 == 0:
            time.sleep(1)
    
    # 保存结果
    results["end_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    results["success_count"] = success_count
    results["still_failed_count"] = len(results["still_failed"])
    
    EFINANCE_LOG.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    # 更新失败列表
    if results["still_failed"]:
        FAILED_LOG.write_text(
            json.dumps(results["still_failed"], ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    else:
        FAILED_LOG.unlink()
    
    print("\n" + "="*50)
    print(f"[DONE] efinance retry completed")
    print(f"  Success: {success_count}/{len(failed)}")
    print(f"  Still failed: {len(results['still_failed'])}")
    print(f"  Results saved to: {EFINANCE_LOG}")
    print("="*50)


if __name__ == "__main__":
    main()
