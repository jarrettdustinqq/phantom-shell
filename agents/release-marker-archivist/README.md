# Release Marker Archivist

Pairs immutable git refs with one-screen release notes and append-only ledger rows.

## Primary Command

```bash
scripts/run_release_marker_agent.sh capture --repo /path/to/repo --ref <tag-or-commit> --marker-name <marker-name>
```

## Guarantees

- deterministic note content from git metadata
- append-only marker ledger in `.loop-agent/release-marker-agent/markers.jsonl`
- explicit commit SHA anchoring for recovery and rollback

## Status Check

```bash
scripts/run_release_marker_agent.sh status
```
