.PHONY: install lint format types test check

install:
	pip install -e ".[dev,data]"
	pre-commit install

lint:
	ruff check .

format:
	ruff format .

types:
	mypy

test:
	pytest -m "not network"

check: lint types test
	ruff format --check .
