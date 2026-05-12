#!/usr/bin/env python3
"""
重试失败的股票，优先使用 akshare
"""

import json
import time
import sys
from pathlib import Path

PROJECT_ROOT = Path.cwd().parent if Path.cwd().name == "scripts" else Path.cwd()
sys.path.append(str(PROJECT_ROOT))

from core.symbol_normalizer import normalize_symbol

# 尝试导入数据源
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False

try:
    import baostock as bs
    BAOSTOCK_AVAILABLE = True
except ImportError:
    BAOSTOCK_AVAILABLE = False

KLINE_DIR = PROJECT_ROOT / "data" / "kline_daily"
LOG_DIR = PROJECT_ROOT / "data_pipeline" / "logs"
FAILED_LOG = LOG_DIR / "failed_symbols.json"
RETRY_LOG = LOG_DIR / "retry_results.json"

KLINE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def fetch_via_akshare(symbol: str):
    """通过 akshare 获取 K 线"""
    try:
        code = symbol.split(".")[0]
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20200101", adjust="qfq")
        
        if df is None or len(df) < 200:
            return {"success": False, "reason": "insufficient data"}
        
        df = df.rename(columns={
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume"
        })
        df = df[["date", "open", "high", "low", "close", "volume"]]
        return {"success": True, "data": df}
    except Exception as e:
        return {"success": False, "reason": f"akshare error: {str(e)}"}


def fetch_via_baostock(symbol: str):
    """通过 baostock 获取 K 线"""
    try:
        lg = bs.login()
        if lg.error_code != '0':
            return {"success": False, "reason": lg.error_msg}
        
        code = symbol.split(".")[0]
        if symbol.endswith(".SH"):
            bs_code = f"sh.{code}"
        else:
            bs_code = f"sz.{code}"
        
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close,volume",
            start_date="2020-01-01",
            frequency="d"
        )
        
        if rs.error_code != '0':
            bs.logout()
            return {"success": False, "reason": rs.error_msg}
        
        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())
        
        bs.logout()
        
        if len(data_list) < 200:
            return {"success": False, "reason": "insufficient data"}
        
        import pandas as pd
        df = pd.DataFrame(data_list, columns=["date", "open", "high", "low", "close", "volume"])
        return {"success": True, "data": df}
    except Exception as e:
        return {"success": False, "reason": f"baostock error: {str(e)}"}


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
    print(f"[INFO] Found {len(failed)} failed symbols")
    
    retry_results = {
        "total": len(failed),
        "success": [],
        "still_failed": [],
        "start_time": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    success_count = 0
    
    for i, item in enumerate(failed):
        symbol = item["symbol"]
        market = item.get("market", "unknown")
        reason = item.get("reason", "unknown")
        
        print(f"[RETRY] {symbol} ({i+1}/{len(failed)}) - {reason}")
        
        # 优先用 akshare
        if AKSHARE_AVAILABLE:
            result = fetch_via_akshare(symbol)
            if result["success"]:
                if save_csv(symbol, result["data"]):
                    print(f"[OK] {symbol} (via akshare)")
                    success_count += 1
                    retry_results["success"].append({
                        "symbol": symbol,
                        "market": market,
                        "source": "akshare"
                    })
                    continue
        
        # 再用 baostock
        if BAOSTOCK_AVAILABLE:
            result = fetch_via_baostock(symbol)
            if result["success"]:
                if save_csv(symbol, result["data"]):
                    print(f"[OK] {symbol} (via baostock)")
                    success_count += 1
                    retry_results["success"].append({
                        "symbol": symbol,
                        "market": market,
                        "source": "baostock"
                    })
                    continue
        
        # 仍然失败
        print(f"[FAIL] {symbol} (both sources failed)")
        retry_results["still_failed"].append(item)
        
        # 每 20 只休息 2 秒
        if (i + 1) % 20 == 0:
            time.sleep(2)
    
    # 保存结果
    retry_results["end_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    retry_results["success_count"] = success_count
    retry_results["still_failed_count"] = len(retry_results["still_failed"])
    
    RETRY_LOG.write_text(
        json.dumps(retry_results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    # 更新失败列表（只保留仍然失败的）
    if retry_results["still_failed"]:
        FAILED_LOG.write_text(
            json.dumps(retry_results["still_failed"], ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    else:
        FAILED_LOG.unlink()
    
    print("\n" + "="*50)
    print(f"[DONE] Retry completed")
    print(f"  Success: {success_count}/{len(failed)}")
    print(f"  Still failed: {len(retry_results['still_failed'])}")
    print(f"  Results saved to: {RETRY_LOG}")
    print("="*50)


if __name__ == "__main__":
    main()
