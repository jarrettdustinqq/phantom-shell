"""Regression tests for stage-aware tamper guardrail classification."""

from pathlib import Path

from scripts.classify_tamper_guardrail import classify_logs


ROOT = Path(__file__).resolve().parents[1]
EXPORT_WORKFLOW = ROOT / ".github/workflows/export-pr-evidence.yml"
GUARDRAIL_WORKFLOW = ROOT / ".github/workflows/nightly-tamper-guardrail.yml"

STAMP = "2026-11-27T16:00:00.000Z"
HASH_A = "a" * 64
HASH_B = "b" * 64


def receipt(
    *,
    generation="success",
    upload="success",
    retrieval="success",
    integrity="failure",
    tamper_test="true",
):
    payload = (
        f"generation={generation} upload={upload} retrieval={retrieval} "
        f"integrity={integrity} tamper_test={tamper_test}"
    )
    return f"{STAMP} ##[notice]EXPORT_STAGE_RECEIPT {payload}\n"


def mismatch():
    return (
        f"{STAMP} ##[error]Integrity mismatch for evidence.json: "
        f"expected {HASH_A}, got {HASH_B}\n"
    )


def test_successful_retrieval_reaches_integrity_and_detects_tamper():
    log = receipt(retrieval="success", integrity="failure") + mismatch()
    result = classify_logs(log, "failure")

    assert result["retrieval_outcome"] == "success"
    assert result["integrity_outcome"] == "failure"
    assert result["classification"] == "expected_tamper_detected"
    assert result["guardrail_pass"] is True
    assert result["open_regression_issue"] is False


def test_artifact_not_found_is_retrieval_failure_not_sha256_regression():
    log = receipt(retrieval="failure", integrity="skipped")
    log += (
        f"{STAMP} ##[error]Unable to download artifact(s): "
        "Artifact not found for name: pr-11-evidence-tuple\n"
    )
    result = classify_logs(log, "failure")

    assert result["classification"] == "artifact_retrieval_failed"
    assert result["failure_stage"] == "retrieval"
    assert result["mismatch_found"] is False
    assert result["guardrail_pass"] is False
    assert result["open_regression_issue"] is False


def test_missing_integrity_files_after_successful_retrieval_fails_closed():
    log = receipt(retrieval="success", integrity="failure")
    log += (
        f"{STAMP} ##[error]Integrity check missing required files "
        "(.json and .json.sha256) in downloaded artifact.\n"
    )
    result = classify_logs(log, "failure")

    assert result["retrieval_outcome"] == "success"
    assert result["classification"] == "missing_artifact_files"
    assert result["failure_stage"] == "integrity"
    assert result["guardrail_pass"] is False
    assert result["open_regression_issue"] is False


def test_successful_integrity_step_with_tamper_enabled_is_a_real_regression():
    log = receipt(retrieval="success", integrity="success")
    result = classify_logs(log, "success")

    assert result["classification"] == "tamper_not_detected"
    assert result["failure_stage"] == "integrity"
    assert result["guardrail_pass"] is False
    assert result["assertion_failed"] is True
    assert result["open_regression_issue"] is True


def test_checksum_mismatch_without_expected_export_failure_is_inconsistent():
    log = receipt(retrieval="success", integrity="failure") + mismatch()
    result = classify_logs(log, "success")

    assert result["classification"] == "inconsistent_evidence"
    assert result["guardrail_pass"] is False
    assert result["open_regression_issue"] is False


def test_legacy_runtime_mismatch_remains_supported_without_stage_receipt():
    result = classify_logs(mismatch(), "failure")

    assert result["receipt_found"] is False
    assert result["classification"] == "expected_tamper_detected"
    assert result["guardrail_pass"] is True


def test_legacy_artifact_not_found_is_classified_as_retrieval_failure():
    log = (
        f"{STAMP} ##[error]Unable to download artifact(s): "
        "Artifact not found for name: pr-11-evidence-tuple\n"
    )
    result = classify_logs(log, "failure")

    assert result["classification"] == "artifact_retrieval_failed"
    assert result["guardrail_pass"] is False
    assert result["open_regression_issue"] is False


def test_unavailable_logs_fail_closed_without_claiming_crypto_regression():
    result = classify_logs(mismatch(), "failure", log_fetch_succeeded=False)

    assert result["classification"] == "export_log_unavailable"
    assert result["mismatch_found"] is False
    assert result["guardrail_pass"] is False
    assert result["open_regression_issue"] is False


def test_echoed_source_or_plain_text_mismatch_is_not_runtime_evidence():
    echoed_source = (
        f"{STAMP} ##[command]echo '::error::Integrity mismatch for evidence.json: "
        f"expected {HASH_A}, got {HASH_B}'\n"
    )
    plain_text = f"{STAMP} diagnostic: Integrity mismatch for evidence.json\n"

    assert classify_logs(echoed_source, "failure")["mismatch_found"] is False
    assert classify_logs(plain_text, "failure")["mismatch_found"] is False


def test_export_workflow_emits_receipt_after_success_or_failure():
    source = EXPORT_WORKFLOW.read_text(encoding="utf-8")

    assert "id: artifact_upload" in source
    assert "id: artifact_download" in source
    assert "steps.artifact_upload.outcome" in source
    assert "steps.artifact_download.outcome" in source
    assert "steps.integrity.outcome" in source
    assert "EXPORT_STAGE_RECEIPT" in source
    assert "always()" in source


def test_guardrail_uses_its_exact_ref_and_updates_issue_only_for_verified_regression():
    source = GUARDRAIL_WORKFLOW.read_text(encoding="utf-8")

    assert "github.sha" in source
    assert "TARGET_BRANCH:" in source and "github.ref_name" in source
    assert "scripts/classify_tamper_guardrail.py" in source
    assert "open_regression_issue" in source
