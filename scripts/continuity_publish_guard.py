#!/usr/bin/env python3
"""CI guard for publish-safe markdown diffs and immutable section enforcement."""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import subprocess
import sys
import tempfile

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from phantom_shell.dominion_protocol import PublishGuard


def run(cmd: list[str]) -> str:
    proc = subprocess.run(
        cmd,
        cwd=ROOT_DIR,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip() or "command failed"
        raise RuntimeError(f"{' '.join(cmd)} :: {err}")
    return proc.stdout


def changed_markdown_files(base_ref: str) -> list[str]:
    out = run(["git", "diff", "--name-only", f"{base_ref}...HEAD", "--", "*.md"])
    return [line.strip() for line in out.splitlines() if line.strip()]


def base_file_content(base_ref: str, rel_path: str) -> str:
    proc = subprocess.run(
        ["git", "show", f"{base_ref}:{rel_path}"],
        cwd=ROOT_DIR,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description="Continuity publish guard")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--report-path", default="reports/continuity-publish-guard.json")
    args = parser.parse_args()

    files = changed_markdown_files(args.base_ref)
    guard = PublishGuard()
    reports = []
    blocked = []
    for rel in files:
        rel_path = Path(rel)
        candidate_path = ROOT_DIR / rel_path
        if not candidate_path.exists():
            continue
        baseline_text = base_file_content(args.base_ref, rel)
        if not baseline_text:
            # New file: no immutable baseline to compare. Still run alignment checks.
            base_tmp = ""
        else:
            base_tmp = baseline_text
        with tempfile.TemporaryDirectory() as tmp:
            baseline_path = Path(tmp) / "baseline.md"
            baseline_path.write_text(base_tmp, encoding="utf-8")
            report = guard.evaluate(
                baseline_path=baseline_path,
                candidate_path=candidate_path,
            )
            report["relative_path"] = rel
            reports.append(report)
            if not report["allowed_to_publish"]:
                blocked.append(rel)

    payload = {
        "base_ref": args.base_ref,
        "changed_markdown_files": files,
        "checked_files": len(reports),
        "blocked_files": blocked,
        "reports": reports,
    }
    report_path = Path(args.report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"report_path={report_path}")
    print(f"checked_files={len(reports)}")
    print(f"blocked_files={len(blocked)}")
    if blocked:
        print("blocked_list=" + ",".join(blocked))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
