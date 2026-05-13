#!/usr/bin/env python3
"""
沪深主板 K线补拉脚本
支持断点恢复、失败记录、限速
"""

import argparse
import json
import time
import sys
from pathlib import Path

# 添加项目根目录到 path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
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

# 配置
BATCH_SIZE = 50
BATCH_SLEEP = 3
MIN_ROWS = 200

KLINE_DIR = PROJECT_ROOT / "data" / "kline_daily"
BATCH_DIR = PROJECT_ROOT / "data_quality" / "missing_batches"
LOG_DIR = PROJECT_ROOT / "data_pipeline" / "logs"
FAILED_LOG = LOG_DIR / "failed_symbols.json"

KLINE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def load_batch(market: str) -> list:
    """加载指定市场的待拉取清单"""
    batch_file = BATCH_DIR / f"{market}.json"
    if not batch_file.exists():
        print(f"[ERROR] Batch file not found: {batch_file}")
        return []
    
    symbols = json.loads(batch_file.read_text(encoding="utf-8"))
    print(f"[INFO] Loaded {len(symbols)} symbols from {market}")
    return symbols


def load_failed() -> list:
    """加载已失败的 symbol"""
    if FAILED_LOG.exists():
        return json.loads(FAILED_LOG.read_text(encoding="utf-8"))
    return []


def save_failed(failed: list):
    """保存失败的 symbol"""
    FAILED_LOG.write_text(
        json.dumps(failed, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def get_existing_csv(symbol: str) -> Path:
    """获取已存在的 CSV 路径"""
    return KLINE_DIR / f"{symbol}.csv"


def fetch_via_akshare(symbol: str) -> dict:
    """通过 akshare 获取 K 线"""
    try:
        # 去掉后缀获取纯数字代码
        code = symbol.split(".")[0]
        
        # 判断市场
        if symbol.endswith(".SH"):
            code_sh = f"sh{code}"
            df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20200101", adjust="qfq")
        else:
            code_sz = f"sz{code}"
            df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20200101", adjust="qfq")
        
        if df is None or len(df) < MIN_ROWS:
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
        
        # 选择需要的列
        df = df[["date", "open", "high", "low", "close", "volume"]]
        
        return {"success": True, "data": df}
    except Exception as e:
        return {"success": False, "reason": str(e)}


def fetch_via_baostock(symbol: str) -> dict:
    """通过 baostock 获取 K 线"""
    try:
        import baostock as bs
        
        # 登录
        lg = bs.login()
        if lg.error_code != '0':
            return {"success": False, "reason": lg.error_msg}
        
        # 转换代码格式
        code = symbol.split(".")[0]
        if symbol.endswith(".SH"):
            bs_code = f"sh.{code}"
        else:
            bs_code = f"sz.{code}"
        
        # 获取数据
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close,volume",
            start_date="2020-01-01",
            frequency="d"
        )
        
        if rs.error_code != '0':
            bs.logout()
            return {"success": False, "reason": rs.error_msg}
        
        # 转换为 DataFrame
        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())
        
        bs.logout()
        
        if len(data_list) < MIN_ROWS:
            return {"success": False, "reason": "insufficient data"}
        
        import pandas as pd
        df = pd.DataFrame(data_list, columns=["date", "open", "high", "low", "close", "volume"])
        
        return {"success": True, "data": df}
    except Exception as e:
        return {"success": False, "reason": str(e)}


def fetch_kline(symbol: str) -> dict:
    """获取 K 线数据（多数据源 fallback）"""
    # 优先用 akshare
    if AKSHARE_AVAILABLE:
        result = fetch_via_akshare(symbol)
        if result["success"]:
            return result
    
    # fallback 用 baostock
    if BAOSTOCK_AVAILABLE:
        result = fetch_via_baostock(symbol)
        if result["success"]:
            return result
    
    return {"success": False, "reason": "no data source available"}


def save_csv(symbol: str, df) -> bool:
    """保存为 CSV"""
    try:
        csv_path = get_existing_csv(symbol)
        df.to_csv(csv_path, index=False, encoding="utf-8")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save {symbol}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="沪深主板 K线补拉")
    parser.add_argument("--market", required=True, choices=["sh_mainboard", "sz_mainboard", "gem", "star"])
    parser.add_argument("--limit", type=int, default=0, help="限制下载数量，0=全部")
    args = parser.parse_args()
    
    # 加载待拉取清单
    symbols = load_batch(args.market)
    if not symbols:
        print(f"[ERROR] No symbols to download for {args.market}")
        return
    
    # 限制数量
    if args.limit > 0:
        symbols = symbols[:args.limit]
        print(f"[INFO] Limited to {args.limit} symbols")
    
    # 加载已失败的
    failed_symbols = load_failed()
    
    # 统计
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for i, symbol in enumerate(symbols):
        # 检查是否已存在有效 CSV
        csv_path = get_existing_csv(symbol)
        if csv_path.exists():
            # 检查行数
            try:
                import pandas as pd
                df_existing = pd.read_csv(csv_path)
                if len(df_existing) >= MIN_ROWS:
                    print(f"[SKIP] {symbol} (already exists, {len(df_existing)} rows)")
                    skip_count += 1
                    continue
            except:
                pass
        
        # 下载
        print(f"[DOWN] {symbol} ({i+1}/{len(symbols)})")
        result = fetch_kline(symbol)
        
        if result["success"]:
            if save_csv(symbol, result["data"]):
                print(f"[OK] {symbol}")
                success_count += 1
            else:
                print(f"[FAIL] {symbol} (save error)")
                failed_symbols.append({"symbol": symbol, "market": args.market, "reason": "save error"})
                fail_count += 1
        else:
            print(f"[FAIL] {symbol} ({result['reason']})")
            failed_symbols.append({"symbol": symbol, "market": args.market, "reason": result["reason"]})
            fail_count += 1
        
        # 每 50 只 sleep 3 秒
        if (i + 1) % BATCH_SIZE == 0:
            print(f"[INFO] Processed {i+1}/{len(symbols)}, sleeping {BATCH_SLEEP}s...")
            time.sleep(BATCH_SLEEP)
    
    # 保存失败的
    save_failed(failed_symbols)
    
    # 总结
    print("\n" + "="*50)
    print(f"[DONE] {args.market}")
    print(f"  Success: {success_count}")
    print(f"  Skip:    {skip_count}")
    print(f"  Failed:  {fail_count}")
    print(f"  Total:   {len(symbols)}")
    print("="*50)


if __name__ == "__main__":
    main()
