"""
Phase-2.3B-Fix2: 补拉失败股票（baostock版 v3）
数据源：baostock（前复权）→ akshare（备用）
"""

import os, sys, json, time, logging, csv, argparse
from pathlib import Path
from datetime import datetime
import pandas as pd

DATA_HOME = Path("/Users/gino/project_ai_trading/data")
KLINE_DIR  = DATA_HOME / "kline_daily"
LOG_DIR    = DATA_HOME / "update_logs"
FAIL_FILE  = LOG_DIR / "kline_failed_20260512.csv"
KLINE_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"retry_bao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("retry_bao_v3")

FIELDS     = ["code","date","open","high","low","close","volume","amount","turnover","source","adjust","update_time"]
END        = datetime.now().strftime("%Y-%m-%d")
START      = "2018-01-01"
UPDATE_TIME = datetime.now().isoformat()

_bao_session = None

def get_bao():
    global _bao_session
    if _bao_session is None:
        import baostock as bs
        bs.login()
        _bao_session = bs
    return _bao_session

def close_bao():
    global _bao_session
    if _bao_session:
        try:
            _bao_session.logout()
        except: pass
        _bao_session = None

def to_bsymbol(code: str):
    code = str(code).zfill(6)
    return f"sh.{code}" if code.startswith(("688","689","600","601","603","605")) else f"sz.{code}"

def fetch_baostock(code: str):
    bs_code = to_bsymbol(code)
    try:
        bs = get_bao()
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close,volume,amount",
            start_date=START, end_date=END,
            frequency="d", adjustflag="2"
        )
        data = []
        while rs.error_code == "0" and rs.next():
            data.append(rs.get_row_data())
        if data:
            df = pd.DataFrame(data, columns=rs.fields)
            df["code"] = code
            closes = pd.to_numeric(df["close"], errors="coerce").fillna(0)
            df["turnover"] = closes.pct_change().fillna(0) * 100
            df["source"] = "baostock"
            df["adjust"] = "qfq"
            df["update_time"] = UPDATE_TIME
            return df
    except Exception as e:
        pass
    return None

def fetch_akshare(code: str):
    code = str(code).zfill(6)
    try:
        import akshare as ak
        prefix = "sh" if code.startswith(("688","600","601","603","605")) else "sz"
        df = ak.stock_zh_a_daily(
            symbol=prefix + code,
            start_date="20180101", end_date="20260512",
            adjust=""
        )
        if df is not None and len(df) > 100:
            df = df.rename(columns={
                "date":"date","open":"open","high":"high","low":"low",
                "close":"close","volume":"volume","amount":"amount",
            })
            closes = pd.to_numeric(df["close"], errors="coerce").fillna(0)
            df["turnover"] = closes.pct_change().fillna(0) * 100
            df["code"] = code
            df["source"] = "ak_daily"
            df["adjust"] = "none"
            df["update_time"] = UPDATE_TIME
            return df
    except: pass
    return None

def clean(df):
    for col in ["open","high","low","close","volume","amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df = df[df["close"] > 0].copy()
    df["high"] = df[["open","close","high"]].max(axis=1)
    df["low"]  = df[["open","close","low"]].min(axis=1)
    df = df.drop_duplicates(subset=["date"], keep="last")
    return df.sort_values("date")

def write_stock(code, df, source, adjust):
    path = KLINE_DIR / f"{code}.csv"
    seen = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f, fieldnames=FIELDS):
                seen[r["date"]] = r
    for _, r in df.iterrows():
        d = str(r["date"])
        row = {
            "code": str(code), "date": d,
            "open": f"{float(r['open']):.4f}",
            "high": f"{float(r['high']):.4f}",
            "low":  f"{float(r['low']):.4f}",
            "close":f"{float(r['close']):.4f}",
            "volume": str(int(float(r["volume"]))),
            "amount": f"{float(r['amount']):.2f}",
            "turnover": f"{float(r['turnover']):.4f}",
            "source": str(r["source"]),
            "adjust": str(r["adjust"]),
            "update_time": str(r["update_time"]),
        }
        if d not in seen or row["update_time"] > seen[d].get("update_time",""):
            seen[d] = row
    out = sorted(seen.values(), key=lambda x: x["date"])
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out)
    quality = "OK" if adjust == "qfq" else "ADJUST_NOT_QFQ"
    with open(KLINE_DIR / f"{code}.meta.json", "w", encoding="utf-8") as f:
        json.dump({
            "code": code, "name": "", "adjust": adjust, "source": source,
            "first_date": str(out[0]["date"]) if out else "",
            "last_date":  str(out[-1]["date"]) if out else "",
            "last_update_time": UPDATE_TIME,
            "rows": len(out), "quality_status": quality,
        }, f, ensure_ascii=False, indent=2)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="store_true")
    parser.add_argument("--all",    action="store_true")
    parser.add_argument("--codes",  type=str, default="")
    args = parser.parse_args()

    targets = []
    if args.codes:
        targets = [{"code": c} for c in args.codes.split(",")]
        log.info(f"=== 指定代码 === {len(targets)} 只")
    elif args.sample:
        SAMPLE = ["600519","601398","603259","000001","000333","002475","002463","300750","300059","301282","688981","688111"]
        targets = [{"code": c} for c in SAMPLE]
        log.info(f"=== 样本验证 === {len(targets)} 只")
    else:
        if not FAIL_FILE.exists():
            log.error(f"失败清单不存在: {FAIL_FILE}")
            return
        with open(FAIL_FILE, encoding="utf-8") as f:
            targets = list(csv.DictReader(f))
        log.info(f"=== 全量补拉 === {len(targets)} 只")

    success = fail = skip = 0
    source_stats = {}
    failed_codes = []
    t0 = time.time()

    try:
        for i, row in enumerate(targets, 1):
            code = str(row["code"]).zfill(6)
            path = KLINE_DIR / f"{code}.csv"
            if path.exists():
                with open(path) as f:
                    lines = len(f.readlines())
                if lines > 100:
                    skip += 1
                    continue

            log.info(f"[{i}/{len(targets)}] {code}")
            df = fetch_baostock(code)
            src, adj = "baostock", "qfq"
            if df is None or len(df) < 100:
                df = fetch_akshare(code)
                src, adj = "ak_daily", "none"

            if df is not None and len(df) > 100:
                df = clean(df)
                write_stock(code, df, src, adj)
                success += 1
                source_stats[src] = source_stats.get(src, 0) + 1
                log.info(f"  ✅ {code} ← {src} ({len(df)}条)")
            else:
                fail += 1
                failed_codes.append(code)
                log.warning(f"  ❌ {code} ← 全部失败")

            if i % 100 == 0:
                elapsed = time.time() - t0
                log.info(f"  进度 {i}/{len(targets)} 耗时{elapsed:.0f}s")
                time.sleep(2)
    finally:
        close_bao()

    elapsed = time.time() - t0
    total_csv = len(list(KLINE_DIR.glob("*.csv")))
    summary = {
        "update_time": UPDATE_TIME,
        "mode": "sample" if args.sample else ("codes" if args.codes else "full"),
        "total": len(targets),
        "success": success, "fail": fail, "skip": skip,
        "current_csv": total_csv,
        "source_stats": source_stats,
        "failed_codes": failed_codes[:200],
        "elapsed_seconds": round(elapsed,1),
    }
    out = LOG_DIR / f"retry_summary_v3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    log.info(f"=== 完成 === 成功:{success} 失败:{fail} 跳过:{skip} 当前CSV:{total_csv} 耗时:{elapsed:.0f}s")
    log.info(f"数据源: {source_stats}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
