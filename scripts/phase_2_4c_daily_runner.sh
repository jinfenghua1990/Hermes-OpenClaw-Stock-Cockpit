#!/bin/bash
# ============================================================
# Phase-2.4C 每日稳定性观察脚本
# 每个交易日 17:00 执行
# ============================================================
set -euo pipefail

BASE_DIR="$HOME/project_ai_trading"
cd "$BASE_DIR"

TODAY=$(date +%Y-%m-%d)
LOG="reports/phase_2_4c/daily/${TODAY}.log"
TRACKER="system_health/stability_tracker.py"

mkdir -p reports/phase_2_4c/daily

echo "============================================" | tee -a "$LOG"
echo "Phase-2.4C Daily Runner — $TODAY" | tee -a "$LOG"
echo "============================================" | tee -a "$LOG"

# ── Step 1: git pull ────────────────────────────────────
echo "[1/7] git pull..." | tee -a "$LOG"
git pull origin main 2>&1 | tee -a "$LOG" || true

# ── Step 2: daily_pipeline ──────────────────────────────
echo "[2/7] daily_pipeline..." | tee -a "$LOG"
if [ -f "scripts/daily_pipeline.sh" ]; then
    bash scripts/daily_pipeline.sh 2>&1 | tee -a "$LOG" || echo "⚠️  daily_pipeline 执行异常" | tee -a "$LOG"
else
    echo "⚠️  daily_pipeline.sh 不存在，跳过" | tee -a "$LOG"
fi

# ── Step 3: daily_health_check ──────────────────────────
echo "[3/7] daily_health_check..." | tee -a "$LOG"
python3 system_health/daily_health_check.py 2>&1 | tee -a "$LOG" || echo "⚠️  daily_health_check 执行异常" | tee -a "$LOG"

# ── Step 4: rolling_snapshot ────────────────────────────
echo "[4/7] rolling_snapshot..." | tee -a "$LOG"
python3 cron/scripts/rolling_snapshot.py 2>&1 | tee -a "$LOG" || echo "⚠️  rolling_snapshot 执行异常" | tee -a "$LOG"

# ── Step 5: generate_daily_report ───────────────────────
echo "[5/7] generate_daily_report..." | tee -a "$LOG"
python3 report_engine/generators/generate_daily_report.py 2>&1 | tee -a "$LOG" || echo "⚠️  generate_daily_report 执行异常" | tee -a "$LOG"

# ── Step 6: stability_tracker 记录 ─────────────────────
echo "[6/7] stability_tracker..." | tee -a "$LOG"
python3 "$TRACKER" 2>&1 | tee -a "$LOG" || echo "⚠️  stability_tracker 执行异常" | tee -a "$LOG"

# ── Step 7: git push ────────────────────────────────────
echo "[7/7] git push..." | tee -a "$LOG"
git add reports/ system_monitor/ runtime_events/ dashboard/ 2>/dev/null || true
git add system_health/history/ system_health/stability_tracker.json 2>/dev/null || true
if git diff --cached --quiet; then
    echo "无变更，跳过 commit" | tee -a "$LOG"
else
    git commit -m "phase-2.4c daily: $TODAY" --no-verify 2>&1 | tee -a "$LOG" || true
    git push origin main 2>&1 | tee -a "$LOG" || true
fi

echo "============================================" | tee -a "$LOG"
echo "Phase-2.4C Daily Runner — $TODAY 完成" | tee -a "$LOG"
echo "============================================" | tee -a "$LOG"
