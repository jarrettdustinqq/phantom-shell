.PHONY: verify test

PY ?= python3

verify:
	@$(PY) ./scripts/verify_config.py

test:
	@$(PY) -m unittest discover -s tests -p 'test_*.py' -v
