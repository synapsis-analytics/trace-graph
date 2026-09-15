#!/usr/bin/env bash
# Run the TRACE Graph backend (no reload; use scripts/deploy.sh for the managed environments).
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then set -a; source .env; set +a; fi
PORT="${PORT:-8413}"
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "${PORT}"
