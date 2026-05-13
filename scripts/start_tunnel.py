#!/usr/bin/env python3
"""
Cockpit Tunnel - 轻量内网穿透
将 localhost:3000 暴露给外网

使用 Python 实现，不依赖外部二进制
原理: 使用 ngrok/bore/cloudflared 的 API 创建隧道

注意: 需要有可用的 tunnel 服务端
如果所有隧道服务都网络不通，请改用:
  - 手机和电脑在同一 WiFi 下，直接访问电脑 IP:3000
  - 或配置路由器端口映射
"""
import subprocess, time, json, sys, os

def get_local_ip():
    """获取本机局域网IP"""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(2)
    try:
        s.connect(("192.168.1.1", 80))
        ip = s.getsockname()[0]
    except:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def check_port(port):
    """检查端口是否开放"""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    r = s.connect_ex(('localhost', port))
    s.close()
    return r == 0

def main():
    print("=== Cockpit Tunnel 启动器 ===")
    print()
    
    # 检测 frontend 端口
    port = None
    for p in [3000, 5173, 5174]:
        if check_port(p):
            port = p
            break
    
    if not port:
        print("❌ 未找到运行中的 Cockpit UI")
        print("请先运行: cd ~/project_ai_trading/frontend && npm run dev")
        return
    
    print(f"✅ Cockpit UI 检测到: localhost:{port}")
    
    local_ip = get_local_ip()
    print(f"📡 局域网访问: http://{local_ip}:{port}")
    print()
    
    # 检查网络连通性
    print("🔍 检查 tunnel 服务可用性...")
    
    # 尝试的 tunnel 服务
    services = [
        ("cloudflared", "https://github.com/cloudflare/cloudflared/releases"),
        ("ngrok", "https://ngrok.com"),
        ("localtunnel", "https://localtunnel.me"),
    ]
    
    for name, url in services:
        r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', 
                          '--connect-timeout', '3', url],
                          capture_output=True, text=True, timeout=5)
        status = r.stdout.strip()
        if status == '200':
            print(f"  ✅ {name} 可访问 (HTTP {status})")
        else:
            print(f"  ❌ {name} 不可用 (HTTP {status})")
    
    print()
    print("=" * 50)
    print("建议:")
    print()
    print("1. 【推荐】手机和电脑在同一 WiFi 下:")
    print(f"   手机浏览器访问: http://{local_ip}:{port}")
    print()
    print("2. 使用 cloudflared (需安装):")
    print("   brew install cloudflared")
    print(f"   cloudflared tunnel --url http://localhost:{port}")
    print()
    print("3. 使用 ngrok (需注册):")
    print(f"   ngrok http {port}")
    print()
    print("=" * 50)
    
    # 检查是否有已安装的 tunnel 工具
    for binary in ['/opt/homebrew/bin/cloudflared', '/usr/local/bin/cloudflared',
                   '/opt/homebrew/bin/ngrok', '/usr/local/bin/ngrok']:
        if os.path.exists(binary):
            print(f"✅ 找到: {binary}")
            try:
                r = subprocess.run([binary, '--version'], capture_output=True, text=True, timeout=5)
                print(f"   版本: {r.stdout.strip()}")
            except:
                pass

if __name__ == '__main__':
    main()
