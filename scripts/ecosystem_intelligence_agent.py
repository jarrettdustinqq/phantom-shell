#!/usr/bin/env python3
"""Run ecosystem intelligence analysis + optional email delivery."""

from __future__ import annotations

from pathlib import Path
import argparse
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from phantom_shell.ecosystem_intelligence_agent import EcosystemIntelligenceAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ecosystem intelligence agent")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--state-dir", default=".loop-agent")
    parser.add_argument(
        "--report-path",
        default="reports/ecosystem-intelligence-report.md",
    )
    parser.add_argument(
        "--json-path",
        default="reports/ecosystem-intelligence-report.json",
    )
    parser.add_argument("--max-sources-per-query", type=int, default=5)
    parser.add_argument("--email-to", action="append", default=[])
    parser.add_argument("--email-subject", default="AI Ecosystem Improvement Recommendations")
    parser.add_argument("--send-email", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    state_dir = (repo_root / args.state_dir).resolve()
    report_path = (repo_root / args.report_path).resolve()
    json_path = (repo_root / args.json_path).resolve()

    agent = EcosystemIntelligenceAgent(
        repo_root=repo_root,
        state_dir=state_dir,
        max_sources_per_query=args.max_sources_per_query,
    )
    inventory = agent.collect_local_inventory()
    queries = agent.build_queries(inventory)
    research = agent.run_research(queries)
    recommendations = agent.synthesize_recommendations(inventory, research)
    report_text = agent.build_markdown_report(inventory, research, recommendations)
    agent.write_outputs(
        report_md=report_text,
        inventory=inventory,
        research=research,
        recommendations=recommendations,
        report_path=report_path,
        json_path=json_path,
    )
    print(f"report_path={report_path}")
    print(f"json_path={json_path}")
    print(f"recommendation_count={len(recommendations)}")
    if args.send_email:
        recipients = args.email_to
        if not recipients:
            raise ValueError("--send-email requires at least one --email-to recipient")
        agent.send_email(
            subject=args.email_subject,
            body_text=report_text,
            to_emails=recipients,
        )
        print(f"email_sent_to={','.join(recipients)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
