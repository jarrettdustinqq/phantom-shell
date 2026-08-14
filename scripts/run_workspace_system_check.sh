#!/usr/bin/env bash
# run_workspace_system_check.sh — Workspace-wide health check for Jarrett's agent system.
# Validates fleet, phantom-shell, and continuity-spine health in one auditable run.
set -euo pipefail

home_dir="${HOME:-/home/jarrettdustinqq}"
fleet_dir="${FLEET_DIR:-${home_dir}/projects/fleet}"
continuity_dir="${CONTINUITY_DIR:-${home_dir}/control_station/continuity_spine}"
phantom_dir="${PHANTOM_DIR:-${home_dir}/projects/phantom-shell}"

started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if [[ -d "${phantom_dir}" ]]; then
  report_dir="${REPORT_DIR:-${phantom_dir}/reports}"
else
  report_dir="${REPORT_DIR:-${TMPDIR:-/tmp}/phantom-shell-reports}"
fi
report_path="${report_dir}/workspace-system-check-$(date -u +%Y%m%dT%H%M%SZ).log"
mkdir -p "${report_dir}"

declare -a failures=()

run_phantom_tests() {
  local tests=(
    tests/test_agent.py
    tests/test_loop_agent_engine.py
    tests/test_release_marker_agent.py
    tests/test_reinstall_assets.py
    tests/test_shell.py
    tests/test_verify_config.py
  )
  local missing=()
  local test_path=""

  for test_path in "${tests[@]}"; do
    if [[ ! -f "${phantom_dir}/${test_path}" ]]; then
      missing+=("${test_path}")
    fi
  done

  if ((${#missing[@]} > 0)); then
    printf 'Missing required phantom test files:' >&2
    printf ' %s' "${missing[@]}" >&2
    printf '\n' >&2
    return 2
  fi

  echo "Running ${#tests[@]} required test files..."
  (
    cd "${phantom_dir}"
    python3 -m pytest "${tests[@]}" -q
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
  echo "fleet_dir=${fleet_dir}"
  echo "continuity_dir=${continuity_dir}"
  echo "phantom_dir=${phantom_dir}"

  run_check "fleet health"       bash -lc "cd '${fleet_dir}' && ./fleetctl health"
  run_check "fleet shell syntax" bash -lc "cd '${fleet_dir}' && bash -n bootstrap.sh healthcheck.sh install_nix.sh fleetctl"
  run_check "fleet python compile" bash -lc "cd '${fleet_dir}' && python3 -m py_compile ops/control_hub_agent.py ops/mission_control_agent.py"
  run_check "fleet unit tests"   bash -lc "cd '${fleet_dir}' && python3 -m pytest tests/ -q"

  if [[ -d "${continuity_dir}" ]]; then
    run_check "continuity verify"       bash -lc "cd '${continuity_dir}' && make verify"
    run_check "continuity access-check" bash -lc "cd '${continuity_dir}' && make access-check"
  else
    echo
    echo "== continuity checkout =="
    echo "result=fail missing_required_directory=${continuity_dir}"
    failures+=("continuity checkout")
  fi

  run_check "phantom compileall" bash -lc "cd '${phantom_dir}' && python3 -m compileall -q phantom_shell scripts"
  run_check "phantom unit tests" run_phantom_tests
  run_check "workspace disk"     bash -lc "df -h '${home_dir}' | sed -n '1,2p'"
  run_check "workspace memory"   bash -lc "free -h | sed -n '1,3p'"

  echo
  if ((${#failures[@]} == 0)); then
    echo "summary=ok checks_failed=0"
  else
    printf "summary=fail checks_failed=%s failed_checks=%s\n" "${#failures[@]}" "${failures[*]}"
  fi
  echo "[END] $(date -u +%Y-%m-%dT%H:%M:%SZ)"

} > >(tee "${report_path}") 2>&1

echo "report_path=${report_path}"

if ((${#failures[@]} > 0)); then
  exit 1
fi
