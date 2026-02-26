## Required Evidence

- [ ] verify-revoke-smoke evidence pair attached in exact format

Run `make verify-revoke-smoke` and paste this block with real UTC timestamps:

```text
verify-revoke-smoke:
verify=YYYY-MM-DDTHH:MM:SSZ
revoke=YYYY-MM-DDTHH:MM:SSZ
```

Notes:
- Keep both timestamps within the last 24 hours.
- Use UTC (`Z` or `+00:00`), with `Z` preferred.
