#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root_dir="$(cd "${script_dir}/.." && pwd)"

host="${HOST:-127.0.0.1}"
port="${PORT:-8787}"
state_path="${STATE_PATH:-.loop-agent/universal-agent-state.json}"
audit_log="${AUDIT_LOG:-logs/universal_agent_audit.log}"
hub_state="${HUB_STATE:-.loop-agent/ecosystem-hub-state.json}"

cd "${root_dir}"
python3 "${script_dir}/universal_agent_dashboard.py" \
  --host "${host}" \
  --port "${port}" \
  --state-path "${state_path}" \
  --audit-log "${audit_log}" \
  --hub-state "${hub_state}"
