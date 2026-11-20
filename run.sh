#!/usr/bin/env bash
# Start the local implementation_sim service.
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] || { python3 -m venv .venv && ./.venv/bin/pip -q install -r requirements.txt; }
exec ./.venv/bin/uvicorn simserver.main:app --host 127.0.0.1 --port 8420 "$@"
