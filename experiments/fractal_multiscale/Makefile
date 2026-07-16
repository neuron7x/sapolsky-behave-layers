.PHONY: test lint typecheck protocol verify clean

test:
	pytest

lint:
	ruff check src tests scripts

typecheck:
	mypy src/cwc_fractal

protocol:
	PYTHONPATH=src python scripts/check_protocol.py

verify: lint test typecheck protocol

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info src/*.egg-info
	find src tests -type d -name '__pycache__' -prune -exec rm -rf {} +
