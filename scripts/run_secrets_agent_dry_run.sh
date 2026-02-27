#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.loop-agent/secrets-agent.env"
AGENT="${ROOT_DIR}/secrets_agent.py"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "error: missing env file at ${ENV_FILE}" >&2
  echo "create it first (local-only, not tracked)." >&2
  exit 2
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

STATUS_JSON="${TMP_DIR}/status.json"
PLAN_JSON="${TMP_DIR}/plan.json"
EXEC_JSON="${TMP_DIR}/exec.json"

python3 "${AGENT}" --backend "${SECRETS_AGENT_BACKEND:-mock}" status | tee "${STATUS_JSON}"
python3 "${AGENT}" --backend "${SECRETS_AGENT_BACKEND:-mock}" rotate-plan | tee "${PLAN_JSON}"

PLAN_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8"))["plan_id"])' "${PLAN_JSON}")"
CONFIRM_TOKEN="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8"))["confirm_token"])' "${PLAN_JSON}")"

python3 "${AGENT}" --backend "${SECRETS_AGENT_BACKEND:-mock}" rotate-exec \
  --plan-id "${PLAN_ID}" \
  --confirm "${CONFIRM_TOKEN}" \
  --revoke | tee "${EXEC_JSON}"

echo "dry-run complete"
echo "env_file=${ENV_FILE}"
echo "status_json=${STATUS_JSON}"
echo "plan_json=${PLAN_JSON}"
echo "exec_json=${EXEC_JSON}"
