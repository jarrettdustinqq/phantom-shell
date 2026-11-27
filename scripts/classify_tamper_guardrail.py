#!/usr/bin/env python3
"""Classify nightly artifact/tamper workflow outcomes without guessing.

A cryptographic regression is reported only when the controlled tamper test
reaches integrity verification and the verifier succeeds despite the mutation.
Earlier-stage failures remain fail-closed but are classified separately.
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Any

_TIMESTAMP = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z"
_JOB_STEP_PREFIX = r"(?:[^\t\r\n]+\t[^\t\r\n]+\t)?"
_RUNTIME_PREFIX = r"^" + _JOB_STEP_PREFIX + _TIMESTAMP + r"\s+"

_RECEIPT_RE = re.compile(
    _RUNTIME_PREFIX
    + r"##\[notice\]EXPORT_STAGE_RECEIPT\s+(?P<payload>[^\r\n]+)$",
    re.MULTILINE,
)
_MISMATCH_RE = re.compile(
    _RUNTIME_PREFIX
    + r"##\[error\]Integrity mismatch for .+: expected "
    + r"[0-9a-fA-F]{64}, got [0-9a-fA-F]{64}$",
    re.MULTILINE,
)
_RETRIEVAL_ERROR_RE = re.compile(
    _RUNTIME_PREFIX + r"##\[error\]Unable to download artifact\(s\):.*$",
    re.MULTILINE,
)
_MISSING_FILES_RE = re.compile(
    _RUNTIME_PREFIX
    + r"##\[error\]Integrity check missing required files .*?$",
    re.MULTILINE,
)

_REQUIRED_RECEIPT_FIELDS = (
    "generation",
    "upload",
    "retrieval",
    "integrity",
    "tamper_test",
)
_VALID_OUTCOMES = {"success", "failure", "skipped", "cancelled", "not_run"}


def _parse_receipt(log_text: str) -> dict[str, str] | None:
    matches = list(_RECEIPT_RE.finditer(log_text))
    if not matches:
        return None
    payload = matches[-1].group("payload")
    return dict(re.findall(r"([a-z_]+)=([^\s]+)", payload))


def _result(
    classification: str,
    failure_stage: str,
    *,
    mismatch_found: bool = False,
    receipt_found: bool = False,
    generation_outcome: str = "unknown",
    upload_outcome: str = "unknown",
    retrieval_outcome: str = "unknown",
    integrity_outcome: str = "unknown",
    tamper_test: str = "unknown",
    reason: str = "",
) -> dict[str, Any]:
    guardrail_pass = classification == "expected_tamper_detected"
    open_regression_issue = classification == "tamper_not_detected"
    return {
        "classification": classification,
        "failure_stage": failure_stage,
        "mismatch_found": mismatch_found,
        "receipt_found": receipt_found,
        "generation_outcome": generation_outcome,
        "upload_outcome": upload_outcome,
        "retrieval_outcome": retrieval_outcome,
        "integrity_outcome": integrity_outcome,
        "tamper_test": tamper_test,
        "guardrail_pass": guardrail_pass,
        "assertion_failed": not guardrail_pass,
        "open_regression_issue": open_regression_issue,
        "reason": reason,
    }


def classify_logs(
    log_text: str,
    export_conclusion: str,
    *,
    log_fetch_succeeded: bool = True,
) -> dict[str, Any]:
    """Return a fail-closed classification for the export workflow run."""
    conclusion = (export_conclusion or "unknown").strip().lower()
    if not log_fetch_succeeded:
        return _result(
            "export_log_unavailable",
            "log_retrieval",
            reason="export_logs_could_not_be_retrieved",
        )

    mismatch_found = bool(_MISMATCH_RE.search(log_text))
    retrieval_error = bool(_RETRIEVAL_ERROR_RE.search(log_text))
    missing_files_error = bool(_MISSING_FILES_RE.search(log_text))
    receipt = _parse_receipt(log_text)

    if receipt is None:
        # Backward compatibility for pre-receipt runs: a real, timestamped
        # mismatch annotation is still sufficient positive evidence.
        if retrieval_error and mismatch_found:
            return _result(
                "inconsistent_evidence",
                "retrieval_and_integrity",
                mismatch_found=True,
                reason="retrieval_failure_and_integrity_mismatch_both_present",
            )
        if retrieval_error:
            return _result(
                "artifact_retrieval_failed",
                "retrieval",
                reason="artifact_download_failed_before_integrity_verification",
            )
        if missing_files_error:
            return _result(
                "missing_artifact_files",
                "integrity",
                reason="downloaded_artifact_did_not_contain_required_checksum_files",
            )
        if mismatch_found and conclusion == "failure":
            return _result(
                "expected_tamper_detected",
                "integrity",
                mismatch_found=True,
                reason="legacy_runtime_checksum_mismatch_annotation_verified",
            )
        if mismatch_found:
            return _result(
                "inconsistent_evidence",
                "integrity",
                mismatch_found=True,
                reason="checksum_mismatch_annotation_conflicts_with_export_conclusion",
            )
        return _result(
            "stage_receipt_missing",
            "unknown",
            reason="no_structured_stage_receipt_or_positive_integrity_evidence",
        )

    missing_fields = [key for key in _REQUIRED_RECEIPT_FIELDS if key not in receipt]
    if missing_fields:
        return _result(
            "invalid_stage_receipt",
            "receipt",
            mismatch_found=mismatch_found,
            receipt_found=True,
            reason="missing_receipt_fields_" + "_".join(missing_fields),
        )

    generation = receipt["generation"].lower()
    upload = receipt["upload"].lower()
    retrieval = receipt["retrieval"].lower()
    integrity = receipt["integrity"].lower()
    tamper_test = receipt["tamper_test"].lower()

    values = {
        "generation": generation,
        "upload": upload,
        "retrieval": retrieval,
        "integrity": integrity,
    }
    invalid = [key for key, value in values.items() if value not in _VALID_OUTCOMES]
    if invalid:
        return _result(
            "invalid_stage_receipt",
            "receipt",
            mismatch_found=mismatch_found,
            receipt_found=True,
            generation_outcome=generation,
            upload_outcome=upload,
            retrieval_outcome=retrieval,
            integrity_outcome=integrity,
            tamper_test=tamper_test,
            reason="invalid_receipt_outcomes_" + "_".join(invalid),
        )

    shared = {
        "mismatch_found": mismatch_found,
        "receipt_found": True,
        "generation_outcome": generation,
        "upload_outcome": upload,
        "retrieval_outcome": retrieval,
        "integrity_outcome": integrity,
        "tamper_test": tamper_test,
    }

    if generation != "success":
        return _result(
            "artifact_generation_failed",
            "generation",
            reason="evidence_tuple_generation_did_not_complete",
            **shared,
        )
    if upload != "success":
        return _result(
            "artifact_upload_failed",
            "upload",
            reason="evidence_artifact_upload_did_not_complete",
            **shared,
        )
    if retrieval != "success":
        return _result(
            "artifact_retrieval_failed",
            "retrieval",
            reason="artifact_download_did_not_complete_so_integrity_was_not_verified",
            **shared,
        )
    if tamper_test not in {"true", "1", "yes"}:
        return _result(
            "tamper_test_not_enabled",
            "test_setup",
            reason="guardrail_export_did_not_enable_the_controlled_tamper_input",
            **shared,
        )

    if integrity == "success":
        if mismatch_found:
            return _result(
                "inconsistent_evidence",
                "integrity",
                reason="integrity_step_succeeded_but_runtime_mismatch_annotation_exists",
                **shared,
            )
        return _result(
            "tamper_not_detected",
            "integrity",
            reason="tamper_input_was_enabled_but_integrity_step_succeeded",
            **shared,
        )

    if integrity == "failure":
        if mismatch_found and conclusion == "failure":
            return _result(
                "expected_tamper_detected",
                "integrity",
                reason="controlled_mutation_produced_runtime_checksum_mismatch",
                **shared,
            )
        if mismatch_found:
            return _result(
                "inconsistent_evidence",
                "integrity",
                reason="checksum_mismatch_annotation_conflicts_with_export_conclusion",
                **shared,
            )
        if missing_files_error:
            return _result(
                "missing_artifact_files",
                "integrity",
                reason="artifact_downloaded_but_required_integrity_files_were_missing",
                **shared,
            )
        return _result(
            "integrity_check_failed_without_mismatch",
            "integrity",
            reason="integrity_step_failed_without_a_verified_checksum_mismatch",
            **shared,
        )

    return _result(
        "integrity_check_not_run",
        "integrity",
        reason="integrity_verification_did_not_produce_a_completed_outcome",
        **shared,
    )


def _write_github_outputs(path: str, result: dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as output:
        for key, value in result.items():
            if isinstance(value, bool):
                rendered = "true" if value else "false"
            else:
                rendered = str(value).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            output.write(f"{key}={rendered}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-file", required=True)
    parser.add_argument("--export-conclusion", required=True)
    parser.add_argument(
        "--log-fetch-succeeded", choices=("true", "false"), required=True
    )
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT", ""))
    args = parser.parse_args()

    log_fetch_succeeded = args.log_fetch_succeeded == "true"
    try:
        log_text = Path(args.log_file).read_text(encoding="utf-8", errors="replace")
    except OSError:
        log_text = ""
        log_fetch_succeeded = False

    result = classify_logs(
        log_text,
        args.export_conclusion,
        log_fetch_succeeded=log_fetch_succeeded,
    )
    if args.github_output:
        _write_github_outputs(args.github_output, result)

    print(
        "Tamper guardrail classification: "
        f"{result['classification']} "
        f"(stage={result['failure_stage']}, "
        f"mismatch_found={str(result['mismatch_found']).lower()}, "
        f"guardrail_pass={str(result['guardrail_pass']).lower()})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
