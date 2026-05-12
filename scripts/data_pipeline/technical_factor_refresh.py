"""
Phase-2.3B Technical Factor Refresh
收盘后预计算技术指标
输出：data/factors_daily/
指标：MA5/MA10/MA20/MA60, RSI, MACD, KDJ, ATR, 涨跌幅, 量比
"""

import csv, json, logging, time
from pathlib import Path
from datetime import datetime
import numpy as np

DATA_HOME  = Path("/Users/gino/project_ai_trading/data")
KLINE_DIR  = DATA_HOME / "kline_daily"
FACTOR_DIR = DATA_HOME / "factors_daily"
FACTOR_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("tech_factor")

FIELDS = ["code","date","open","high","low","close","volume","amount","turnover","source","adjust","update_time"]

def calc_ma(closes, period):
    if len(closes) < period: return [None]*len(closes)
    arr = np.array(closes, dtype=float)
    out = [None]*(period-1)
    for i in range(period-1, len(arr)):
        out.append(round(arr[i-period+1:i+1].mean(), 4))
    return out

def calc_rsi(closes, period=14):
    if len(closes) < period+1: return [None]*len(closes)
    arr = np.array(closes, dtype=float)
    deltas = np.diff(arr)
    gains = np.where(deltas>0, deltas, 0)
    losses = np.where(deltas<0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    out = [None]*period
    for i in range(period, len(arr)):
        avg_gain = (avg_gain*(period-1) + gains[i-1])/period
        avg_loss = (avg_loss*(period-1) + losses[i-1])/period
        if avg_loss == 0: out.append(100)
        else: out.append(round(100 - 100/(1+avg_gain/avg_loss), 2))
    return out

def calc_macd(closes, fast=12, slow=26, signal=9):
    arr = np.array(closes, dtype=float)
    if len(arr) < slow+signal: return [None]*len(arr), [None]*len(arr), [None]*len(arr)
    ema_fast = list(_ema(arr, fast))
    ema_slow = list(_ema(arr, slow))
    dif = []
    for f, s in zip(ema_fast, ema_slow):
        if f is None or s is None:
            dif.append(None)
        else:
            dif.append(f - s)
    # DEA
    dif_vals = [x if x is not None else 0 for x in dif]
    dea = list(_ema(np.array(dif_vals, dtype=float), signal))
    macd = []
    for d, g in zip(dif, dea):
        if d is None or g is None:
            macd.append(None)
        else:
            macd.append(round((d - g) * 2, 4))
    return dif, dea, macd

def _ema(arr, period):
    out = [None]*len(arr)
    if len(arr) < period: return out
    sma = np.mean(arr[:period])
    out[period-1] = round(sma, 4)
    k = 2/(period+1)
    for i in range(period, len(arr)):
        out[i] = round(arr[i]*k + out[i-1]*(1-k), 4)
    return out

def calc_kdj(highs, lows, closes, period=9, k_period=3, d_period=3):
    arr_h = np.array(highs, dtype=float)
    arr_l = np.array(lows, dtype=float)
    arr_c = np.array(closes, dtype=float)
    n = len(arr_c)
    if n < period: return [None]*n, [None]*n, [None]*n
    K = [50.0]*n
    D = [50.0]*n
    for i in range(period-1, n):
        h = np.max(arr_h[i-period+1:i+1])
        l = np.min(arr_l[i-period+1:i+1])
        c = arr_c[i]
        if h==l: rsv = 50
        else: rsv = (c-l)/(h-l)*100
        K[i] = (2/3)*K[i-1] + (1/3)*rsv
        D[i] = (2/3)*D[i-1] + (1/3)*K[i]
    J = [round(3*K[i]-2*D[i], 2) if K[i] is not None else None for i in range(n)]
    return [round(x,2) for x in K], [round(x,2) for x in D], J

def calc_atr(highs, lows, closes, period=14):
    arr_h = np.array(highs, dtype=float)
    arr_l = np.array(lows, dtype=float)
    arr_c = np.array(closes, dtype=float)
    n = len(arr_c)
    if n < 2: return [None]*n
    tr = [max(arr_h[0]-arr_l[0], abs(arr_h[0]-arr_c[0]), abs(arr_c[0]-arr_l[0]))]
    for i in range(1, n):
        h, l, c, pc = arr_h[i], arr_l[i], arr_c[i], arr_c[i-1]
        tr.append(max(h-l, abs(h-pc), abs(l-pc)))
    tr = np.array(tr)
    out = [None]*(period-1)
    if len(tr) < period: return out
    avg = np.mean(tr[:period])
    out.append(round(avg, 4))
    for i in range(period, len(tr)):
        avg = (avg*(period-1) + tr[i])/period
        out.append(round(avg, 4))
    return out

def volume_ratio(volumes):
    if len(volumes) < 5: return [None]*len(volumes)
    arr = np.array(volumes, dtype=float)
    avg5_list = []
    for i in range(4, len(arr)):
        avg5_list.append(arr[i-4:i+1].mean())
    out = [None]*4
    for i, avg_val in enumerate(avg5_list):
        idx = i + 4
        if avg_val == 0:
            out.append(None)
        else:
            out.append(round(arr[idx]/avg_val, 2))
    return out

def process_stock(code):
    path = KLINE_DIR / f"{code}.csv"
    if not path.exists(): return None
    rows = []
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if len(rows) < 60: return None  # 至少60天数据才够算MA60+RSI14

    closes = [float(r["close"]) for r in rows]
    highs  = [float(r["high"])  for r in rows]
    lows   = [float(r["low"])   for r in rows]
    vols   = [float(r["volume"]) for r in rows]
    dates  = [r["date"]        for r in rows]

    ma5   = calc_ma(closes, 5)
    ma10  = calc_ma(closes, 10)
    ma20  = calc_ma(closes, 20)
    ma60  = calc_ma(closes, 60)
    rsi   = calc_rsi(closes)
    dif, dea, macd = calc_macd(closes)
    k_val, d_val, j_val = calc_kdj(highs, lows, closes)
    atr   = calc_atr(highs, lows, closes)
    vr    = volume_ratio(vols)

    # 涨跌幅用原始turnover字段
    pcts  = [float(r.get("turnover",0)) for r in rows]

    # 拼接输出（只输出最新N条）
    N = min(len(rows), 252)  # 最多1年
    factor_rows = []
    for i in range(max(0, len(rows)-N), len(rows)):
        factor_rows.append({
            "code": code, "date": dates[i],
            "close": closes[i],
            "ma5": ma5[i], "ma10": ma10[i], "ma20": ma20[i], "ma60": ma60[i],
            "rsi": rsi[i] if i < len(rsi) else None,
            "dif": dif[i] if i < len(dif) else None,
            "dea": dea[i] if i < len(dea) else None,
            "macd": macd[i] if i < len(macd) else None,
            "k": k_val[i] if i < len(k_val) else None,
            "d": d_val[i] if i < len(d_val) else None,
            "j": j_val[i] if i < len(j_val) else None,
            "atr": atr[i] if i < len(atr) else None,
            "volume_ratio": vr[i] if i < len(vr) else None,
            "pct_change": pcts[i],
        })

    return factor_rows

def run():
    files = list(KLINE_DIR.glob("*.csv"))
    total = len(files)
    t0 = time.time()
    log.info(f"=== 技术指标计算开始 === 股票:{total}")

    all_factors = {}
    for i, f in enumerate(files, 1):
        rows = process_stock(f.stem)
        if rows:
            all_factors[f.stem] = rows
        if i%500==0: log.info(f"  {i}/{total}")

    # 写入每只股票一个因子文件
    for code, rows in all_factors.items():
        out_path = FACTOR_DIR / f"{code}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)

    elapsed = time.time()-t0
    summary = {
        "update_time": datetime.now().isoformat(),
        "total_stocks": total,
        "success": len(all_factors),
        "elapsed_seconds": round(elapsed,1),
        "output_dir": str(FACTOR_DIR),
    }
    with open(FACTOR_DIR / "refresh_summary.json","w",encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    log.info(f"=== 完成 === 计算:{len(all_factors)}/{total} 耗时:{elapsed:.0f}s")
    return summary

if __name__ == "__main__":
    run()
