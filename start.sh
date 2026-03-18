#!/bin/bash
# MathClaw one-click launcher
# Starts backend + frontend and auto-stops child processes on exit.

set -u

BACKEND_PORT="${BACKEND_PORT:-6006}"
FRONTEND_PORT="${FRONTEND_PORT:-6008}"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
export MATHCLAW_WORKING_DIR="${MATHCLAW_WORKING_DIR:-$PROJECT_DIR/.mathclaw}"
export MATHCLAW_SECRET_DIR="${MATHCLAW_SECRET_DIR:-$PROJECT_DIR/.mathclaw.secret}"
mkdir -p "$MATHCLAW_WORKING_DIR" "$MATHCLAW_SECRET_DIR" "$PROJECT_DIR/.runtime"

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
        echo "[MathClaw] Warning: neither fuser nor lsof found, skip pre-clean for port ${port}"
    fi
}

cleanup() {
    echo ""
    echo "[MathClaw] Stopping services..."
    [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null && echo "[MathClaw] Backend stopped (PID: $BACKEND_PID)"
    [ -n "${FRONTEND_PID:-}" ] && kill "$FRONTEND_PID" 2>/dev/null && echo "[MathClaw] Frontend stopped (PID: $FRONTEND_PID)"
    wait 2>/dev/null || true
    echo "[MathClaw] All services stopped"
    exit 0
}

trap cleanup EXIT INT TERM HUP

if [ -n "${MATHCLAW_BIN:-}" ] && [ -x "${MATHCLAW_BIN}" ]; then
    MATHCLAW_BIN="$MATHCLAW_BIN"
elif command -v mathclaw >/dev/null 2>&1; then
    MATHCLAW_BIN="$(command -v mathclaw)"
elif [ -x "/root/miniconda3/bin/mathclaw" ]; then
    MATHCLAW_BIN="/root/miniconda3/bin/mathclaw"
else
    echo "[MathClaw] ERROR: mathclaw command not found"
    exit 1
fi

kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"

echo "============================================"
echo "  MathClaw starting..."
echo "  Backend port : $BACKEND_PORT"
echo "  Frontend port: $FRONTEND_PORT"
echo "  Working dir  : $MATHCLAW_WORKING_DIR"
echo "  Secret dir   : $MATHCLAW_SECRET_DIR"
echo "============================================"

cd "$PROJECT_DIR"
"$MATHCLAW_BIN" app --host 127.0.0.1 --port "$BACKEND_PORT" &
BACKEND_PID=$!
echo "[MathClaw] Backend starting (PID: $BACKEND_PID)..."
sleep 3

if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "[MathClaw] ERROR: backend failed to start"
    exit 1
fi

cd "$PROJECT_DIR/console"
npx vite --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort &
FRONTEND_PID=$!
echo "[MathClaw] Frontend starting (PID: $FRONTEND_PID)..."
sleep 2

if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "[MathClaw] ERROR: frontend failed to start"
    exit 1
fi

echo ""
echo "============================================"
echo "  MathClaw started"
echo "  Backend : http://127.0.0.1:$BACKEND_PORT"
echo "  Frontend: http://127.0.0.1:$FRONTEND_PORT"
echo "  Press Ctrl+C to stop all"
echo "============================================"
echo ""

wait -n "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
