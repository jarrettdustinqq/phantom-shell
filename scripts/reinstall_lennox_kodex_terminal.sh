#!/usr/bin/env bash
set -euo pipefail

# Reinstall Codex terminal tooling on macOS/Linux in an auditable way.
# This script does not auto-run privileged commands; it prints them.

OS_NAME="$(uname -s)"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: missing required command '$1'" >&2
    return 1
  fi
}

print_header() {
  echo "== Lennox Kodex Terminal Reinstall =="
  echo "Repo: ${ROOT_DIR}"
  echo "OS: ${OS_NAME}"
}

print_os_packages() {
  echo
  echo "[1/5] System dependencies"
  if [[ "${OS_NAME}" == "Darwin" ]]; then
    cat <<'PKG'
Run manually if needed:
  brew update
  brew install git python@3.11 ripgrep make
PKG
  elif [[ "${OS_NAME}" == "Linux" ]]; then
    cat <<'PKG'
Run manually if needed:
  sudo apt-get update
  sudo apt-get install -y git python3 python3-venv python3-pip ripgrep make
PKG
  else
    echo "Unsupported OS: ${OS_NAME}. Install git, python3, venv, pip, ripgrep, make manually."
  fi
}

rebuild_venv() {
  echo
  echo "[2/5] Rebuilding Python virtual environment"
  require_cmd python3
  rm -rf "${VENV_DIR}"
  python3 -m venv "${VENV_DIR}"
  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"
  pip install --upgrade pip
  pip install -r "${ROOT_DIR}/requirements.txt"
}

verify_repo() {
  echo
  echo "[3/5] Running repository verification"
  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"
  make -C "${ROOT_DIR}" verify
  make -C "${ROOT_DIR}" test
}

print_connectivity_plan() {
  echo
  echo "[4/5] App + AI ecosystem wiring checklist"
  cat <<'PLAN'
- Connect Codex/OpenAI API key using environment variables only (no plaintext in repo).
- Add broker endpoints for finance, notes, and task systems via stable wrappers.
- Log every autonomous action with UTC timestamp and verification state.
- Keep one objective queue: income growth experiments with measurable deltas.
PLAN
}

print_next_steps() {
  echo
  echo "[5/5] Next steps"
  cat <<'NEXT'
1. Activate environment:
   source .venv/bin/activate
2. Start your terminal workflow from this repository root.
3. Keep objectives in init.txt and run make verify before each autonomous loop.
NEXT
}

main() {
  print_header
  print_os_packages
  rebuild_venv
  verify_repo
  print_connectivity_plan
  print_next_steps
  echo
  echo "Reinstall workflow completed."
}

main "$@"
