"""
Phase-2.3B Init Kline Daily
首次全量初始化：拉取4000+A股历史日K（2018-至今）
"""

import os, sys, json, time, logging, csv
from pathlib import Path
from datetime import datetime

# ── 路径 ──────────────────────────────────────────────────────────────────
DATA_HOME = Path("/Users/gino/project_ai_trading/data")
KLINE_DIR  = DATA_HOME / "kline_daily"
LOG_DIR    = DATA_HOME / "update_logs"
KLINE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"init_kline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("init_kline")

FIELDS = ["code","date","open","high","low","close","volume","amount","turnover","source","adjust","update_time"]
START  = "20180101"
END    = datetime.now().strftime("%Y%m%d")

# ── 数据源 ────────────────────────────────────────────────────────────────
def fetch_efinance(code):
    try:
        import efinance as ef
        df = ef.stock.get_quote_history(code, start=START, end=END, fq="前复权")
        if df is None or df.empty: return None
        df = df.rename(columns={
            "股票代码":"code","日期":"date","开盘":"open",
            "最高":"high","最低":"low","收盘":"close",
            "成交量":"volume","成交额":"amount","振幅":"turnover",
        })
        df["source"] = "efinance"; df["adjust"] = "qfq"
        df["update_time"] = datetime.now().isoformat()
        return df[["code","date","open","high","low","close","volume","amount","turnover","source","adjust","update_time"]]
    except Exception as e:
        log.debug(f"  ef失败 {code}: {e}"); return None

def fetch_akshare(code):
    try:
        import akshare as ak
        sym = code.zfill(6)
        df = ak.stock_zh_a_hist(symbol=sym, period="daily",
                                  start_date=START, end_date=END, adjust="qfq")
        if df is None or df.empty: return None
        df = df.rename(columns={
            "日期":"date","开盘":"open","最高":"high","最低":"low",
            "收盘":"close","成交量":"volume","成交额":"amount","涨跌幅":"turnover",
        })
        df["code"] = sym; df["source"] = "akshare"; df["adjust"] = "qfq"
        df["update_time"] = datetime.now().isoformat()
        return df[["code","date","open","high","low","close","volume","amount","turnover","source","adjust","update_time"]]
    except Exception as e:
        log.debug(f"  aks失败 {code}: {e}"); return None

def fetch_stock(code):
    df = fetch_efinance(code)
    if df is not None: return df, "efinance"
    df = fetch_akshare(code)
    if df is not None: return df, "akshare"
    return None, "none"

# ── 股票列表 ──────────────────────────────────────────────────────────────
def get_stock_list():
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        return [(str(r["code"]).zfill(6), r.get("name","")) for _, r in df.iterrows()
                if str(r["code"]).isdigit()]
    except Exception as e:
        log.error(f"获取列表失败: {e}"); return []

# ── 写CSV ─────────────────────────────────────────────────────────────────
def write_csv(code, df):
    path = KLINE_DIR / f"{code}.csv"
    if df is None or df.empty: return
    # 去重
    df = df.drop_duplicates(subset=["date"], keep="last")
    df = df.sort_values("date")
    # 过滤明显异常
    df = df[df["close"] > 0]
    df = df[df["high"] >= df[["open","close"]].max(axis=1)]
    df = df[df["low"]  <= df[["open","close"]].min(axis=1)]
    df.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")

def write_meta(code, name, source, rows):
    path = KLINE_DIR / f"{code}.meta.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "code": code, "name": name, "adjust": "qfq", "source": source,
            "first_date": "", "last_date": "",
            "last_update_time": datetime.now().isoformat(),
            "rows": rows, "quality_status": "OK"
        }, f, ensure_ascii=False, indent=2)

# ── 主循环 ─────────────────────────────────────────────────────────────────
def run(batch_size=300, batch_sleep=4):
    stocks = get_stock_list()
    total = len(stocks)
    success = fail = skip = 0
    failed = []
    t0 = time.time()

    log.info(f"=== 初始化开始 === 股票:{total} 批次:{(total+batch_size-1)//batch_size} 范围:{START}~{END}")

    # 已有数据的先跳过
    existing = {f.stem for f in KLINE_DIR.glob("*.csv")}
    if existing:
        log.info(f"已有 {len(existing)} 只股票的本地数据，跳过")

    for i, (code, name) in enumerate(stocks, 1):
        if code in existing:
            skip += 1; continue

        df, src = fetch_stock(code)
        if df is not None and not df.empty:
            write_csv(code, df)
            write_meta(code, name, src, len(df))
            success += 1
        else:
            fail += 1; failed.append(code)

        if i % batch_size == 0:
            elapsed = time.time()-t0
            log.info(f"  批次完成 {i}/{total} 耗时{elapsed:.0f}s")

        if i % batch_size == 0 and i < total:
            time.sleep(batch_sleep)

    elapsed = time.time()-t0
    summary = {
        "update_time": datetime.now().isoformat(),
        "total": total, "success": success, "fail": fail, "skip": skip,
        "failed_codes": failed[:100], "elapsed_seconds": round(elapsed,1),
    }
    with open(LOG_DIR / f"init_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json","w",encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    log.info(f"=== 完成 === 成功:{success} 失败:{fail} 跳过:{skip} 耗时:{elapsed:.0f}s")
    return summary

if __name__ == "__main__":
    run()
