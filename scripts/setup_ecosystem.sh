#!/usr/bin/env bash
set -euo pipefail

OS_NAME="$(uname -s)"

require_cmd() {
  command -v "$1" >/dev/null 2>&1
}

install_linux_pkg() {
  local pkg="$1"
  if require_cmd apt-get; then
    sudo apt-get update -y
    sudo apt-get install -y "$pkg"
  else
    echo "[warn] apt-get not available. Install $pkg manually." >&2
  fi
}

install_mac_pkg() {
  local pkg="$1"
  if ! require_cmd brew; then
    echo "[info] Homebrew missing. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)" || true
  fi
  brew install "$pkg"
}

install_pkg() {
  local pkg="$1"
  case "$OS_NAME" in
    Linux) install_linux_pkg "$pkg" ;;
    Darwin) install_mac_pkg "$pkg" ;;
    *) echo "[warn] Unsupported OS: $OS_NAME. Install $pkg manually." >&2 ;;
  esac
}

ensure_pkg() {
  local cmd="$1"
  local pkg="$2"
  if require_cmd "$cmd"; then
    echo "[ok] $cmd already installed"
  else
    echo "[info] Installing $pkg ($cmd)"
    install_pkg "$pkg"
  fi
}

banner() {
  echo ""
  echo "============================="
  echo "$1"
  echo "============================="
}

banner "Core CLI prerequisites"
ensure_pkg curl curl
ensure_pkg git git

banner "Task runner"
if ! require_cmd just && ! [ -f Makefile ]; then
  echo "[info] No task runner found. Installing just."
  ensure_pkg just just
else
  echo "[ok] Task runner already present"
fi

banner "Browser automation"
if require_cmd python3; then
  python3 -m pip install --upgrade pip
  python3 -m pip install playwright
  python3 -m playwright install
else
  echo "[warn] python3 not found. Install Python 3 to use Playwright." >&2
fi

banner "Optional: Node.js (for JS-based automations)"
if ! require_cmd node; then
  echo "[info] Node.js not found. Install if needed for JS automation."
else
  echo "[ok] Node.js already installed"
fi

cat <<'SUMMARY'

Next steps (manual):
- Install and open Windsurf IDE.
- Install/enable the OpenAI/ChatGPT extension in Windsurf.
- Verify a windsurf: link opens the IDE.
- Choose docs/tasks/logging systems and connect them.

SUMMARY
