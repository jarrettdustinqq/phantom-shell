#!/usr/bin/env bash
set -euo pipefail

prefix="$(npm config get prefix)"
codex_dir="${prefix}/lib/node_modules/@openai/codex"

echo "Using npm prefix: ${prefix}"

if [[ -d "${codex_dir}" ]]; then
  echo "Removing existing Codex directory: ${codex_dir}"
  rm -rf "${codex_dir}"
fi

echo "Cleaning npm cache..."
npm cache clean --force

echo "Installing @openai/codex globally..."
npm install -g @openai/codex

echo "Codex installation complete. Verify with: codex --help"
