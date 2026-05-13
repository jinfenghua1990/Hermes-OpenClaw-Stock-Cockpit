#!/bin/bash
# 安装 cloudflared 并启动 tunnel
# 用法: bash scripts/start_tunnel.sh

set -e

echo "=== Cloudflare Tunnel 安装脚本 ==="

# 1. 检测系统
ARCH=$(uname -m)
SYSTEM=$(uname -s)
echo "System: $SYSTEM $ARCH"

CLOUDFLARED="/tmp/cloudflared"

# 2. 检查是否已有
if [ -f "$CLOUDFLARED" ] && [ -x "$CLOUDFLARED" ]; then
    echo "✅ cloudflared 已安装: $($CLOUDFLARED --version 2>/dev/null | head -1)"
else
    echo "📥 下载 cloudflared..."
    VERSION=$(curl -s https://api.github.com/repos/cloudflare/cloudflared/releases/latest | grep tag_name | cut -d'"' -f4)
    echo "版本: $VERSION"
    
    if [ "$ARCH" = "arm64" ]; then
        ASSET="cloudflared-darwin-arm64.tgz"
    else
        ASSET="cloudflared-darwin-amd64.tgz"
    fi
    
    URL="https://github.com/cloudflare/cloudflared/releases/download/$VERSION/$ASSET"
    echo "下载: $URL"
    
    curl -L -o /tmp/cloudflared.tgz "$URL"
    tar -xzf /tmp/cloudflared.tgz -C /tmp/
    mv /tmp/cloudflared-darwin-*/cloudflared "$CLOUDFLARED" 2>/dev/null || cp /tmp/cloudflared-darwin-*/cloudflared "$CLOUDFLARED"
    chmod +x "$CLOUDFLARED"
    rm -rf /tmp/cloudflared.tgz /tmp/cloudflared-darwin-*
    
    echo "✅ 安装完成: $($CLOUDFLARED --version)"
fi

# 3. 检测 frontend 端口
if lsof -i :3000 >/dev/null 2>&1; then
    PORT=3000
elif lsof -i :5173 >/dev/null 2>&1; then
    PORT=5173
else
    echo "⚠️  未找到运行中的 frontend dev server"
    echo "请先运行: cd ~/project_ai_trading/frontend && npm run dev"
    exit 1
fi

echo "📡 连接到 localhost:$PORT"
echo "🚀 启动 Tunnel (Ctrl+C 停止)..."
echo ""

cloudflared tunnel --url "http://localhost:$PORT"