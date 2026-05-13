#!/bin/bash
# ============================================================
# log_event - shell 脚本用的 Runtime Event 写入工具
# 用法:
#   log_event <module> <layer> <status> <message> [runtime_ms]
#
#   带计时:
#   start=$(date +%s%3N)
#   ... 执行命令 ...
#   end=$(date +%s%3N)
#   log_event "OpenClaw" "execution_layer" "success" "data fetched" $((end-start))
#
#   自动推断 layer (传 auto):
#   log_event "OpenClaw" "auto" "success" "data fetched"
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

function log_event() {
    local module="$1"
    local layer="${2:-auto}"
    local status="${3:-running}"
    local message="${4:-}"
    local runtime_ms="${5:-}"

    if [ -n "$runtime_ms" ]; then
        python3 "${SCRIPT_DIR}/runtime_event_logger.py" "$module" "$layer" "$status" "$message" "$runtime_ms"
    else
        python3 "${SCRIPT_DIR}/runtime_event_logger.py" "$module" "$layer" "$status" "$message"
    fi
}

# 作为独立脚本直接调用
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [ $# -lt 3 ]; then
        echo "用法: log_event.sh <module> <layer> <status> <message> [runtime_ms]"
        exit 1
    fi
    log_event "$@"
fi
