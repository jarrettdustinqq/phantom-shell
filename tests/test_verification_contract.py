from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "verify-revoke-evidence.yml"
OPERATIONS = ROOT / "OPERATIONS.md"
PR_TEMPLATE = ROOT / ".github" / "pull_request_template.md"
MAKEFILE = ROOT / "Makefile"


def test_evidence_gate_does_not_trust_pr_body_or_timestamps():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "PR_BODY" not in text
    assert "MAX_EVIDENCE_AGE_HOURS" not in text
    assert "verify=<timestamp>" not in text
    assert "revoke=<timestamp>" not in text
    assert "pull_request.body" not in text


def test_evidence_gate_is_bound_to_exact_pr_head():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "ref: ${{ github.event.pull_request.head.sha }}" in text
    assert "EXPECTED_HEAD_SHA: ${{ github.event.pull_request.head.sha }}" in text
    assert 'git rev-parse HEAD' in text


def test_evidence_gate_runs_real_repository_verification():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python ./scripts/verify_config.py" in text
    assert "python -m pytest tests/ -q" in text


def test_legacy_smoke_command_is_retired_from_operator_instructions():
    operations = OPERATIONS.read_text(encoding="utf-8")
    template = PR_TEMPLATE.read_text(encoding="utf-8")
    assert "run `make verify-revoke-smoke`" not in operations.lower()
    assert "run `make verify-revoke-smoke`" not in template.lower()
    assert "self-authored verify/revoke timestamps" in template


def test_documented_evidence_export_make_target_exists():
    makefile = MAKEFILE.read_text(encoding="utf-8")
    assert "export-evidence-tuple:" in makefile
    assert './scripts/export_pr_evidence_tuple.sh "$(PR)"' in makefile
