"""
TuShare 全量重建 K 线 - 单线程安全版
Phase-2.3C
原则：单线程 + 0.12s 延迟 = 绝对不超过 500次/分钟
"""
import sys, os, time, json, logging
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT_DIR = Path(__file__).parent.parent.resolve()
KLINE_DIR = PROJECT_DIR / "data" / "kline_daily"
ADJ_DIR = PROJECT_DIR / "data" / "adj_factor"
FEATURES_LOG = PROJECT_DIR / "features" / "logs"

KLINE_DIR.mkdir(parents=True, exist_ok=True)
ADJ_DIR.mkdir(parents=True, exist_ok=True)
FEATURES_LOG.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("/tmp/tushare_rebuild.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

import requests

TOKEN = "e85b62c1005ad7254faf4cfa7b2e0fac194af09889ddb784d1882f74"
BASE_URL = "https://api.tushare.pro"
RATE_LIMIT_DELAY = 0.13  # 500次/分钟 → 每秒≤8.3次 → 0.12s/次安全

_session = requests.Session()
_session.headers["Content-Type"] = "application/json"


def _call(api_name, params=None, fields=None):
    payload = {"api_name": api_name, "token": TOKEN, "params": params or {}}
    if fields and api_name not in ("stock_basic", "trade_cal", "index_basic"):
        payload["fields"] = fields
    elif fields and api_name in ("stock_basic", "trade_cal", "index_basic"):
        payload["params"]["fields"] = fields

    for attempt in range(3):
        try:
            resp = _session.post(BASE_URL, json=payload, timeout=30)
            data = resp.json()
            if data.get("code") == 0:
                return data["data"]
            logger.warning(f"TuShare {api_name} code={data.get('code')} msg={data.get('msg')}")
            return {"items": [], "fields": []}
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
            else:
                logger.error(f"TuShare {api_name} 最终失败: {e}")
                return {"items": [], "fields": []}
    return {"items": [], "fields": []}


def _to_df(data):
    if not data or not data.get("items"):
        return None
    import pandas as pd
    return pd.DataFrame(data["items"], columns=data["fields"])


def ts_to_code(ts):
    return ts.replace(".SH", "").replace(".SZ", "")


def fix_high_low(df):
    """修复 high < low"""
    if df is None or "high" not in df.columns:
        return df, 0
    mask = df["high"] < df["low"]
    count = int(mask.sum())
    if count:
        max_val = df.loc[mask, ["high", "low"]].max(axis=1)
        min_val = df.loc[mask, ["high", "low"]].min(axis=1)
        df.loc[mask, "high"] = max_val
        df.loc[mask, "low"] = min_val
    return df, count


def convert_and_save(df_tushare, ts_code):
    """
    TuShare DataFrame → 现有系统格式
    现有格式: code,date,open,high,low,close,volume,amount,turnover,source,adjust,update_time
    """
    if df_tushare is None or df_tushare.empty:
        return None

    df = df_tushare.copy()

    # 列名统一：trade_date→date, vol→volume
    if "trade_date" in df.columns:
        df = df.rename(columns={"trade_date": "date"})
    if "vol" in df.columns:
        df = df.rename(columns={"vol": "volume"})

    # 修复 high < low
    df, fixed = fix_high_low(df)

    # 补充字段
    code = ts_to_code(ts_code)
    df.insert(0, "code", code)
    df["source"] = "tushare"
    df["adjust"] = "qfq"
    df["turnover"] = None
    df["update_time"] = datetime.now().isoformat()

    # 列顺序
    wanted = ["code", "date", "open", "high", "low", "close", "volume", "amount", "turnover", "source", "adjust", "update_time"]
    for c in wanted:
        if c not in df.columns:
            df[c] = None
    df = df[wanted]

    return df, fixed


def download_one(ts_code, start_date, end_date):
    """下载单只并保存"""
    code = ts_to_code(ts_code)
    out_path = KLINE_DIR / f"{code}.csv"

    # 下载日K
    df_raw = _to_df(_call("daily", {"ts_code": ts_code, "start_date": start_date, "end_date": end_date}))
    if df_raw is None or df_raw.empty:
        return False, 0, f"{ts_code}: no_data"

    result, fixed = convert_and_save(df_raw, ts_code)
    if result is None:
        return False, 0, f"{ts_code}: convert_failed"

    result.to_csv(out_path, index=False)
    rows = len(result)

    # 复权因子
    adj_raw = _to_df(_call("adj_factor", {"ts_code": ts_code, "start_date": start_date, "end_date": end_date}))
    if adj_raw is not None and not adj_raw.empty:
        adj_out = ADJ_DIR / f"{ts_code}.csv"
        adj_raw = adj_raw.rename(columns={"trade_date": "date"}) if "trade_date" in adj_raw.columns else adj_raw
        adj_raw.to_csv(adj_out, index=False)

    return True, rows, fixed


def main(resume=False):
    start_time = datetime.now()
    start_date = "20200101"
    end_date = datetime.now().strftime("%Y%m%d")
    SLEEP = RATE_LIMIT_DELAY

    logger.info(f"=== TuShare 全量重建 K 线 (单线程安全版) ===")
    logger.info(f"范围: {start_date} ~ {end_date}")
    logger.info(f"延迟: {SLEEP}s/请求 (安全 < 500次/分钟)")

    # 股票列表
    logger.info("[1/3] 获取股票列表...")
    stocks_df = _to_df(_call("stock_basic", {"list_status": "L"}))
    if stocks_df is None:
        logger.error("无法获取股票列表"); return
    all_stocks = stocks_df["ts_code"].tolist()
    logger.info(f"  共 {len(all_stocks)} 只")

    # 断点续跑
    done_file = FEATURES_LOG / ".rebuild_done.json"
    done_set = set()
    if resume and done_file.exists():
        try:
            done_set = set(json.load(open(done_file)))
            logger.info(f"  已完成: {len(done_set)} 只 (resume)")
        except:
            pass

    to_do = [s for s in all_stocks if s not in done_set]
    logger.info(f"  待处理: {len(to_do)} 只")

    # 单线程下载
    logger.info(f"[2/3] 下载 + 转换 (单线程, {SLEEP}s延迟)...")
    stats = {"ok": 0, "fail": 0, "rows": 0, "fixed": 0}
    errors = []

    for i, ts in enumerate(to_do):
        ok, rows, fixed = download_one(ts, start_date, end_date)
        if ok:
            stats["ok"] += 1
            stats["rows"] += rows
            stats["fixed"] += fixed
            done_set.add(ts)
        else:
            stats["fail"] += 1
            errors.append(fixed)  # 错误信息在fixed位置

        # 每100只报告进度
        if (i + 1) % 100 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            speed = (i + 1) / elapsed
            remain = (len(to_do) - i - 1) / speed if speed > 0 else 0
            logger.info(
                f"  {i+1}/{len(to_do)} ({ (i+1)/len(to_do)*100:.1f}%) "
                f"| ok={stats['ok']} fail={stats['fail']} "
                f"| 剩余约 {remain/60:.1f}分钟"
            )

        time.sleep(SLEEP)

        # 每500只保存断点
        if (i + 1) % 500 == 0:
            with open(done_file, "w") as f:
                json.dump(sorted(done_set), f)

    # 最终保存
    with open(done_file, "w") as f:
        json.dump(sorted(done_set), f)

    elapsed = (datetime.now() - start_time).total_seconds()

    logger.info(f"[3/3] 完成！耗时 {elapsed:.0f}秒 ({elapsed/60:.1f}分钟)")
    logger.info(f"  ok={stats['ok']} fail={stats['fail']} 总行={stats['rows']} high<low修复={stats['fixed']}")
    if errors[:5]:
        logger.warning(f"  错误样例: {errors[:5]}")

    # 重建 factors
    logger.info("[4/4] 重建 daily_technical_factors...")
    import subprocess, sys
    r = subprocess.run(
        [sys.executable, str(PROJECT_DIR / "features" / "build_technical_factor_cache.py")],
        capture_output=True, text=True, timeout=600, cwd=str(PROJECT_DIR)
    )
    logger.info(f"  factors: exit={r.returncode}")

    # 质量检查
    logger.info("[5/5] K线质量检查...")
    from data_quality.kline_quality_checker import KLineQualityChecker
    checker = KLineQualityChecker()
    report = checker.run_full_check(force_recheck=True)
    logger.info(f"  CRITICAL={report['stats']['critical_files']} | {'✅' if report['CRITICAL'] else '❌'}")


if __name__ == "__main__":
    resume = "--resume" in sys.argv
    main(resume=resume)
