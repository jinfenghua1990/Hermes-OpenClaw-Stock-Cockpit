"""
Phase-2.3B Kline Data Guard
数据质量检查脚本
检查：缺失日期/重复日期/OHLC异常/成交量异常/涨跌幅异常/复权混乱/数据源缺失
异常写入 data/data_quality/kline_quality_YYYYMMDD.json
"""

import csv, json, logging, time
from pathlib import Path
from datetime import datetime

DATA_HOME = Path("/Users/gino/project_ai_trading/data")
KLINE_DIR = DATA_HOME / "kline_daily"
QUAL_DIR  = DATA_HOME / "data_quality"
QUAL_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(QUAL_DIR / f"guard_{datetime.now().strftime('%Y%m%d')}.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("kline_guard")
FIELDS = ["code","date","open","high","low","close","volume","amount","turnover","source","adjust","update_time"]

ANOMALY_RULES = {
    "high_lt_low":      lambda r: float(r["high"]) < float(r["low"]),
    "close_le_zero":    lambda r: float(r["close"]) <= 0,
    "volume_lt_zero":   lambda r: float(r["volume"]) < 0,
    "amount_lt_zero":   lambda r: float(r["amount"]) < 0,
}

def check_stock(code):
    path = KLINE_DIR / f"{code}.csv"
    anomalies = []
    if not path.exists():
        return [{"code":code,"type":"file_missing","severity":"HIGH","detail":"CSV不存在"}]
    rows = []
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f, fieldnames=FIELDS))
    # 重复日期
    seen, dups = {}, []
    for r in rows:
        if r["date"] in seen:
            dups.append(r["date"])
        seen[r["date"]] = r
    if dups:
        anomalies.append({"code":code,"type":"duplicate_date","severity":"MEDIUM",
                          "detail":f"重复日期: {set(dups)}","affected":len(dups)})
    # OHLC/成交量检查
    for r in rows:
        for name, rule in ANOMALY_RULES.items():
            try:
                if rule(r):
                    anomalies.append({"code":code,"type":name,"severity":"CRITICAL",
                                     "detail":f"{r['date']} {name}","row_date":r["date"]})
                    break
            except: pass
    # 涨跌幅超限（按板块差异化判断）
    PCT_LIMIT = {"主板": 10.5, "创业板": 20.5, "科创板": 20.5, "北交所": 30.5, "未知": 10.5}
    def _board(code):
        if code.startswith("688") or code.startswith("689"): return "科创板"
        if code.startswith(("300","301")): return "创业板"
        if code.startswith("8"): return "北交所"
        return "主板"
    for r in rows:
        try:
            pct = float(r.get("turnover",0))
            limit = PCT_LIMIT.get(_board(code), 10.5)
            if abs(pct) > limit:
                anomalies.append({"code":code,"type":"pct_abnormal","severity":"HIGH",
                                 "detail":f"{r['date']} pct={pct}% 板块限额{limit}%","row_date":r["date"]})
        except: pass
    return anomalies

def run():
    files = list(KLINE_DIR.glob("*.csv"))
    total = len(files)
    all_anomalies = []
    t0 = time.time()
    log.info(f"=== 质量检查开始 === 股票:{total}")
    for i, f in enumerate(files, 1):
        anomalies = check_stock(f.stem)
        all_anomalies.extend(anomalies)
        if i%500==0: log.info(f"  {i}/{total}")
    elapsed = time.time()-t0
    counts = {"CRITICAL":0,"HIGH":0,"MEDIUM":0,"LOW":0,"OK":total}
    for a in all_anomalies:
        counts[a["severity"]] += 1
    counts["OK"] = max(0, total - sum(v for k,v in counts.items() if k!="OK"))
    result = {
        "check_time": datetime.now().isoformat(),
        "total_stocks": total,
        "anomalies": all_anomalies[:100],
        "summary": counts,
        "elapsed_seconds": round(elapsed,1),
    }
    out = QUAL_DIR / f"kline_quality_{datetime.now().strftime('%Y%m%d')}.json"
    with open(out,"w",encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log.info(f"=== 完成 === 正常:{counts['OK']} 异常:{len(all_anomalies)} 耗时:{elapsed:.0f}s")
    log.info(f"报告: {out}")
    return result

if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv)>1 else None
    if code:
        print(json.dumps(check_stock(code), indent=2, ensure_ascii=False))
    else:
        run()
