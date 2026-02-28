#!/usr/bin/env bash
set -euo pipefail

home_dir="${HOME:-/home/jarrettdustinqq}"
fleet_dir="${home_dir}/projects/fleet"
continuity_dir="${home_dir}/control_station/continuity_spine"
phantom_dir="${home_dir}/projects/phantom-shell"

started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
report_path="${phantom_dir}/reports/workspace-system-check-$(date -u +%Y%m%dT%H%M%SZ).log"
mkdir -p "$(dirname "${report_path}")"

declare -a failures=()

run_phantom_unit_tests() {
  local tests=(
    tests/test_codex_cross_chat_memory.py
    tests/test_brain_repository.py
    tests/test_income_os.py
    tests/test_n8n_swarm_forge.py
    tests/test_release_marker_agent.py
  )
  local existing=()
  local test_path=""
  for test_path in "${tests[@]}"; do
    if [[ -f "${phantom_dir}/${test_path}" ]]; then
      existing+=("${test_path}")
    fi
  done

  if ((${#existing[@]} == 0)); then
    echo "No configured phantom tests found on this branch; skipping."
    return 0
  fi

  (
    cd "${phantom_dir}"
    python3 -m unittest -q "${existing[@]}"
  )
}

run_check() {
  local label="$1"
  shift
  echo
  echo "== ${label} =="
  if "$@"; then
    echo "result=ok"
  else
    local code=$?
    echo "result=fail exit_code=${code}"
    failures+=("${label}")
  fi
}

{
  echo "[BEGIN] ${started_at}"
  run_check "fleet health" bash -lc "cd '${fleet_dir}' && ./fleetctl health"
  run_check "fleet shell syntax" bash -lc "cd '${fleet_dir}' && bash -n bootstrap.sh healthcheck.sh install_nix.sh fleetctl"
  run_check "fleet shellcheck" bash -lc "cd '${fleet_dir}' && shellcheck bootstrap.sh healthcheck.sh install_nix.sh fleetctl"
  run_check "fleet python compile" bash -lc "cd '${fleet_dir}' && python3 -m py_compile ops/control_hub_agent.py ops/mission_control_agent.py"
  run_check "fleet unit tests" bash -lc "cd '${fleet_dir}' && python3 -m unittest -q tests/test_control_hub_generated_inventory.py"

  run_check "continuity verify" bash -lc "cd '${continuity_dir}' && make verify"
  run_check "continuity access-check" bash -lc "cd '${continuity_dir}' && make access-check"

  run_check "phantom compileall" bash -lc "cd '${phantom_dir}' && python3 -m compileall -q phantom_shell scripts"
  run_check "phantom unit tests" run_phantom_unit_tests
  run_check "workspace disk snapshot" bash -lc "df -h '${home_dir}' | sed -n '1,2p'"
  run_check "workspace memory snapshot" bash -lc "free -h | sed -n '1,3p'"

  echo
  if ((${#failures[@]} == 0)); then
    echo "summary=ok checks_failed=0"
    echo "[END] $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  else
    printf "summary=fail checks_failed=%s failed_checks=%s\n" "${#failures[@]}" "${failures[*]}"
    echo "[END] $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  fi
} > >(tee "${report_path}") 2>&1

echo "report_path=${report_path}"

if ((${#failures[@]} > 0)); then
  exit 1
fi
