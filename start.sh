#!/bin/bash
# ResearchClaw one-click launcher
# Starts backend + frontend and auto-stops child processes on exit.

set -u

BACKEND_PORT=6006
FRONTEND_PORT=6008
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

kill_port() {
    local port="$1"
    if command -v fuser >/dev/null 2>&1; then
        fuser -k "${port}/tcp" 2>/dev/null || true
    elif command -v lsof >/dev/null 2>&1; then
        local pids
        pids="$(lsof -ti "tcp:${port}" 2>/dev/null || true)"
        if [ -n "$pids" ]; then
            kill $pids 2>/dev/null || true
        fi
    else
        echo "[ResearchClaw] Warning: neither fuser nor lsof found, skip pre-clean for port ${port}"
    fi
}

cleanup() {
    echo ""
    echo "[ResearchClaw] Stopping services..."
    [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null && echo "[ResearchClaw] Backend stopped (PID: $BACKEND_PID)"
    [ -n "${FRONTEND_PID:-}" ] && kill "$FRONTEND_PID" 2>/dev/null && echo "[ResearchClaw] Frontend stopped (PID: $FRONTEND_PID)"
    wait 2>/dev/null || true
    echo "[ResearchClaw] All services stopped"
    exit 0
}

trap cleanup EXIT INT TERM HUP

if command -v researchclaw >/dev/null 2>&1; then
    RESEARCHCLAW_BIN="$(command -v researchclaw)"
elif [ -x "/root/miniconda3/bin/researchclaw" ]; then
    RESEARCHCLAW_BIN="/root/miniconda3/bin/researchclaw"
else
    echo "[ResearchClaw] ERROR: researchclaw command not found"
    exit 1
fi

# Clean potential stale port holders first
kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"

echo "============================================"
echo "  ResearchClaw starting..."
echo "  Backend port : $BACKEND_PORT"
echo "  Frontend port: $FRONTEND_PORT"
echo "============================================"

# Start backend
cd "$PROJECT_DIR"
"$RESEARCHCLAW_BIN" app --host 0.0.0.0 --port "$BACKEND_PORT" &
BACKEND_PID=$!
echo "[ResearchClaw] Backend starting (PID: $BACKEND_PID)..."
sleep 3

if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "[ResearchClaw] ERROR: backend failed to start"
    exit 1
fi

# Start frontend
cd "$PROJECT_DIR/console"
npx vite --host 0.0.0.0 --port "$FRONTEND_PORT" --strictPort &
FRONTEND_PID=$!
echo "[ResearchClaw] Frontend starting (PID: $FRONTEND_PID)..."
sleep 2

if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "[ResearchClaw] ERROR: frontend failed to start"
    exit 1
fi

echo ""
echo "============================================"
echo "  ResearchClaw started"
echo "  Backend : http://0.0.0.0:$BACKEND_PORT"
echo "  Frontend: http://0.0.0.0:$FRONTEND_PORT"
echo "  Press Ctrl+C to stop all"
echo "============================================"
echo ""

# Wait until one process exits
wait -n "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null

