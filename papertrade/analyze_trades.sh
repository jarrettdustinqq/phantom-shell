#!/usr/bin/env bash
set -euo pipefail

DATA_PATH="${DATA_PATH:-/data}"
LOG_FILE="${DATA_PATH}/paper_trades.log"

mkdir -p "${DATA_PATH}"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] paper-trade started" >> "${LOG_FILE}"

while true; do
  if [[ -f "${DATA_PATH}/signal_engine.log" ]]; then
    tail -n 5 "${DATA_PATH}/signal_engine.log" >> "${LOG_FILE}"
  else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] waiting for signals" >> "${LOG_FILE}"
  fi
  sleep 60
done
