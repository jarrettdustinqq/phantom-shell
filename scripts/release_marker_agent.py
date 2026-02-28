#!/usr/bin/env python3
"""CLI for immutable release marker note generation."""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from phantom_shell.release_marker_agent import ReleaseMarkerAgent


def print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="release marker agent")
    parser.add_argument(
        "--state-dir",
        default=".loop-agent/release-marker-agent",
        help="state directory used for append-only marker ledger",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="show release marker ledger status")
    status.add_argument(
        "--ledger-path",
        default="",
        help="optional override for ledger file path",
    )

    capture = sub.add_parser("capture", help="capture one immutable release marker note")
    capture.add_argument(
        "--repo",
        default=".",
        help="target repository path",
    )
    capture.add_argument(
        "--ref",
        default="HEAD",
        help="tag/commit/branch ref to capture",
    )
    capture.add_argument(
        "--marker-name",
        default="",
        help="optional marker label used for the note title and filename",
    )
    capture.add_argument(
        "--output-path",
        default="",
        help="optional absolute/relative path for markdown note output",
    )
    capture.add_argument(
        "--ledger-path",
        default="",
        help="optional override for marker ledger file path",
    )
    capture.add_argument(
        "--allow-existing-note",
        action="store_true",
        help="allow overwriting existing note path",
    )

    return parser


def optional_path(value: str) -> Path | None:
    clean = value.strip()
    if not clean:
        return None
    return Path(clean)


def main() -> int:
    args = build_parser().parse_args()
    agent = ReleaseMarkerAgent(state_dir=(ROOT_DIR / args.state_dir).resolve())

    if args.command == "status":
        print_json(agent.status(ledger_path=optional_path(args.ledger_path)))
        return 0

    if args.command == "capture":
        payload = agent.capture(
            repo_path=Path(args.repo).expanduser().resolve(),
            ref=args.ref,
            marker_name=args.marker_name,
            note_path=optional_path(args.output_path),
            ledger_path=optional_path(args.ledger_path),
            allow_existing_note=bool(args.allow_existing_note),
        )
        print_json(payload)
        return 0

    raise SystemExit(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
