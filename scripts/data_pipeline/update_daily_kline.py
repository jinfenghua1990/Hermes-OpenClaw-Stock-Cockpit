"""
Phase-2.3B Update Daily Kline
每日收盘后增量补充K线
逻辑：
- 读取每只股票本地最后 date
- 如果本地最后日期 < 最新交易日 → 补缺失K
- 如果等于 → 跳过
- 写入前按 code+date 去重
"""

import os, sys, json, time, logging, csv
from pathlib import Path
from datetime import datetime, date

DATA_HOME = Path("/Users/gino/project_ai_trading/data")
KLINE_DIR = DATA_HOME / "kline_daily"
LOG_DIR   = DATA_HOME / "update_logs"
KLINE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"update_kline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("update_kline")

FIELDS = ["code","date","open","high","low","close","volume","amount","turnover","source","adjust","update_time"]
END    = datetime.now().strftime("%Y%m%d")

def fetch_efinance(code, start):
    try:
        import efinance as ef
        df = ef.stock.get_quote_history(code, start=start, end=END, fq="前复权")
        if df is None or df.empty: return None
        df = df.rename(columns={
            "股票代码":"code","日期":"date","开盘":"open",
            "最高":"high","最低":"low","收盘":"close",
            "成交量":"volume","成交额":"amount","振幅":"turnover",
        })
        df["source"] = "efinance"; df["adjust"] = "qfq"
        df["update_time"] = datetime.now().isoformat()
        return df[["code","date","open","high","low","close","volume","amount","turnover","source","adjust","update_time"]]
    except: return None

def fetch_akshare(code, start):
    try:
        import akshare as ak
        sym = code.zfill(6)
        df = ak.stock_zh_a_hist(symbol=sym, period="daily",
                                  start_date=start.replace("-",""), end_date=END, adjust="qfq")
        if df is None or df.empty: return None
        df = df.rename(columns={
            "日期":"date","开盘":"open","最高":"high","最低":"low",
            "收盘":"close","成交量":"volume","成交额":"amount","涨跌幅":"turnover",
        })
        df["code"] = sym; df["source"] = "akshare"; df["adjust"] = "qfq"
        df["update_time"] = datetime.now().isoformat()
        return df[["code","date","open","high","low","close","volume","amount","turnover","source","adjust","update_time"]]
    except: return None

def fetch(code, start):
    df = fetch_efinance(code, start)
    if df is not None: return df, "efinance"
    df = fetch_akshare(code, start)
    if df is not None: return df, "akshare"
    return None, "none"

def read_last_date(code) -> str:
    path = KLINE_DIR / f"{code}.csv"
    if not path.exists(): return ""
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows[-1]["date"] if rows else ""

def write_update(code, df_new):
    path = KLINE_DIR / f"{code}.csv"
    rows = []
    if path.exists():
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    # 去重：date唯一，保留最新update_time
    seen = {r["date"]: r for r in rows}
    for _, r in df_new.iterrows():
        d = r["date"]
        if d not in seen or r["update_time"] > seen[d]["update_time"]:
            seen[d] = r.to_dict()
    out = sorted(seen.values(), key=lambda x: x["date"])
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(out)
    # 更新meta
    meta_path = KLINE_DIR / f"{code}.meta.json"
    meta = {}
    if meta_path.exists():
        with open(meta_path) as f: meta = json.load(f)
    meta["last_date"] = out[-1]["date"] if out else ""
    meta["first_date"] = out[0]["date"] if out else ""
    meta["rows"] = len(out)
    meta["last_update_time"] = datetime.now().isoformat()
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def run(trading_date=None):
    td = trading_date or date.today().strftime("%Y-%m-%d")
    files = list(KLINE_DIR.glob("*.csv"))
    total = len(files)
    success = fail = skip = 0
    failed = []
    t0 = time.time()

    log.info(f"=== 增量更新开始 === 日期:{td} 股票:{total}")

    for f in files:
        code = f.stem
        last_date = read_last_date(code)
        if last_date >= td[:10]:
            skip += 1; continue

        df, src = fetch(code, last_date)
        if df is not None and not df.empty:
            df_new = df[df["date"] > last_date]
            if not df_new.empty:
                write_update(code, df_new)
                success += 1
        else:
            fail += 1; failed.append(code)

    elapsed = time.time()-t0
    summary = {
        "update_time": datetime.now().isoformat(), "trading_date": td,
        "total": total, "success": success, "fail": fail, "skip": skip,
        "failed_codes": failed[:50], "elapsed_seconds": round(elapsed,1),
    }
    with open(LOG_DIR / f"update_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json","w",encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    log.info(f"=== 完成 === 成功:{success} 失败:{fail} 跳过:{skip} 耗时:{elapsed:.0f}s")
    return summary

if __name__ == "__main__":
    td = sys.argv[1] if len(sys.argv)>1 else None
    run(td)
