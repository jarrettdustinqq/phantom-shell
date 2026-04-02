# Evidence Export Proof Loop

This runbook documents the minimum durable proof loop for PR evidence export.

## Purpose

Prove a replay-safe, checkpointed, feature-flagged workflow before broader autonomy.

## Files

- `scripts/evidence_export_loop.py`: proof-loop runtime
- `docker-compose.yml`: optional local Redis/Qdrant stack for later expansion
- `checkpoint_evidence.json`: local state file created at runtime

## Required environment variables

Set these outside the repository in a secret store or CI settings:

- `EVIDENCE_EXPORT_ENABLED=true|false`
- `EVIDENCE_OUTPUT_DIR=./evidence_exports`
- `CHECKPOINT_FILE=./checkpoint_evidence.json`
- `MAX_RETRIES=3`

## Example sandbox run

```bash
EVIDENCE_EXPORT_ENABLED=true python scripts/evidence_export_loop.py 12
```

## Expected result

- one JSON file
- one Markdown file
- one SHA256 file
- one checkpoint entry for the PR
- repeat runs skip completed PRs
