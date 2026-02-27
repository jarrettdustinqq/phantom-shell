.PHONY: verify test verify-revoke-smoke export-evidence-tuple

PY ?= python3

verify:
	@$(PY) ./scripts/verify_config.py

test:
	@$(PY) -m unittest discover -s tests -p 'test_*.py' -v

verify-revoke-smoke:
	@./scripts/verify_revoke_smoke.sh

export-evidence-tuple:
	@./scripts/export_pr_evidence_tuple.sh $(PR)
