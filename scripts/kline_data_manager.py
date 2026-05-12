"""
A股本地K线数据底座 — 数据管理器
Phase-2.3B A股本地K线数据底座

功能：
1. 初始化：一次性拉取全A股历史日K（2018-至今）
2. 增量更新：每日收盘后补充当日K线
3. 盘中隔离：实时数据写入 realtime_cache/，不污染历史日K
4. 防重复：code+date去重，保留最新update_time
5. metadata：每只股票生成 .meta.json 状态文件
6. fallback：efinance → AKShare → easyquotation → cache

作者：Hermes Main / Strategy Architect
"""

import os
import json
import time
import logging
import warnings
from datetime import datetime, date
from pathlib import Path
from typing import Optional

warnings.filterwarnings("ignore")

# ── 路径配置 ────────────────────────────────────────────────────────────────
DATA_HOME = Path(os.environ.get("DATA_HOME", "/Users/gino/project_ai_trading/data"))
KLINE_DAILY = DATA_HOME / "kline_daily"
KLINE_MINUTE = DATA_HOME / "kline_minute"
REALTIME_CACHE = DATA_HOME / "realtime_cache"
SECTOR_CACHE = DATA_HOME / "sector_cache"
UPDATE_LOGS = DATA_HOME / "update_logs"
DATA_QUALITY = DATA_HOME / "data_quality"
TRADING_CALENDAR = DATA_HOME / "trading_calendar.csv"

KLINE_DAILY.mkdir(parents=True, exist_ok=True)
KLINE_MINUTE.mkdir(parents=True, exist_ok=True)
REALTIME_CACHE.mkdir(parents=True, exist_ok=True)
SECTOR_CACHE.mkdir(parents=True, exist_ok=True)
UPDATE_LOGS.mkdir(parents=True, exist_ok=True)
DATA_QUALITY.mkdir(parents=True, exist_ok=True)

# ── 日志配置 ────────────────────────────────────────────────────────────────
log_file = UPDATE_LOGS / f"kline_update_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("kline_manager")


# ── 数据源优先级 ────────────────────────────────────────────────────────────
def get_kline_efinance(code: str, start: str = "2018-01-01", end: str = None,
                       adjust: str = "qfq") -> Optional[list]:
    """efinance 主数据源"""
    try:
        import efinance as ef
        end = end or datetime.now().strftime("%Y-%m-%d")
        df = ef.stock.get_quote_history(code, start=start, end=end, fq=adjust)
        if df is None or df.empty:
            return None
        df = df.rename(columns={
            "股票代码": "code", "日期": "date",
            "开盘": "open", "最高": "high", "最低": "low",
            "收盘": "close", "成交量": "volume",
            "成交额": "amount", "振幅": "turnover",
        })
        df["source"] = "efinance"
        df["adjust"] = adjust
        df["update_time"] = datetime.now().isoformat()
        return df[["code", "date", "open", "high", "low", "close",
                   "volume", "amount", "turnover", "source", "adjust",
                   "update_time"]].to_dict("records")
    except Exception as e:
        log.warning(f"efinance 失败 {code}: {e}")
        return None


def get_kline_akshare(code: str, adjust: str = "qfq") -> Optional[list]:
    """AKShare 备用数据源"""
    try:
        import akshare as ak
        start = "20180101"
        end = datetime.now().strftime("%Y%m%d")
        # 前复权日K
        df = ak.stock_zh_a_hist(symbol=code.zfill(6), period="daily",
                                  start_date=start, end_date=end,
                                  adjust=adjust if adjust == "qfq" else "qfq")
        if df is None or df.empty:
            return None
        df = df.rename(columns={
            "日期": "date", "开盘": "open", "最高": "high",
            "最低": "low", "收盘": "close", "成交量": "volume",
            "成交额": "amount", "涨跌幅": "turnover",
        })
        df["code"] = code.zfill(6)
        df["source"] = "akshare"
        df["adjust"] = adjust
        df["update_time"] = datetime.now().isoformat()
        return df[["code", "date", "open", "high", "low", "close",
                   "volume", "amount", "turnover", "source", "adjust",
                   "update_time"]].to_dict("records")
    except Exception as e:
        log.warning(f"akshare 失败 {code}: {e}")
        return None


def fetch_kline(code: str, start: str = "2018-01-01",
                adjust: str = "qfq") -> Optional[list]:
    """数据源 fallback：efinance → akshare"""
    for source_name, fetcher in [
        ("efinance", lambda: get_kline_efinance(code, start, adjust=adjust)),
        ("akshare",  lambda: get_kline_akshare(code, adjust=adjust)),
    ]:
        result = fetcher()
        if result:
            log.info(f"  {code} ← {source_name} ({len(result)} 条)")
            return result
    log.error(f"  {code} ← 全部数据源失败")
    return None


# ── 全A股股票列表 ────────────────────────────────────────────────────────────
def get_stock_list() -> list[tuple[str, str]]:
    """获取全A股股票列表 (code, name)"""
    try:
        import efinance as ef
        df = ef.stock.get_base_info()
        return [(str(r["代码"]).zfill(6), r.get("名称", "")) for _, r in df.iterrows()]
    except Exception:
        pass
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        return [(str(r["code"]).zfill(6), r.get("name", "")) for _, r in df.iterrows()]
    except Exception:
        pass
    log.error("无法获取股票列表")
    return []


# ── CSV 读写 ────────────────────────────────────────────────────────────────
CSV_FIELDS = ["code", "date", "open", "high", "low", "close",
              "volume", "amount", "turnover", "source", "adjust", "update_time"]


def read_csv(code: str) -> list[dict]:
    """读取本地日K，code 形如 '000001'"""
    path = KLINE_DAILY / f"{code.zfill(6)}.csv"
    if not path.exists():
        return []
    import csv
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, fieldnames=CSV_FIELDS)
        for row in reader:
            rows.append(row)
    return rows


def write_csv(code: str, rows: list[dict]):
    """写入日K，自动去重（code+date，保留最新update_time）"""
    import csv
    path = KLINE_DAILY / f"{code.zfill(6)}.csv"
    # 去重：{date: row} 取最大 update_time
    seen = {}
    for r in rows:
        k = r["date"]
        if k not in seen or r["update_time"] > seen[k]["update_time"]:
            seen[k] = r
    out = list(seen.values())
    out.sort(key=lambda x: x["date"])

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(out)


def append_kline(code: str, new_rows: list[dict]):
    """增量追加：读取本地 → 合并去重 → 写入"""
    existing = read_csv(code)
    merged = {r["date"]: r for r in existing}
    for r in new_rows:
        k = r["date"]
        if k not in merged or r["update_time"] > merged[k]["update_time"]:
            merged[k] = r
    write_csv(code, list(merged.values()))


# ── Metadata 管理 ──────────────────────────────────────────────────────────
def read_meta(code: str) -> dict:
    path = KLINE_DAILY / f"{code.zfill(6)}.meta.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def write_meta(code: str, name: str = "", adjust: str = "qfq", source: str = ""):
    rows = read_csv(code)
    meta = {
        "code": code.zfill(6),
        "name": name,
        "adjust": adjust,
        "source": source,
        "first_date": rows[0]["date"] if rows else "",
        "last_date": rows[-1]["date"] if rows else "",
        "last_update_time": datetime.now().isoformat(),
        "rows": len(rows),
        "quality_status": "OK",
    }
    path = KLINE_DAILY / f"{code.zfill(6)}.meta.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


# ── 异常检测 ────────────────────────────────────────────────────────────────
ANOMALY_RULES = [
    lambda r: float(r["high"]) < float(r["low"]),
    lambda r: float(r["close"]) <= 0,
    lambda r: float(r["volume"]) < 0,
    lambda r: float(r["amount"]) < 0,
]


def is_anomaly(row: dict) -> bool:
    for rule in ANOMALY_RULES:
        try:
            if rule(row):
                return True
        except Exception:
            return True
    return False


# ── 批量初始化 ─────────────────────────────────────────────────────────────
def init_all_stocks(batch_size: int = 300, batch_sleep: int = 3,
                    start: str = "2018-01-01"):
    """首次运行：批量拉取全A股历史K线"""
    stocks = get_stock_list()
    total = len(stocks)
    success = fail = skip = 0
    failed_stocks = []
    start_time = time.time()

    log.info(f"=== 全量初始化开始 === 股票总数：{total} 批次：{(total+batch_size-1)//batch_size}")

    for i, (code, name) in enumerate(stocks, 1):
        c = code.zfill(6)
        local_rows = read_csv(c)

        # 检查是否已有完整历史（跳过）
        if local_rows:
            local_last = local_rows[-1]["date"]
            if local_last >= "2025-01-01":
                skip += 1
                if i % 100 == 0:
                    log.info(f"  跳过已有数据：{c}（{i}/{total}）")
                continue

        rows = fetch_kline(c, start=start)
        if rows:
            clean = [r for r in rows if not is_anomaly(r)]
            write_csv(c, clean)
            write_meta(c, name=name, source=rows[0].get("source", ""))
            success += 1
        else:
            fail += 1
            failed_stocks.append(c)

        if i % batch_size == 0:
            elapsed = time.time() - start_time
            log.info(f"  ——— 批次完成 {i}/{total} 耗时 {elapsed:.0f}s ———")
            time.sleep(batch_sleep)

    elapsed = time.time() - start_time
    summary = {
        "update_time": datetime.now().isoformat(),
        "total_stocks": total,
        "success": success,
        "fail": fail,
        "skip": skip,
        "failed_stocks": failed_stocks[:50],
        "elapsed_seconds": round(elapsed, 1),
        "data_source": "efinance→akshare",
    }
    log.info(f"=== 初始化完成 === 成功:{success} 失败:{fail} 跳过:{skip} 耗时:{elapsed:.0f}s")
    _save_update_log(summary)
    return summary


# ── 增量更新 ────────────────────────────────────────────────────────────────
def is_trading_day(d: date) -> bool:
    """简单判断：周一到周五，非节假日（精确版依赖 calendar 数据）"""
    # 后续读取 trading_calendar.csv 做精确判断
    return d.weekday() < 5  # 临时：仅排除周末


def incremental_update(stock_codes: list[str] = None,
                       trading_date: str = None):
    """每日收盘后增量更新"""
    td = trading_date or date.today().strftime("%Y-%m-%d")
    td_date = datetime.strptime(td, "%Y-%m-%d").date()
    if not is_trading_day(td_date):
        log.info(f"非交易日，跳过：{td}")
        return

    stocks = get_stock_list() if stock_codes is None else [(c, "") for c in stock_codes]
    success = fail = skip = 0
    failed_stocks = []
    start_time = time.time()

    log.info(f"=== 增量更新开始 === 日期：{td} 股票数：{len(stocks)}")

    for code, name in stocks:
        c = code.zfill(6)
        rows = read_csv(c)
        local_last_date = rows[-1]["date"] if rows else "2018-01-01"

        # 判断是否需要更新
        if local_last_date >= td:
            skip += 1
            continue

        new_rows = fetch_kline(c, start=local_last_date)
        if new_rows:
            # 只保留 local_last_date 之后的新数据
            new_rows = [r for r in new_rows if r["date"] > local_last_date and not is_anomaly(r)]
            if new_rows:
                append_kline(c, new_rows)
                write_meta(c, name=name, source=new_rows[0].get("source", ""))
                success += 1
        else:
            fail += 1
            failed_stocks.append(c)

    elapsed = time.time() - start_time
    summary = {
        "update_time": datetime.now().isoformat(),
        "trading_date": td,
        "total_stocks": len(stocks),
        "success": success,
        "fail": fail,
        "skip": skip,
        "failed_stocks": failed_stocks[:50],
        "elapsed_seconds": round(elapsed, 1),
        "data_source": "efinance→akshare",
    }
    log.info(f"=== 增量更新完成 === 成功:{success} 失败:{fail} 跳过:{skip} 耗时:{elapsed:.0f}s")
    _save_update_log(summary)
    return summary


def _save_update_log(summary: dict):
    log_file = UPDATE_LOGS / f"kline_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


# ── 盘中实时缓存 ───────────────────────────────────────────────────────────
def write_realtime_cache(data: dict, prefix: str = None):
    """盘中写入实时数据到 cache（不污染历史日K）"""
    prefix = prefix or datetime.now().strftime("%Y%m%d")
    path = REALTIME_CACHE / f"{prefix}_quotes.json"
    cache = {}
    if path.exists():
        with open(path) as f:
            cache = json.load(f)
    # 按 code 覆盖（保留最新）
    for code, item in data.items():
        item["price_time"] = item.get("price_time", datetime.now().strftime("%H:%M"))
        item["update_time"] = datetime.now().isoformat()
        item["source"] = item.get("source", "realtime")
        cache[code] = item
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def read_realtime_cache(prefix: str = None) -> dict:
    prefix = prefix or datetime.now().strftime("%Y%m%d")
    path = REALTIME_CACHE / f"{prefix}_quotes.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


# ── CLI 入口 ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "init"

    if cmd == "init":
        print("全量初始化 A股历史K线（2018-至今）...")
        init_all_stocks()
    elif cmd == "update":
        td = sys.argv[2] if len(sys.argv) > 2 else date.today().strftime("%Y-%m-%d")
        print(f"增量更新 {td} ...")
        incremental_update(trading_date=td)
    elif cmd == "info":
        code = sys.argv[2]
        rows = read_csv(code)
        meta = read_meta(code)
        print(f"股票：{meta.get('name','')} ({code})")
        print(f"记录数：{len(rows)}")
        print(f"起止：{meta.get('first_date','')} → {meta.get('last_date','')}")
        print(f"质量：{meta.get('quality_status','')}")
    else:
        print(f"用法：python kline_data_manager.py [init|update|info]")
