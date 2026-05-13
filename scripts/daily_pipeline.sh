#!/bin/bash

echo "=================================================="
echo "[START] Hermes Daily Pipeline"
echo "=================================================="

# 设置工作目录
cd "$(dirname "$0")/.." || exit 1
CRON_BASE="/Users/gino/project_ai_trading"

# 创建日志目录
mkdir -p logs

# 记录开始时间
START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
echo "[TIME] Pipeline started at: $START_TIME"

# 1. 构建技术因子缓存
echo "[1/6] Build Technical Factor Cache"
python features/build_technical_factor_cache.py
if [ $? -ne 0 ]; then
    echo "[ERROR] Technical Factor Cache failed"
    exit 1
fi

# 2. 运行原版四种模式扫描器
echo "[2/6] Run Original Four Modes Scanner"
python strategies/original_four_modes_scanner.py
if [ $? -ne 0 ]; then
    echo "[ERROR] Four Modes Scanner failed"
    exit 1
fi

# 3. 构建市场情绪快照
echo "[3/6] Build Market Emotion Snapshot"
python emotion_engine/build_market_emotion_snapshot.py
if [ $? -ne 0 ]; then
    echo "[WARNING] Market Emotion Snapshot failed, continuing with pipeline"
fi

# 4. 分析情绪历史
echo "[4/6] Analyze Emotion History"
python emotion_engine/analyzer/analyze_emotion_history.py
if [ $? -ne 0 ]; then
    echo "[WARNING] Emotion History Analyzer failed, continuing with pipeline"
fi

# 5. 构建市场摘要
echo "[5/6] Build Market Summary"
python report_engine/generators/build_market_summary.py
if [ $? -ne 0 ]; then
    echo "[ERROR] Market Summary failed"
    exit 1
fi

# 6. 生成日报
echo "[6/6] Generate Daily Report"
python report_engine/generators/generate_daily_report.py
if [ $? -ne 0 ]; then
    echo "[ERROR] Daily Report failed"
    exit 1
fi

# 7. 归档历史日报
echo "[7/7] Archive Historical Reports"
mkdir -p reports/history
cp report_engine/outputs/*.md reports/history/ 2>/dev/null || echo "[WARNING] No reports to copy"
echo "[ARCHIVE] Daily reports archived to reports/history/"

# 8. 更新日报索引
echo "[8/8] Update Report Index"
python reports/build_report_index.py
if [ $? -ne 0 ]; then
    echo "[WARNING] Report index update failed"
fi

# 9. 发送日报到飞书
echo "[9/9] Send Daily Report to Feishu"
python3 "${CRON_BASE}/cron/scripts/notification_router.py" daily_report pre_market 2>/dev/null || echo "[WARNING] Feishu notification skipped"

# 记录结束时间
END_TIME=$(date '+%Y-%m-%d %H:%M:%S')
echo "[TIME] Pipeline finished at: $END_TIME"

echo "=================================================="
echo "[DONE] Hermes Daily Pipeline Finished"
echo "=================================================="

# 输出文件列表
echo "[FILES] Generated files:"
echo "  - features/cache/daily_technical_factors.json"
echo "  - strategies/outputs/original_four_modes_$(date '+%Y-%m-%d').json"
echo "  - emotion_engine/cache/market_emotion_snapshot.json"
echo "  - emotion_engine/history/$(date '+%Y-%m-%d').json"
echo "  - emotion_engine/analyzer/emotion_history_analysis.json"
echo "  - report_engine/data/market_summary.json"
echo "  - report_engine/outputs/$(date '+%Y-%m-%d').md"
echo "  - reports/history/$(date '+%Y-%m-%d').md"
echo "  - reports/history/index.json"

# Runtime Event
python3 -c "
import sys
sys.path.insert(0, '/Users/gino/project_ai_trading')
from runtime_events.runtime_event_logger import log_event
log_event('daily_pipeline', 'execution_layer', 'success', 'daily pipeline completed 8 steps')
print('event logged')
" 2>/dev/null || echo '[WARNING] Runtime event not logged'