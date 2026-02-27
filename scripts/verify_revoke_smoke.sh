#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.loop-agent/secrets-agent.env"
AGENT="${ROOT_DIR}/secrets_agent.py"
REVOKE_HOOK_SCRIPT="${ROOT_DIR}/scripts/secrets_agent_revoke_hook.sh"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

: "${SECRETS_AGENT_BACKEND:=mock}"
: "${SECRETS_AGENT_LOG_PATH:=logs/secrets_agent_audit.log}"

if [[ -z "${SECRETS_AGENT_CONFIRM_SALT:-}" ]]; then
  echo "error: SECRETS_AGENT_CONFIRM_SALT is required" >&2
  exit 2
fi

cd "${ROOT_DIR}"

AUDIT_LOG_PATH="${SECRETS_AGENT_LOG_PATH}"
if [[ "${AUDIT_LOG_PATH}" != /* ]]; then
  AUDIT_LOG_PATH="${ROOT_DIR}/${AUDIT_LOG_PATH}"
fi

mkdir -p "$(dirname "${AUDIT_LOG_PATH}")"
touch "${AUDIT_LOG_PATH}"

LINE_COUNT_BEFORE="$(wc -l < "${AUDIT_LOG_PATH}")"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

PLAN_JSON="${TMP_DIR}/plan.json"
EXEC_JSON="${TMP_DIR}/exec.json"

check_no_new_error() {
  local phase="$1"
  python3 - "${AUDIT_LOG_PATH}" "${LINE_COUNT_BEFORE}" "${phase}" <<'PY'
import json
import sys

path = sys.argv[1]
start = int(sys.argv[2])
phase = sys.argv[3]

with open(path, "r", encoding="utf-8") as fh:
    lines = fh.readlines()

for line_no, raw in enumerate(lines[start:], start=start + 1):
    row_text = raw.strip()
    if not row_text:
        continue
    try:
        row = json.loads(row_text)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in audit log at line {line_no}: {exc}", file=sys.stderr)
        sys.exit(1)
    if row.get("action") == "error":
        ts = row.get("ts", "")
        metadata = row.get("metadata", {})
        msg = metadata.get("message", "") if isinstance(metadata, dict) else ""
        print(
            f"error: new audit action=error during {phase} at {ts} message={msg}",
            file=sys.stderr,
        )
        sys.exit(1)
PY
}

echo "verify-revoke-smoke: backend=${SECRETS_AGENT_BACKEND}"
echo "verify-revoke-smoke: audit_log=${AUDIT_LOG_PATH}"
echo "verify-revoke-smoke: audit_lines_before=${LINE_COUNT_BEFORE}"

python3 "${AGENT}" --backend "${SECRETS_AGENT_BACKEND}" rotate-plan | tee "${PLAN_JSON}"
check_no_new_error "rotate-plan"

PLAN_ID="$(python3 - "${PLAN_JSON}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as fh:
    payload = json.load(fh)
print(payload["plan_id"])
PY
)"

CONFIRM_TOKEN="$(python3 - "${PLAN_JSON}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as fh:
    payload = json.load(fh)
print(payload["confirm_token"])
PY
)"

export SECRETS_AGENT_REVOKE_HOOK="${REVOKE_HOOK_SCRIPT} {item_id}"

python3 "${AGENT}" --backend "${SECRETS_AGENT_BACKEND}" rotate-exec \
  --plan-id "${PLAN_ID}" \
  --confirm "${CONFIRM_TOKEN}" \
  --revoke | tee "${EXEC_JSON}"
check_no_new_error "rotate-exec"

python3 - "${AUDIT_LOG_PATH}" "${LINE_COUNT_BEFORE}" <<'PY'
import json
import sys

path = sys.argv[1]
start = int(sys.argv[2])

with open(path, "r", encoding="utf-8") as fh:
    lines = fh.readlines()

new_rows = []
for line_no, raw in enumerate(lines[start:], start=start + 1):
    row_text = raw.strip()
    if not row_text:
        continue
    try:
        new_rows.append(json.loads(row_text))
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in audit log at line {line_no}: {exc}", file=sys.stderr)
        sys.exit(1)

rotate_plan_rows = [row for row in new_rows if row.get("action") == "rotate-plan"]
rotate_exec_rows = [
    row
    for row in new_rows
    if row.get("action") == "rotate-exec"
    and isinstance(row.get("metadata"), dict)
    and row["metadata"].get("revoke") is True
]

if not rotate_exec_rows:
    print("error: no new rotate-exec audit row with metadata.revoke=true", file=sys.stderr)
    sys.exit(1)

rotate_plan_ts = rotate_plan_rows[-1].get("ts", "") if rotate_plan_rows else ""
rotate_exec_ts = rotate_exec_rows[-1].get("ts", "")
rotate_exec_plan_id = rotate_exec_rows[-1].get("metadata", {}).get("plan_id", "")

print(f"audit_lines_after={len(lines)}")
print(f"new_audit_lines={len(new_rows)}")
print(f"rotate_plan_ts={rotate_plan_ts}")
print(f"rotate_exec_ts={rotate_exec_ts}")
print(f"rotate_exec_plan_id={rotate_exec_plan_id}")
PY

echo "verify-revoke-smoke: PASS"
