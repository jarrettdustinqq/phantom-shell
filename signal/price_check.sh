#!/usr/bin/env bash
set -euo pipefail

DATA_PATH="${DATA_PATH:-/data}"
CONFIG_PATH="${CONFIG_PATH:-/config}"

mkdir -p "${DATA_PATH}" "${CONFIG_PATH}"

LOG_FILE="${DATA_PATH}/signal_engine.log"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] signal-engine started" >> "${LOG_FILE}"

# Placeholder loop for existing price_check/adaptive_tune logic.
while true; do
  if [[ -f "${DATA_PATH}/btcusdt_klines.csv" ]]; then
    tail -n 1 "${DATA_PATH}/btcusdt_klines.csv" >> "${LOG_FILE}"
  else
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] waiting for collector data" >> "${LOG_FILE}"
  fi
  sleep 30
done
