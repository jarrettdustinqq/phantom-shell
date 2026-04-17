.PHONY: verify test deps

PY ?= python3

deps:
	@$(PY) -m pip install -q -r requirements.txt

verify: deps
	@$(PY) ./scripts/verify_config.py

test: deps
	@$(PY) -m pytest tests/ -v
