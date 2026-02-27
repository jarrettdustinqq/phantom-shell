#!/usr/bin/env python3
"""CLI to run autonomous risk triage and print top events/actions."""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from phantom_shell.autonomous_risk_triage import AutonomousRiskTriage


def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomous risk triage runner")
    parser.add_argument("--state-dir", default=".loop-agent")
    parser.add_argument("--log-path", default="logs/universal_agent_audit.log")
    parser.add_argument("--output", default="reports/autonomous-risk-triage.json")
    args = parser.parse_args()

    agent = AutonomousRiskTriage(
        state_dir=Path(args.state_dir),
        log_path=Path(args.log_path),
    )
    report = agent.build_report()
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"triage report={out_path}")
    for action in report["actions"]:
        print(f"{action['title']} (impact={action['impact']} effort={action['effort']}) -> {action['suggested_action']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
