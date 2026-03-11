#!/bin/bash
# ResearchClaw 一键启动脚本
# 启动前后端，Ctrl+C 或关闭终端时自动停掉所有子进程

BACKEND_PORT=6006
FRONTEND_PORT=6008
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
    echo ""
    echo "[ResearchClaw] 正在停止所有服务..."
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null && echo "[ResearchClaw] 后端已停止 (PID: $BACKEND_PID)"
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null && echo "[ResearchClaw] 前端已停止 (PID: $FRONTEND_PID)"
    wait 2>/dev/null
    echo "[ResearchClaw] 全部服务已关闭"
    exit 0
}

trap cleanup EXIT INT TERM HUP

# 先清理可能残留的旧进程
fuser -k "$BACKEND_PORT/tcp" 2>/dev/null
fuser -k "$FRONTEND_PORT/tcp" 2>/dev/null

echo "============================================"
echo "  ResearchClaw 启动中..."
echo "  后端端口: $BACKEND_PORT"
echo "  前端端口: $FRONTEND_PORT"
echo "============================================"

# 启动后端
cd "$PROJECT_DIR"
researchclaw app --host 0.0.0.0 --port "$BACKEND_PORT" &
BACKEND_PID=$!
echo "[ResearchClaw] 后端启动中 (PID: $BACKEND_PID)..."
sleep 3

# 启动前端
cd "$PROJECT_DIR/console"
npx vite --host 0.0.0.0 --port "$FRONTEND_PORT" &
FRONTEND_PID=$!
echo "[ResearchClaw] 前端启动中 (PID: $FRONTEND_PID)..."
sleep 2

echo ""
echo "============================================"
echo "  ResearchClaw 已启动!"
echo "  后端: http://0.0.0.0:$BACKEND_PORT"
echo "  前端: http://0.0.0.0:$FRONTEND_PORT"
echo "  按 Ctrl+C 停止所有服务"
echo "============================================"
echo ""

# 等待任一子进程退出
wait -n "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
