#!/usr/bin/env python3
"""Interactive console for the Ecosystem Hub."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import json
import shlex
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from phantom_shell.ecosystem_hub import EcosystemHub
from phantom_shell.universal_agent import UniversalAgent


def build_hub(args: argparse.Namespace) -> EcosystemHub:
    ua = UniversalAgent(
        state_path=Path(args.ua_state),
        audit_log_path=Path(args.ua_audit),
    )
    return EcosystemHub(universal_agent=ua, state_path=Path(args.hub_state))


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True))


def help_text() -> str:
    return (
        "Commands:\n"
        "  /help\n"
        "  /status\n"
        "  /connectors\n"
        "  /agents\n"
        "  /agent-add <agent_id> <role> <connector_ids_csv> <objective>\n"
        "  /agent-toggle <agent_id> <true|false>\n"
        "  /suggest <objective>\n"
        "  /run <agent_id> <connector_id> [json_payload]\n"
        "  /workflow <agent_id> <json_steps>\n"
        "  /quit\n"
    )


def run_repl(hub: EcosystemHub) -> int:
    print("Ecosystem Hub Console")
    print(help_text())
    while True:
        try:
            raw = input("hub> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not raw:
            continue
        if raw in {"/quit", "quit", "exit"}:
            return 0
        if raw == "/help":
            print(help_text())
            continue
        try:
            parts = shlex.split(raw)
            cmd = parts[0]
            if cmd == "/status":
                print_json({"hub": hub.status(), "universal_agent": hub.universal_agent.status()})
            elif cmd == "/connectors":
                print_json({"connectors": hub.universal_agent.list_connectors()})
            elif cmd == "/agents":
                print_json({"agents": hub.list_agents()})
            elif cmd == "/agent-add":
                if len(parts) < 5:
                    raise ValueError("usage: /agent-add <id> <role> <connector_ids_csv> <objective>")
                connector_ids = [item.strip() for item in parts[3].split(",") if item.strip()]
                row = hub.register_agent(
                    agent_id=parts[1],
                    name=parts[1],
                    role=parts[2],
                    allowed_connectors=connector_ids,
                    objective=" ".join(parts[4:]),
                    enabled=True,
                )
                print_json({"agent": row})
            elif cmd == "/agent-toggle":
                if len(parts) != 3:
                    raise ValueError("usage: /agent-toggle <id> <true|false>")
                enabled = parts[2].lower() == "true"
                print_json({"agent": hub.toggle_agent(parts[1], enabled)})
            elif cmd == "/suggest":
                if len(parts) < 2:
                    raise ValueError("usage: /suggest <objective>")
                text = " ".join(parts[1:])
                print_json({"objective": text, "suggested_connectors": hub.suggest_connectors(text)})
            elif cmd == "/run":
                if len(parts) < 3:
                    raise ValueError("usage: /run <agent_id> <connector_id> [json_payload]")
                payload = {}
                if len(parts) > 3:
                    payload = json.loads(" ".join(parts[3:]))
                print_json(hub.route_task(parts[1], parts[2], payload))
            elif cmd == "/workflow":
                if len(parts) < 3:
                    raise ValueError("usage: /workflow <agent_id> <json_steps>")
                steps = json.loads(" ".join(parts[2:]))
                if not isinstance(steps, list):
                    raise ValueError("json_steps must be a list")
                print_json(hub.run_workflow(agent_id=parts[1], steps=steps))
            else:
                print("Unknown command. Use /help.")
        except Exception as exc:  # noqa: BLE001
            print(f"error: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ecosystem Hub console")
    parser.add_argument("--ua-state", default=".loop-agent/universal-agent-state.json")
    parser.add_argument("--ua-audit", default="logs/universal_agent_audit.log")
    parser.add_argument("--hub-state", default=".loop-agent/ecosystem-hub-state.json")
    args = parser.parse_args()
    hub = build_hub(args)
    return run_repl(hub)


if __name__ == "__main__":
    raise SystemExit(main())
