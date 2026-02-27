#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
STATE_DIR="${STATE_DIR:-${ROOT_DIR}/.loop-agent}"

cd "${ROOT_DIR}"

# Ensure bootstrap events exist before one-shot worker processing.
python3 "${SCRIPT_DIR}/dominion_control.py" --state-dir "${STATE_DIR}" bootstrap >/dev/null
python3 - "${STATE_DIR}" "${ROOT_DIR}" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
repo_root = Path(sys.argv[2]).resolve()
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from phantom_shell.dominion_protocol import DominionMessageBus

bus = DominionMessageBus(root / "dominion-events.jsonl")
for event_type in (
    "daily_tick",
    "hourly_tick",
    "strategy_update",
    "new_trend",
    "backup_tick",
    "persona_rotation_tick",
):
    bus.emit(event_type=event_type, source="run_dominion_swarm", payload={})
PY

agents=(
  reclaimor
  mutator
  ghost_writer
  fund_tracker
  identity_forge
  tactician
  dominion_guard
)

pids=()
for agent in "${agents[@]}"; do
  python3 "${SCRIPT_DIR}/dominion_agent_worker.py" \
    --state-dir "${STATE_DIR}" \
    --agent-id "${agent}" \
    --once &
  pids+=("$!")
done

for pid in "${pids[@]}"; do
  wait "${pid}"
done

echo "Dominion swarm one-shot cycle complete."
