#!/usr/bin/env python3
"""Deterministic validation for phantom-shell config."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "openai.yaml",
    "requirements.txt",
    "init.txt",
]

REQUIRED_OPENAI_KEYS = [
    "schema_version:",
    "name:",
    "description:",
    "instructions:",
    "tools:",
    "model:",
]


def require_files() -> None:
    missing = [rel for rel in REQUIRED_FILES if not (ROOT / rel).exists()]
    if missing:
        raise SystemExit(f"FATAL: missing files: {', '.join(missing)}")


def require_openai_yaml_shape() -> None:
    text = (ROOT / "openai.yaml").read_text(encoding="utf-8", errors="ignore")
    for key in REQUIRED_OPENAI_KEYS:
        if key not in text:
            raise SystemExit(f"FATAL: openai.yaml missing required key marker: {key}")


def require_init_seed() -> None:
    init_text = (ROOT / "init.txt").read_text(encoding="utf-8", errors="ignore").strip()
    if not init_text:
        raise SystemExit("FATAL: init.txt is empty")


def main() -> int:
    require_files()
    require_openai_yaml_shape()
    require_init_seed()
    print("PASS: phantom-shell verification complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
