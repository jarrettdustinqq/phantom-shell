.PHONY: verify test verify-revoke-smoke export-evidence-tuple dominion-smoke publish-guard

PY ?= python3

verify:
	@$(PY) ./scripts/verify_config.py

test:
	@$(PY) -m unittest discover -s tests -p 'test_*.py' -v

verify-revoke-smoke:
	@./scripts/verify_revoke_smoke.sh

export-evidence-tuple:
	@./scripts/export_pr_evidence_tuple.sh $(PR)

dominion-smoke:
	@./scripts/run_dominion_control.sh status >/dev/null
	@./scripts/run_dominion_control.sh cycle --objective "Smoke test dominion cycle" >/dev/null
	@./scripts/run_dominion_swarm.sh >/dev/null
	@echo "PASS: dominion smoke complete"

publish-guard:
	@./scripts/continuity_publish_guard.py --base-ref origin/main
