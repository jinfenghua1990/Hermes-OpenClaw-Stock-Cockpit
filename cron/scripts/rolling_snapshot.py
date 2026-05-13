#!/usr/bin/env python3
"""rolling_snapshot.py - Phase-1.6 Rolling Snapshot (30min)
交易时段 09:30/10:00/10:30/11:00/13:00/13:30/14:00/14:30/15:00 执行。
Pipeline: OpenClaw → Feature Engine → Data Quality → Candidate Pool → Strategy Match → Risk Check → Snapshot
输出: system_monitor/system_snapshot.json（结构化摘要，不生成长文本）
不调用大模型或极少量调用。
"""
import json, subprocess, sys, re
from pathlib import Path
from datetime import datetime

BASE = Path.home() / "project_ai_trading"
SNAPSHOT_FILE = BASE / "system_monitor" / "system_snapshot.json"
LOG_FILE = BASE / "system_monitor" / "rolling_snapshot.log"
CANDIDATE_FILE = BASE / "configs" / "candidate_stocks.json"
OPENCLAW_RAW = BASE / "data" / "openclaw_raw"
CACHE_DIR = BASE / "cache"

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg):
    ts = now_str()
    print(f"[{ts}] {msg}")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

log("开始 Rolling Snapshot")

# ── 1. OpenClaw 数据状态 ────────────────────────────────────
raw_files = sorted(OPENCLAW_RAW.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if OPENCLAW_RAW.exists() else []
latest_raw = raw_files[0] if raw_files else None

if latest_raw:
    raw_age = (datetime.now().timestamp() - latest_raw.stat().st_mtime) / 60
    raw_count = len(raw_files)
    log(f"OpenClaw raw: {latest_raw.name}, {raw_count} files, age={raw_age:.1f}min")
else:
    raw_age = None
    raw_count = 0
    log("OpenClaw raw: 无数据")

# ── 2. Feature Engine 状态 ────────────────────────────────────
feature_dir = BASE / "data" / "features"
feature_files = sorted(feature_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if feature_dir.exists() else []
latest_feature = feature_files[0] if feature_files else None

if latest_feature:
    feature_age = (datetime.now().timestamp() - latest_feature.stat().st_mtime) / 60
    feature_count = len(feature_files)
    log(f"Feature Engine: {latest_feature.name}, {feature_count} files, age={feature_age:.1f}min")
else:
    feature_age = None
    feature_count = 0
    log("Feature Engine: 无数据")

# ── 3. Candidate Pool ────────────────────────────────────
if CANDIDATE_FILE.exists():
    try:
        cand_data = json.loads(CANDIDATE_FILE.read_text(encoding="utf-8"))
        candidate_stocks = cand_data.get("stocks", cand_data.get("candidates", []))
        log(f"Candidate Pool: {len(candidate_stocks)} 只候选")
    except:
        candidate_stocks = []
        log("Candidate Pool: 解析失败")
else:
    candidate_stocks = []
    log("Candidate Pool: 文件不存在")

# ── 4. Strategy Match（从 latest intraday/pre_market 读取） ──
report_files = []
for subdir in ["pre_market", "intraday", "daily_review"]:
    rdir = BASE / "reports" / subdir
    if rdir.exists():
        report_files.extend(rdir.glob("*.json"))

latest_report = sorted(report_files, key=lambda p: p.stat().st_mtime, reverse=True)[0] if report_files else None

strategy_summary = {"matched": 0, "details": []}
if latest_report:
    try:
        report = json.loads(latest_report.read_text(encoding="utf-8"))
        matched_stocks = report.get("candidate_stocks", [])
        strategy_summary["matched"] = len(matched_stocks)
        strategy_summary["latest_report"] = latest_report.name
        strategy_summary["latest_report_time"] = report.get("timestamp", "N/A")
        # 取前3只作为快照摘要
        top = []
        for s in matched_stocks[:3]:
            top.append({
                "code": s.get("stock_code", ""),
                "name": s.get("stock_name", ""),
                "rsi": s.get("indicators", {}).get("RSI", 0),
                "量比": s.get("indicators", {}).get("量比", 0)
            })
        strategy_summary["top_candidates"] = top
        log(f"Strategy Match: {len(matched_stocks)} 只命中")
    except Exception as e:
        log(f"Strategy Match: 解析报告失败 {e}")
else:
    log("Strategy Match: 无报告文件")

# ── 5. Risk Check ────────────────────────────────────
risk_rules_file = BASE / "configs" / "risk_rules.json"
risk_flags = []
if risk_rules_file.exists():
    try:
        rules = json.loads(risk_rules_file.read_text(encoding="utf-8"))
        # 简单风险标志提取
        if rules.get("max_positions"):
            risk_flags.append(f"max_positions={rules['max_positions']}")
        if rules.get("stop_loss"):
            risk_flags.append(f"stop_loss={rules['stop_loss']}")
        log(f"Risk Check: {len(risk_flags)} 规则加载")
    except:
        risk_flags = ["risk_rules解析失败"]
else:
    risk_flags = ["risk_rules不存在"]

# ── 6. Data Quality ────────────────────────────────────
quality = {
    "openclaw_raw_freshness_min": round(raw_age, 1) if raw_age else None,
    "feature_engine_freshness_min": round(feature_age, 1) if feature_age else None,
    "candidate_pool_count": len(candidate_stocks),
    "strategy_matched_count": strategy_summary["matched"],
    "report_available": latest_report is not None,
    "openclaw_file_count": raw_count,
    "feature_file_count": feature_count
}

if raw_age and raw_age > 120:
    quality["alert"] = "openclaw数据超过2小时未更新"
elif feature_age and feature_age > 120:
    quality["alert"] = "feature数据超过2小时未更新"
else:
    quality["alert"] = None

# ── 7. 构建 Snapshot ────────────────────────────────────
snapshot = {
    "report_type": "rolling_snapshot",
    "timestamp": now_str(),
    "phase": "Phase-1.6 OBSERVE_ONLY",
    "data_quality": quality,
    "candidate_pool": {
        "count": len(candidate_stocks),
        "source": "configs/candidate_stocks.json"
    },
    "strategy_match": strategy_summary,
    "risk_check": {
        "flags": risk_flags,
        "status": "规则已加载" if risk_flags else "无规则"
    },
    "trade_reference": {
        "description": "此快照不作为交易依据",
        "official_reports": [
            "reports/pre_market/pre_market_report.json (08:30)",
            "reports/intraday/intraday_signal_am.json / intraday_signal_pm.json",
            "reports/daily_review/daily_review.json (15:30)"
        ]
    },
    "prohibited": [
        "自动交易", "自动调仓", "strategy_positions写入",
        "baseline修改", "自动学习", "将snapshot作为交易依据"
    ]
}

SNAPSHOT_FILE.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
log(f"Snapshot 已写入: {SNAPSHOT_FILE.name}")

# Runtime Event
import time as _time
_snap_start = _time.time()
import sys as _sys
_sys.path.insert(0, str(BASE))
try:
    from runtime_events.runtime_event_logger import log_event
    qual_alert = quality.get("alert")
    log_event(
        module="rolling_snapshot",
        layer="cockpit_layer",
        status="warning" if qual_alert else "success",
        message=f"snapshot: candidates={len(candidate_stocks)}, matched={strategy_summary['matched']}" + (f" | {qual_alert}" if qual_alert else ""),
        runtime_ms=int((_time.time()-_snap_start)*1000),
    )
except ImportError:
    pass
