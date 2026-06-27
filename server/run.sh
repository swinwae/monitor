#!/usr/bin/env bash
set -e
export MONITOR_DB="${MONITOR_DB:-monitor.db}"
exec uvicorn server.main:app --host 0.0.0.0 --port "${MONITOR_PORT:-8800}"
