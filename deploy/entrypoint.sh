#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "bash" ]]; then
  exec bash
fi

exec mathclaw app --host 0.0.0.0 --port "${PORT:-8899}"
