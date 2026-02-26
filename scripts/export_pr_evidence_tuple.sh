#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PR_NUMBER="${1:-11}"
DEFAULT_EVIDENCE_DIR="/home/jarrettdustinqq/incident-evidence/phantom-shell"
EVIDENCE_DIR="${PR_EVIDENCE_OUTPUT_DIR:-${DEFAULT_EVIDENCE_DIR}}"

if ! command -v gh >/dev/null 2>&1; then
  echo "error: gh CLI is required" >&2
  exit 2
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is required" >&2
  exit 2
fi

mkdir -p "${EVIDENCE_DIR}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

PR_JSON="${TMP_DIR}/pr.json"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARTIFACT_BASENAME="pr-${PR_NUMBER}-evidence-tuple-${STAMP}"
JSON_OUT="${EVIDENCE_DIR}/${ARTIFACT_BASENAME}.json"
MD_OUT="${EVIDENCE_DIR}/${ARTIFACT_BASENAME}.md"
SHA_OUT="${JSON_OUT}.sha256"

cd "${ROOT_DIR}"

gh pr view "${PR_NUMBER}" \
  --json number,title,url,body,statusCheckRollup,updatedAt,headRefName,baseRefName \
  > "${PR_JSON}"

python3 - "${PR_JSON}" "${JSON_OUT}" "${MD_OUT}" <<'PY'
import datetime
import json
import re
import sys
from typing import Dict, List, Optional

pr_json_path = sys.argv[1]
json_out = sys.argv[2]
md_out = sys.argv[3]

run_url_re = re.compile(
    r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/\d+"
)


def uniq(items: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def first_match(pattern: str, text: str) -> Optional[str]:
    matched = re.search(pattern, text, flags=re.MULTILINE)
    if not matched:
        return None
    return matched.group(1)


with open(pr_json_path, "r", encoding="utf-8") as fh:
    pr = json.load(fh)

body = pr.get("body") or ""
verify_ts = first_match(r"^\s*verify\s*=\s*([^\s`]+)\s*$", body)
revoke_ts = first_match(r"^\s*revoke\s*=\s*([^\s`]+)\s*$", body)

body_run_urls = uniq(run_url_re.findall(body))

stale_failing_from_body: Optional[str] = None
new_passing_from_body: Optional[str] = None
passing_from_body: List[str] = []

for line in body.splitlines():
    match = run_url_re.search(line)
    if not match:
        continue
    url = match.group(0)
    lower_line = line.lower()
    if stale_failing_from_body is None and "stale" in lower_line and "fail" in lower_line:
        stale_failing_from_body = url
    if "pass" in lower_line:
        passing_from_body.append(url)
    if new_passing_from_body is None and "new" in lower_line and "pass" in lower_line:
        new_passing_from_body = url

passing_from_body = uniq(passing_from_body)

status_checks = []
failure_pairs = []
success_pairs = []

for item in pr.get("statusCheckRollup") or []:
    if not isinstance(item, dict):
        continue
    details_url = item.get("detailsUrl") or ""
    run_url_match = run_url_re.search(details_url)
    run_url = run_url_match.group(0) if run_url_match else ""

    row: Dict[str, str] = {
        "type": item.get("__typename") or "",
        "workflow_name": item.get("workflowName") or "",
        "name": item.get("name") or "",
        "status": item.get("status") or "",
        "conclusion": item.get("conclusion") or "",
        "started_at": item.get("startedAt") or "",
        "completed_at": item.get("completedAt") or "",
        "details_url": details_url,
        "run_url": run_url,
    }
    status_checks.append(row)

    completed_key = row["completed_at"] or row["started_at"] or ""
    if row["conclusion"] == "FAILURE" and run_url:
        failure_pairs.append((completed_key, run_url))
    if row["conclusion"] == "SUCCESS" and run_url:
        success_pairs.append((completed_key, run_url))

failure_pairs.sort(key=lambda pair: pair[0])
success_pairs.sort(key=lambda pair: pair[0])

status_failure_urls = uniq([run for _, run in failure_pairs])
status_success_urls = uniq([run for _, run in success_pairs])

stale_failing_run_url = stale_failing_from_body
if stale_failing_run_url is None and status_failure_urls:
    stale_failing_run_url = status_failure_urls[0]

passing_run_url = new_passing_from_body
if passing_run_url is None and passing_from_body:
    passing_run_url = passing_from_body[-1]
if passing_run_url is None and status_success_urls:
    passing_run_url = status_success_urls[-1]

exported_at_utc = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
if exported_at_utc.endswith("+00:00"):
    exported_at_utc = exported_at_utc[:-6] + "Z"

artifact = {
    "schema": "pr-evidence-tuple/v1",
    "exported_at_utc": exported_at_utc,
    "source": {
        "tool": "gh pr view",
        "fields": [
            "number",
            "title",
            "url",
            "body",
            "statusCheckRollup",
            "updatedAt",
            "headRefName",
            "baseRefName",
        ],
    },
    "pr": {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "url": pr.get("url"),
        "updated_at": pr.get("updatedAt"),
        "head_ref": pr.get("headRefName"),
        "base_ref": pr.get("baseRefName"),
    },
    "evidence": {
        "verify_timestamp": verify_ts,
        "revoke_timestamp": revoke_ts,
        "stale_failing_run_url": stale_failing_run_url,
        "passing_run_url": passing_run_url,
        "body_labeled_urls": {
            "stale_failing_run_url": stale_failing_from_body,
            "new_passing_run_url": new_passing_from_body,
            "passing_run_urls": passing_from_body,
        },
        "body_run_urls": body_run_urls,
        "status_run_urls": {
            "failure": status_failure_urls,
            "success": status_success_urls,
        },
        "status_checks": status_checks,
    },
}

with open(json_out, "w", encoding="utf-8") as fh:
    json.dump(artifact, fh, indent=2, sort_keys=True)
    fh.write("\n")

with open(md_out, "w", encoding="utf-8") as fh:
    fh.write("# PR Evidence Tuple\n\n")
    fh.write(f"- Exported at: {artifact['exported_at_utc']}\n")
    fh.write(f"- PR: #{artifact['pr']['number']} {artifact['pr']['url']}\n")
    fh.write(f"- Verify timestamp: {verify_ts or 'missing'}\n")
    fh.write(f"- Revoke timestamp: {revoke_ts or 'missing'}\n")
    fh.write(f"- Stale failing run URL: {stale_failing_run_url or 'missing'}\n")
    fh.write(f"- Passing run URL: {passing_run_url or 'missing'}\n")
    fh.write("\n")
    fh.write("## Body Run URLs\n\n")
    for url in body_run_urls:
        fh.write(f"- {url}\n")
    fh.write("\n")
    fh.write("## Status Check Run URLs\n\n")
    for url in status_failure_urls:
        fh.write(f"- failure: {url}\n")
    for url in status_success_urls:
        fh.write(f"- success: {url}\n")
PY

sha256sum "${JSON_OUT}" > "${SHA_OUT}"

echo "export-pr-evidence-tuple: PASS"
echo "pr_number=${PR_NUMBER}"
echo "json=${JSON_OUT}"
echo "md=${MD_OUT}"
echo "sha256=${SHA_OUT}"
echo "index=${MD_OUT}"
