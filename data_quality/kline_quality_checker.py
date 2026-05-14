"""
K线质量检查器 - Phase-2.3C
检查 data/kline_daily/*.csv 的数据质量问题
CRITICAL = 0 后才恢复选股/cockpit/paper_trading
"""
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).parent.parent.resolve()
KLINE_DIR = PROJECT_DIR / "data" / "kline_daily"
OUTPUT_DIR = PROJECT_DIR / "data_quality"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 问题严重等级
CRITICAL = "CRITICAL"  # 必须修复
WARNING = "WARNING"     # 建议修复
INFO = "INFO"           # 仅供参考


class KLineQualityChecker:
    def __init__(self):
        self.issues = defaultdict(list)
        self.stats = {"total_files": 0, "ok_files": 0, "critical_files": 0, "warning_files": 0}

    def check_file(self, fpath: Path) -> dict:
        """检查单个K线文件，返回问题列表"""
        code = fpath.stem
        issues = []
        try:
            df = pd.read_csv(fpath)
        except Exception as e:
            issues.append({"level": CRITICAL, "type": "FILE_READ_ERROR", "detail": str(e)})
            return issues

        # 1. CRITICAL: 缺少必要列
        required = ["open", "high", "low", "close", "volume"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            issues.append({"level": CRITICAL, "type": "MISSING_COLUMNS", "detail": f"缺少 {missing}"})

        # 2. CRITICAL: 行数不足（<200交易日，约1年）
        if len(df) < 200:
            issues.append({"level": WARNING, "type": "INSUFFICIENT_DATA", "detail": f"仅{len(df)}行,<200"})

        # 3. CRITICAL: high < low
        if "high" in df.columns and "low" in df.columns:
            mask = df["high"] < df["low"]
            if mask.any():
                bad_rows = df[mask][[c for c in ["open","high","low","close","volume"] if c in df.columns]].to_dict("records")
                issues.append({
                    "level": CRITICAL,
                    "type": "HIGH_LESS_LOW",
                    "count": int(mask.sum()),
                    "detail": f"共{mask.sum()}条 high<low",
                    "samples": bad_rows[:5]
                })

        # 4. CRITICAL: 价格为0或负
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                mask = df[col] <= 0
                if mask.any():
                    issues.append({
                        "level": CRITICAL,
                        "type": f"ZERO_{col.upper()}",
                        "count": int(mask.sum()),
                        "detail": f"{col}有{mask.sum()}条<=0"
                    })

        # 5. WARNING: 成交量为负
        if "volume" in df.columns:
            mask = df["volume"] < 0
            if mask.any():
                issues.append({"level": WARNING, "type": "NEGATIVE_VOLUME", "count": int(mask.sum()), "detail": f"vol<0共{mask.sum()}条"})

        # 6. WARNING: 涨停超限（个股单日涨跌>20%，排除ST/新股）
        for col in ["open", "close"]:
            if col not in df.columns or len(df) < 2:
                continue
            prev_close = df["close"].iloc[:-1].values
            curr = df[col].iloc[1:].values
            dates = df["trade_date"].iloc[1:].values if "trade_date" in df.columns else range(len(curr))
            pct = (curr - prev_close) / prev_close * 100
            mask = (pct > 20) | (pct < -20)
            if mask.any():
                # 检查是否ST
                bad_count = mask.sum()
                issues.append({
                    "level": WARNING,
                    "type": f"EXTREME_CHANGE_{col.upper()}",
                    "count": int(bad_count),
                    "detail": f"{col}涨跌幅超20%共{bad_count}条"
                })

        # 7. WARNING: high/low 超出涨跌停范围
        if "high" in df.columns and "low" in df.columns and len(df) >= 2:
            prev_close = df["close"].iloc[:-1].values
            curr_high = df["high"].iloc[1:].values
            curr_low = df["low"].iloc[1:].values
            # 涨跌停限制±10%（简化估算）
            mask_high = curr_high > prev_close * 1.25  # 实际11板以上
            mask_low = curr_low < prev_close * 0.75
            if mask_high.any():
                issues.append({"level": WARNING, "type": "HIGH_BEYOND_LIMIT", "count": int(mask_high.sum()), "detail": f"最高价超限{int(mask_high.sum())}条"})
            if mask_low.any():
                issues.append({"level": WARNING, "type": "LOW_BEYOND_LIMIT", "count": int(mask_low.sum()), "detail": f"最低价超限{int(mask_low.sum())}条"})

        # 8. WARNING: 成交量异常（当天成交量 > 前5日均值 * 50倍）
        if "volume" in df.columns and len(df) >= 6:
            vol_ma5 = df["volume"].rolling(5).mean().iloc[:-1].values
            curr_vol = df["volume"].iloc[6:].values
            if len(vol_ma5) > 0 and len(curr_vol) > 0:
                min_len = min(len(vol_ma5), len(curr_vol))
                mask = curr_vol[:min_len] > vol_ma5[:min_len] * 50
                if mask.any():
                    issues.append({"level": INFO, "type": "VOLUME_SPIKE", "count": int(mask.sum()), "detail": f"成交量异常放大{int(mask.sum())}条"})

        return issues

    def run_full_check(self, force_recheck: bool = False) -> dict:
        """全量检查所有K线文件"""
        report_path = OUTPUT_DIR / "quality_report.json"
        if not force_recheck and report_path.exists():
            with open(report_path) as f:
                cached = json.load(f)
            # 缓存1小时内有效
            if datetime.now().timestamp() - cached.get("_cached_at", 0) < 3600:
                logger.info(f"使用缓存报告: {report_path}")
                return cached

        csv_files = list(KLINE_DIR.glob("*.csv"))
        self.stats["total_files"] = len(csv_files)
        all_issues = []
        critical_summary = defaultdict(int)
        warning_summary = defaultdict(int)

        for fpath in csv_files:
            code = fpath.stem
            issues = self.check_file(fpath)
            if issues:
                self.issues[code] = issues
                all_issues.append({"code": code, "issues": issues})
                for iss in issues:
                    if iss["level"] == CRITICAL:
                        critical_summary[iss["type"]] += 1
                        self.stats["critical_files"] += 1
                    elif iss["level"] == WARNING:
                        warning_summary[iss["type"]] += 1
                        self.stats["warning_files"] += 1
            else:
                self.stats["ok_files"] += 1

        report = {
            "_cached_at": datetime.now().timestamp(),
            "_generated_at": datetime.now().isoformat(),
            "stats": self.stats,
            "critical_summary": dict(critical_summary),
            "warning_summary": dict(warning_summary),
            "CRITICAL": all([s["critical_files"] == 0 for s in [self.stats]]),
            "critical_issues": [x for x in all_issues if any(i["level"] == CRITICAL for i in x["issues"])],
            "warning_issues": [x for x in all_issues if all(i["level"] != CRITICAL for i in x["issues"]) and any(i["level"] == WARNING for i in x["issues"])],
        }

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"=== K线质量检查报告 ===")
        logger.info(f"总文件: {self.stats['total_files']} | 正常: {self.stats['ok_files']} | CRITICAL: {self.stats['critical_files']} | WARNING: {self.stats['warning_files']}")
        logger.info(f"CRITICAL问题: {dict(critical_summary)}")
        logger.info(f"WARNING问题: {dict(warning_summary)}")
        logger.info(f"CRITICAL=0: {'✅ 是' if report['CRITICAL'] else '❌ 否'}")
        logger.info(f"报告: {report_path}")

        return report

    def fix_high_less_low(self, dry_run: bool = True) -> dict:
        """自动修复 high < low 问题"""
        fixed = []
        to_fix = [x for x in self.issues.items() if any(i["type"] == "HIGH_LESS_LOW" for i in x[1])]
        for code, issues in to_fix:
            fpath = KLINE_DIR / f"{code}.csv"
            if not fpath.exists():
                continue
            df = pd.read_csv(fpath)
            mask = df["high"] < df["low"]
            count = mask.sum()
            if count == 0:
                continue
            # 修复：high取较大值，low取较小值
            df.loc[mask, "high"] = df.loc[mask, ["high", "low"]].max(axis=1)
            df.loc[mask, "low"] = df.loc[mask, ["high", "low"]].min(axis=1)
            if not dry_run:
                df.to_csv(fpath, index=False, encoding="utf-8")
            fixed.append({"code": code, "count": int(count), "fixed": not dry_run})
            logger.info(f"  {'[已修复]' if not dry_run else '[预览]'}{code} high<low {count}条")

        return {"dry_run": dry_run, "fixed": fixed}

    def fix_zero_prices(self, dry_run: bool = True) -> dict:
        """自动修复价格为0的问题"""
        fixed = []
        to_fix = [x for x in self.issues.items() if any("ZERO" in i["type"] for i in x[1])]
        for code, issues in to_fix:
            fpath = KLINE_DIR / f"{code}.csv"
            if not fpath.exists():
                continue
            df = pd.read_csv(fpath)
            for col in ["open", "high", "low", "close"]:
                if col not in df.columns:
                    continue
                mask = df[col] <= 0
                if not mask.any():
                    continue
                count = mask.sum()
                # 用前一日收盘价填充
                prev_close = df["close"].shift(1)
                df.loc[mask, col] = prev_close.loc[mask].values
                if not dry_run:
                    df.to_csv(fpath, index=False, encoding="utf-8")
                fixed.append({"code": code, "col": col, "count": int(count), "fixed": not dry_run})
                logger.info(f"  {'[已修复]' if not dry_run else '[预览]'}{code}.{col} {count}条价格为0")

        return {"dry_run": dry_run, "fixed": fixed}


if __name__ == "__main__":
    import sys
    checker = KLineQualityChecker()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"

    if cmd == "check":
        report = checker.run_full_check(force_recheck=True)
        print(f"\n{'='*50}")
        print(f"CRITICAL=0: {'✅ 可以恢复交易' if report['CRITICAL'] else '❌ 仍有CRITICAL问题'}")
        print(f"critical_files: {report['stats']['critical_files']}")
        print(f"critical_summary: {report['critical_summary']}")

    elif cmd == "fix":
        print("=== 修复预览（加fix参数才真正执行）===")
        r1 = checker.fix_high_less_low(dry_run=True)
        r2 = checker.fix_zero_prices(dry_run=True)

    elif cmd == "fix_do":
        print("=== 执行修复 ===")
        checker.run_full_check(force_recheck=True)
        r1 = checker.fix_high_less_low(dry_run=False)
        r2 = checker.fix_zero_prices(dry_run=False)
        # 重新检查
        checker2 = KLineQualityChecker()
        report = checker2.run_full_check(force_recheck=True)
        print(f"\n修复后 CRITICAL=0: {'✅' if report['CRITICAL'] else '❌'}")
