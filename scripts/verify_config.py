#!/usr/bin/env python3
"""Deterministic validation for phantom-shell config."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "openai.yaml",
    "requirements.txt",
    "init.txt",
]

REQUIRED_OPENAI_KEYS = [
    "schema_version",
    "name",
    "description",
    "instructions",
    "tools",
    "model",
]


def require_files() -> None:
    missing = [rel for rel in REQUIRED_FILES if not (ROOT / rel).exists()]
    if missing:
        raise SystemExit(f"FATAL: missing files: {', '.join(missing)}")


def require_openai_yaml_shape() -> None:
    path = ROOT / "openai.yaml"
    text = path.read_text(encoding="utf-8")

    if "\t" in text:
        raise SystemExit("FATAL: openai.yaml contains tab characters")
    if not text.endswith("\n"):
        raise SystemExit("FATAL: openai.yaml must end with a newline")

    trailing_ws = [
        line_no
        for line_no, line in enumerate(text.splitlines(), start=1)
        if line.rstrip(" ") != line
    ]
    if trailing_ws:
        lines = ", ".join(str(item) for item in trailing_ws[:8])
        raise SystemExit(f"FATAL: openai.yaml contains trailing spaces on line(s): {lines}")

    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as err:
        raise SystemExit(f"FATAL: openai.yaml failed YAML parse: {err}") from err

    if not isinstance(parsed, dict):
        raise SystemExit("FATAL: openai.yaml root must be a mapping")

    missing = [key for key in REQUIRED_OPENAI_KEYS if key not in parsed]
    if missing:
        raise SystemExit(f"FATAL: openai.yaml missing required key(s): {', '.join(missing)}")

    if parsed["schema_version"] != 1:
        raise SystemExit("FATAL: openai.yaml schema_version must equal 1")
    if not isinstance(parsed["name"], str) or not parsed["name"].strip():
        raise SystemExit("FATAL: openai.yaml name must be a non-empty string")
    if not isinstance(parsed["description"], str) or not parsed["description"].strip():
        raise SystemExit("FATAL: openai.yaml description must be a non-empty string")
    if not isinstance(parsed["instructions"], str) or not parsed["instructions"].strip():
        raise SystemExit("FATAL: openai.yaml instructions must be a non-empty string")
    if not isinstance(parsed["model"], str) or not parsed["model"].strip():
        raise SystemExit("FATAL: openai.yaml model must be a non-empty string")

    tools = parsed["tools"]
    if not isinstance(tools, list) or not tools:
        raise SystemExit("FATAL: openai.yaml tools must be a non-empty list")
    tool_types = []
    for idx, tool in enumerate(tools, start=1):
        if not isinstance(tool, dict):
            raise SystemExit(f"FATAL: openai.yaml tools[{idx}] must be a mapping")
        tool_type = tool.get("type")
        if not isinstance(tool_type, str) or not tool_type.strip():
            raise SystemExit(f"FATAL: openai.yaml tools[{idx}] must include a non-empty type")
        tool_types.append(tool_type)

    for required_tool in ("browser", "python"):
        if required_tool not in tool_types:
            raise SystemExit(f"FATAL: openai.yaml tools must include type '{required_tool}'")

    instructions = parsed["instructions"]
    for marker in (
        "Instruction priority order is",
        "If directives conflict,",
        "closest compliant alternative",
    ):
        if marker not in instructions:
            raise SystemExit(
                f"FATAL: openai.yaml instructions missing conflict-priority marker: {marker}"
            )


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
