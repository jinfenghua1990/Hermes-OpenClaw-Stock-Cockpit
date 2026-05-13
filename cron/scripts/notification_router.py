#!/usr/bin/env python3
"""
notification_router.py - Phase-1.6 飞书通知路由
仅允许 4 种通知类型，禁止高频/robot spam/中间过程
"""
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

# ---- 配置 ----
HERMES_GROUP_ID = "oc_174834d2967c4dfbdd692464f85398e0"
REPORTS_BASE = Path.home() / "project_ai_trading" / "reports"
CRON_BASE = Path.home() / "project_ai_trading" / "cron"
CACHE_DIR = CRON_BASE / ".notify_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = Path.home() / "project_ai_trading" / "cron" / "logs" / "notification_router.log"

ALLOWED_TYPES = {"pre_market", "daily_review", "cron_error", "red_alert", "daily_report"}

# ---- 日志 ----
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} [router] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.open("a").write(line + "\n")

# ---- 冷却检查 ----
def in_cooldown(notify_type: str, cooldown: int = 300) -> bool:
    cache_file = CACHE_DIR / f"{notify_type}.last"
    if not cache_file.exists():
        return False
    try:
        last = int(cache_file.read_text().strip())
        delta = int(datetime.now().timestamp()) - last
        return delta < cooldown
    except:
        return False

def mark_sent(notify_type: str):
    (CACHE_DIR / f"{notify_type}.last").write_text(str(int(datetime.now().timestamp())))

# ---- 飞书发消息 ----
def send_feishu(text: str) -> bool:
    try:
        result = subprocess.run(
            ["lark-cli", "im", "+messages-send",
             "--chat-id", HERMES_GROUP_ID,
             "--text", text],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            log(f"✓ sent to Feishu group")
            return True
        else:
            log(f"✗ lark-cli failed: {result.stderr[:200]}")
            return False
    except Exception as e:
        log(f"✗ exception: {e}")
        return False

# ---- 读取系统状态（供消息使用）----
def read_status_summary() -> dict:
    status_file = Path.home() / "project_ai_trading" / "system_monitor" / "system_status.json"
    snapshot_file = Path.home() / "project_ai_trading" / "system_monitor" / "system_snapshot.json"
    summary = {"scheduler": "unknown", "feature_engine": "unknown", "candidate_pool": "?"}
    try:
        if status_file.exists():
            d = json.loads(status_file.read_text())
            summary["scheduler"] = d.get("scheduler", {}).get("status", "unknown")
        if snapshot_file.exists():
            s = json.loads(snapshot_file.read_text())
            summary["feature_engine"] = s.get("data_quality", {}).get("feature_engine", "?")
            summary["candidate_pool"] = s.get("candidate_pool", {}).get("count", "?")
    except:
        pass
    return summary

# ---- 格式化消息 ----
def format_message(notify_type: str, report_path: str = "") -> str:
    ts = datetime.now().strftime("%H:%M")
    status = read_status_summary()

    lines = [f"【Production】"]

    if notify_type == "pre_market":
        lines.append(f"{ts} pre_market_report 已生成")
        lines.append(f"状态：scheduler={status['scheduler']} | feature_engine={status['feature_engine']}")
        lines.append(f"candidate_pool: {status['candidate_pool']}")
        if report_path:
            lines.append(f"文件：reports/pre_market/pre_market_report.json")

    elif notify_type == "daily_review":
        lines.append(f"{ts} daily_review 已生成")
        lines.append(f"状态：scheduler={status['scheduler']} | feature_engine={status['feature_engine']}")
        lines.append(f"candidate_pool: {status['candidate_pool']}")
        if report_path:
            lines.append(f"文件：reports/daily_review/daily_review.json")

    elif notify_type == "cron_error":
        lines.append(f"{ts} ⚠️ cron_error")
        lines.append(f"状态：scheduler={status['scheduler']}")
        if report_path:
            lines.append(f"详情：{report_path}")

    elif notify_type == "red_alert":
        lines.append(f"{ts} 🚨 RED_ALERT")
        lines.append(f"状态：scheduler={status['scheduler']}")
        if report_path:
            lines.append(f"详情：{report_path}")

    return "\n".join(lines)

# ---- 读取日报文件内容 ----
def read_daily_report_content(report_type: str) -> str:
    """读取日报内容用于发送"""
    ts = datetime.now().strftime("%Y-%m-%d")
    report_paths = {
        "pre_market": REPORTS_BASE / "pre_market" / f"pre_market_report_{ts}.json",
        "daily_review": REPORTS_BASE / "daily_review" / f"daily_review_{ts}.json",
    }
    path = report_paths.get(report_type)
    if path and path.exists():
        try:
            data = json.loads(path.read_text())
            return json.dumps(data, ensure_ascii=False, indent=2)
        except:
            return f"[{report_type}] 报告文件读取失败"
    return f"[{report_type}] 报告文件不存在: {path}"

# ---- 发送日报到飞书 ----
def send_daily_report_to_feishu(report_type: str) -> bool:
    """
    发送日报摘要到飞书群
    report_type: pre_market | daily_review
    """
    log(f"send_daily_report_to_feishu called with type={report_type}")

    # 冷却检查
    cooldown_map = {"pre_market": 300, "daily_review": 300}
    cooldown = cooldown_map.get(report_type, 300)
    if in_cooldown(report_type, cooldown):
        log(f"{report_type} 冷却中 ({cooldown}s)，跳过")
        return False

    # 读取报告内容
    report_content = read_daily_report_content(report_type)

    # 截断过长内容（飞书限制）
    max_len = 4000
    if len(report_content) > max_len:
        report_content = report_content[:max_len] + "\n...(内容已截断)"

    # 格式化消息
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg_lines = [
        f"【Production Daily Report】",
        f"⏰ {ts}",
        f"📊 类型: {report_type}",
        f"```",
        report_content,
        f"```",
    ]
    msg = "\n".join(msg_lines)

    # 发送
    sent_ok = send_feishu(msg)
    if sent_ok:
        mark_sent(report_type)
        log(f"✓ {report_type} 日报已发送到飞书")
    else:
        log(f"✗ {report_type} 日报发送失败")

    # 更新 delivery status
    update_delivery_status(report_type, sent_ok)

    return sent_ok

# ---- 更新交付状态文件 ----
def update_delivery_status(report_type: str, success: bool):
    """更新 reports/report_delivery_status.json"""
    status_file = REPORTS_BASE / "report_delivery_status.json"
    try:
        if status_file.exists():
            data = json.loads(status_file.read_text())
        else:
            data = {"reports": {}, "delivery_history": []}
    except:
        data = {"reports": {}, "delivery_history": []}

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "timestamp": now,
        "report_type": report_type,
        "status": "success" if success else "error",
    }

    if report_type not in data.get("reports", {}):
        data["reports"][report_type] = {
            "enabled": True,
            "last_sent": "",
            "last_status": "pending",
            "delivery_count": 0
        }

    data["reports"][report_type]["last_sent"] = now
    data["reports"][report_type]["last_status"] = "success" if success else "error"
    data["reports"][report_type]["delivery_count"] = \
        data["reports"][report_type].get("delivery_count", 0) + (1 if success else 0)

    data["last_updated"] = now
    data.setdefault("delivery_history", []).append(entry)
    # 保留最近 100 条历史
    data["delivery_history"] = data["delivery_history"][-100:]

    status_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    log(f"delivery status updated for {report_type}")

# ---- 主逻辑 ----
def main():
    if len(sys.argv) < 2:
        print("Usage: notification_router.py <pre_market|daily_review|cron_error|red_alert> [detail]")
        sys.exit(1)

    notify_type = sys.argv[1]
    detail = sys.argv[2] if len(sys.argv) > 2 else ""

    # 类型白名单校验
    if notify_type not in ALLOWED_TYPES:
        log(f"类型 {notify_type} 不在白名单，跳过")
        sys.exit(0)

    # 冷却检查
    if in_cooldown(notify_type):
        log(f"{notify_type} 冷却中，跳过")
        sys.exit(0)

    # 禁止：heartbeat / rolling_snapshot
    if notify_type in ("heartbeat", "rolling_snapshot"):
        log(f"{notify_type} 禁止推送，跳过")
        sys.exit(0)

    # 构建消息
    msg = format_message(notify_type, detail)

    # 发送
    sent_ok = send_feishu(msg)
    if sent_ok:
        mark_sent(notify_type)
        log(f"✓ {notify_type} 通知已发送")
    else:
        log(f"✗ {notify_type} 发送失败")

    # Runtime Event
    try:
        sys.path.insert(0, str(CRON_BASE))
        from runtime_events.runtime_event_logger import log_event
        log_event(
            module="notification_router",
            layer="execution_layer",
            status="success" if sent_ok else "error",
            message=f"{notify_type} notification sent={sent_ok}",
        )
    except ImportError:
        pass

if __name__ == "__main__":
    main()
