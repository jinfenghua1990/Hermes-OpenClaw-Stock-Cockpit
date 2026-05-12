"""
K线数据质量检查脚本
Phase-2.3B

用法：
  python kline_data_guard.py check              # 全量检查
  python kline_data_guard.py check 000001       # 检查单只
  python kline_data_guard.py clean              # 清理重复数据
"""

import csv
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

DATA_HOME = Path("/Users/gino/project_ai_trading/data")
KLINE_DAILY = DATA_HOME / "kline_daily"
DATA_QUALITY = DATA_HOME / "data_quality"
TRADING_CALENDAR = DATA_HOME / "trading_calendar.csv"
FIELDS = ["code", "date", "open", "high", "low", "close",
          "volume", "amount", "turnover", "source", "adjust", "update_time"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("kline_guard")


def load_calendar() -> set[str]:
    holidays = set()
    if TRADING_CALENDAR.exists():
        with open(TRADING_CALENDAR) as f:
            for row in csv.DictReader(f):
                if row["is_trading_day"] == "False":
                    holidays.add(row["date"])
    return holidays


def check_stock(code: str, holidays: set[str]) -> list[dict]:
    """检查单只股票K线数据质量"""
    path = KLINE_DAILY / f"{code.zfill(6)}.csv"
    anomalies = []
    if not path.exists():
        return [{"code": code, "type": "file_missing", "severity": "HIGH",
                 "detail": "CSV文件不存在"}]

    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, fieldnames=FIELDS)
        for row in reader:
            rows.append(row)

    # 1. 重复日期
    dates = [r["date"] for r in rows]
    seen = {}
    for r in rows:
        d = r["date"]
        if d in seen:
            anomalies.append({"code": code, "type": "duplicate_date",
                             "severity": "MEDIUM",
                             "detail": f"重复日期 {d}，保留update_time最新的",
                             "row_date": d})
        seen[d] = r

    # 2. OHLC异常
    for r in rows:
        try:
            o, h, l, c = float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])
            v = float(r["volume"])
            if h < l:
                anomalies.append({"code": code, "type": "ohlc_abnormal",
                                 "severity": "CRITICAL",
                                 "detail": f"high({h}) < low({l})",
                                 "row_date": r["date"]})
            if c <= 0:
                anomalies.append({"code": code, "type": "ohlc_abnormal",
                                 "severity": "CRITICAL",
                                 "detail": f"close({c}) <= 0",
                                 "row_date": r["date"]})
            if v < 0:
                anomalies.append({"code": code, "type": "volume_abnormal",
                                 "severity": "CRITICAL",
                                 "detail": f"volume({v}) < 0",
                                 "row_date": r["date"]})
        except (ValueError, KeyError) as e:
            anomalies.append({"code": code, "type": "parse_error",
                             "severity": "HIGH",
                             "detail": str(e), "row_date": r.get("date", "?")})

    # 3. 涨跌幅超限（A股涨停板10%/20%为主，44%为新股上限）
    for r in rows:
        try:
            pct = float(r.get("turnover", 0))
            if abs(pct) > 20.5:  # 主板10%/20%，科创创业44%
                anomalies.append({"code": code, "type": "pct_abnormal",
                                 "severity": "HIGH",
                                 "detail": f"涨跌幅{pct}% 超出正常范围",
                                 "row_date": r["date"]})
        except ValueError:
            pass

    return anomalies


def run_full_check() -> dict:
    """全量检查所有股票"""
    files = list(KLINE_DAILY.glob("*.csv"))
    total = len(files)
    holidays = load_calendar()
    all_anomalies = []
    start_time = time.time()

    log.info(f"=== K线数据质量检查开始 === 检查：{total} 只股票")

    for i, f in enumerate(files, 1):
        code = f.stem
        anomalies = check_stock(code, holidays)
        all_anomalies.extend(anomalies)
        if anomalies and len(anomalies) <= 3:
            for a in anomalies:
                log.warning(f"  {code}: {a['type']} - {a['detail']}")
        if i % 500 == 0:
            log.info(f"  进度：{i}/{total}")

    elapsed = time.time() - start_time
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "OK": total}
    for a in all_anomalies:
        counts[a["severity"]] += 1
    counts["OK"] = max(0, total - sum(v for k, v in counts.items() if k != "OK"))

    result = {
        "check_time": datetime.now().isoformat(),
        "total_stocks_checked": total,
        "anomalies": all_anomalies[:100],  # 只保留前100条
        "summary": counts,
        "elapsed_seconds": round(elapsed, 1),
    }

    out_path = DATA_QUALITY / f"{datetime.now().strftime('%Y%m%d')}_quality_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    log.info(f"=== 检查完成 === 正常:{counts['OK']} 异常:{len(all_anomalies)} 耗时:{elapsed:.0f}s")
    log.info(f"报告已保存：{out_path}")
    return result


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    code = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "check":
        if code:
            result = {"anomalies": check_stock(code, load_calendar())}
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            run_full_check()
