#!/usr/bin/env python3
"""CLI for ChatGPT mission control task orchestration."""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from phantom_shell.chatgpt_mission_control import ChatGPTMissionControl


def print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True))


def parse_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ChatGPT mission control")
    parser.add_argument(
        "--state-path",
        default=".loop-agent/chatgpt-mission-control.json",
        help="state file path",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="show mission-control status")

    list_parser = sub.add_parser("list", help="list tasks")
    list_parser.add_argument("--status", default="", help="optional status filter")

    create = sub.add_parser("create", help="create a task")
    create.add_argument("--title", required=True)
    create.add_argument("--objective", required=True)
    create.add_argument("--mode", required=True, choices=["deep_research", "agent_mode"])
    create.add_argument("--assignee", default="chatgpt.com-agent")
    create.add_argument("--context", default="")
    create.add_argument(
        "--acceptance",
        default="Return concrete findings and source links.;Call out risks and confidence.",
        help="semicolon-separated acceptance criteria",
    )

    update = sub.add_parser("update", help="update task status")
    update.add_argument("--task-id", required=True)
    update.add_argument("--status", required=True)
    update.add_argument("--result", default="")

    packet = sub.add_parser("packet", help="generate task handoff packet")
    packet.add_argument("--task-id", required=True)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    control = ChatGPTMissionControl(state_path=Path(args.state_path))

    if args.command == "status":
        print_json(control.status())
        return 0
    if args.command == "list":
        print_json({"tasks": control.list_tasks(status=args.status)})
        return 0
    if args.command == "create":
        task = control.create_task(
            title=args.title,
            objective=args.objective,
            mode=args.mode,
            assignee=args.assignee,
            context=args.context,
            acceptance_criteria=parse_list(args.acceptance),
        )
        print_json({"task": task})
        return 0
    if args.command == "update":
        print_json(
            {
                "task": control.update_task(
                    task_id=args.task_id,
                    status=args.status,
                    result_summary=args.result,
                )
            }
        )
        return 0
    if args.command == "packet":
        print(control.build_handoff_prompt(task_id=args.task_id))
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
