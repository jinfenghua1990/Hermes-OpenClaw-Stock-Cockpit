#!/usr/bin/env bash
# notify_feishu.sh - 最小飞书通知层
# 仅推送：08:30盘前 / 15:30复盘 / cron_error / RED_ALERT
# 不推送中间过程，不影响主流程

CONFIG="$HOME/project_ai_trading/configs/feishu_webhook.json"
LOG="$HOME/project_ai_trading/cron/logs/notify_feishu.log"

# 读取配置
get_config() {
    local key="$1"
    grep -o "\"${key}\"[[:space:]]*:[[:space:]]*[^,}]*" "$CONFIG" | head -1 | sed 's/.*:.*"\?\([^"]*\)"\?.*/\1/' | tr -d ' '
}

enabled=$(get_config "enabled")
webhook_url=$(get_config "webhook_url")
notify_types=$(grep -o '"notify_types"' "$CONFIG" -A 5 | grep -o '"[^"]*"' | tr -d '"' | tr '\n' ' ')

# 检查开关
if [ "$enabled" != "true" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] disabled, skip" >> "$LOG"
    exit 0
fi

# 检查 webhook_url
if [ -z "$webhook_url" ] || [ "$webhook_url" = "" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] webhook_url empty, skip" >> "$LOG"
    exit 0
fi

# 解析通知类型
notify_type="$1"  # pre_market | daily_review | cron_error | red_alert
shift

# 简单防抖：检查是否在冷却期内（5分钟内同一类型不重复推送）
COOLDOWN=300
CACHE_DIR="$HOME/project_ai_trading/cron/.notify_cache"
mkdir -p "$CACHE_DIR"
CACHE_FILE="$CACHE_DIR/${notify_type}.last"

if [ -f "$CACHE_FILE" ]; then
    last_time=$(cat "$CACHE_FILE")
    now_time=$(date +%s)
    delta=$((now_time - last_time))
    if [ "$delta" -lt "$COOLDOWN" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ${notify_type} cooling down (${delta}s), skip" >> "$LOG"
        exit 0
    fi
fi

# 允许的类型白名单
allowed="pre_market daily_review cron_error red_alert"
if ! echo "$allowed" | grep -qw "$notify_type"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ${notify_type} not in whitelist, skip" >> "$LOG"
    exit 0
fi

# 构建消息
case "$notify_type" in
    pre_market)
        title="📊 盘前报告已生成"
        summary="候选股数量: ${1:-未知} | 时间: $(date '+%Y-%m-%d %H:%M')"
        ;;
    daily_review)
        title="📝 收盘复盘已生成"
        summary="时间: $(date '+%Y-%m-%d %H:%M')"
        ;;
    cron_error)
        title="⚠️ Cron 执行异常"
        summary="错误: $1"
        ;;
    red_alert)
        title="🔴 RED_ALERT"
        summary="告警: $1"
        ;;
esac

# 推送（失败不影响主流程）
payload=$(cat <<PAYLOAD
{
  "msg_type": "text",
  "content": {
    "text": "[Hermes Phase-1.6]\n${title}\n${summary}\n⏰ $(date '+%H:%M:%S')"
  }
}
PAYLOAD
)

response=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d "$(echo "$payload" | tr -d '\n')" \
    --max-time 10 \
    "$webhook_url" 2>&1)
curl_exit=$?

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ${notify_type} curl_exit=${curl_exit} response=${response}" >> "$LOG"

if [ $? -eq 0 ]; then
    date +%s > "$CACHE_FILE"
fi

exit 0
