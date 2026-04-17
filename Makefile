.PHONY: verify test

PY ?= python3

verify:
	@$(PY) ./scripts/verify_config.py

test:
	@$(PY) -m pytest tests/ -v
