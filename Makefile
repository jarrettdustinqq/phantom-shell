.PHONY: verify test deps export-evidence-tuple

PY ?= python3

deps:
	@$(PY) -m pip install -q -r requirements.txt

verify: deps
	@$(PY) ./scripts/verify_config.py

test: deps
	@$(PY) -m pytest tests/ -v

export-evidence-tuple:
	@test -n "$(PR)" || (echo "error: PR=<pull_request_number> is required" >&2; exit 2)
	@./scripts/export_pr_evidence_tuple.sh "$(PR)"
