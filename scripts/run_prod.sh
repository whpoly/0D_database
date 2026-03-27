#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export ZERO_DB_ENV="${ZERO_DB_ENV:-production}"
export ZERO_DB_DEBUG="${ZERO_DB_DEBUG:-0}"
export ZERO_DB_DEV_TOOLS_UI="${ZERO_DB_DEV_TOOLS_UI:-0}"

exec gunicorn -c gunicorn.conf.py
