#!/usr/bin/env python3
"""Durable proof-loop for PR evidence export.

This script is intentionally simple and file-backed first. It:
- gates execution behind EVIDENCE_EXPORT_ENABLED=true
- records one checkpoint entry per PR in JSON
- avoids re-export for completed PRs
- emits JSON completion/failure events for downstream consumers

It is a proof loop, not the final production runtime.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(8192), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _load_checkpoint(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _save_checkpoint(path: Path, payload: dict) -> None:
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    tmp.replace(path)


def _export(pr_number: int, out_dir: Path) -> dict:
    ts = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    stem = f'pr-{pr_number}-evidence-tuple-{ts}'
    json_path = out_dir / f'{stem}.json'
    md_path = out_dir / f'{stem}.md'
    sha_path = out_dir / f'{stem}.sha256'
    payload = {
        'pr_number': pr_number,
        'timestamp_utc': ts,
        'mode': 'proof-loop',
        'note': 'Replace this simulated export with the real make export-evidence-tuple integration.'
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    md_path.write_text(
        f'# Evidence for PR #{pr_number}\n\n- generated_at_utc: {ts}\n- mode: proof-loop\n',
        encoding='utf-8',
    )
    sha_value = _sha256(json_path)
    sha_path.write_text(sha_value + '\n', encoding='utf-8')
    return {
        'json': str(json_path),
        'md': str(md_path),
        'sha256': str(sha_path),
        'hash': sha_value,
        'timestamp_utc': ts,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print('usage: evidence_export_loop.py <pr_number>', file=sys.stderr)
        return 2
    if os.getenv('EVIDENCE_EXPORT_ENABLED', 'false').lower() != 'true':
        print('evidence export disabled by feature flag')
        return 0
    try:
        pr_number = int(argv[1])
    except ValueError:
        print('pr_number must be an integer', file=sys.stderr)
        return 2

    out_dir = Path(os.getenv('EVIDENCE_OUTPUT_DIR', './evidence_exports'))
    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = Path(os.getenv('CHECKPOINT_FILE', './checkpoint_evidence.json'))
    max_retries = int(os.getenv('MAX_RETRIES', '3'))

    checkpoint = _load_checkpoint(checkpoint_path)
    key = str(pr_number)
    if key in checkpoint and checkpoint[key].get('completed'):
        print(json.dumps({'event': 'evidence_export_skipped', 'reason': 'already_completed', 'pr_number': pr_number}))
        return 0
    if key in checkpoint and checkpoint[key].get('fail_count', 0) >= max_retries:
        print(json.dumps({'event': 'evidence_export_blocked', 'reason': 'circuit_breaker_open', 'pr_number': pr_number}), file=sys.stderr)
        return 1

    try:
        files = _export(pr_number, out_dir)
        checkpoint[key] = {
            'completed': True,
            'fail_count': 0,
            'timestamp_utc': files['timestamp_utc'],
            'files': files,
        }
        _save_checkpoint(checkpoint_path, checkpoint)
        print(json.dumps({'event': 'evidence_export_complete', 'pr_number': pr_number, 'files': files}))
        return 0
    except Exception as exc:
        row = checkpoint.get(key, {'completed': False, 'fail_count': 0})
        row['fail_count'] = int(row.get('fail_count', 0)) + 1
        row['last_error'] = str(exc)
        checkpoint[key] = row
        _save_checkpoint(checkpoint_path, checkpoint)
        print(json.dumps({'event': 'evidence_export_failure', 'pr_number': pr_number, 'error': str(exc), 'fail_count': row['fail_count']}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
