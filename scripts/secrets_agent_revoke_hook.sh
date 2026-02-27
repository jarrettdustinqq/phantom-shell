#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs"
LOG_FILE="${LOG_DIR}/secrets_agent_revoke_hook.log"

ITEM_ID="${1:-}"
if [[ -z "${ITEM_ID}" ]]; then
  echo "error: missing item_id argument" >&2
  exit 2
fi

mkdir -p "${LOG_DIR}"
printf '{"ts":"%s","action":"revoke-hook","item_id":"%s"}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  "${ITEM_ID}" >> "${LOG_FILE}"
