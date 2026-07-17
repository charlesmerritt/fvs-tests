.PHONY: install format lint typecheck test check run

ENGINE ?= fvsjl
EXAMPLE ?= thinba

install:
	uv sync --all-groups

format:
	uv run ruff format .

lint:
	uv run ruff check .

typecheck:
	uv run ty check

test:
	uv run pytest

check: lint typecheck test

run:
	uv run fvs-test run --engine $(ENGINE) --example $(EXAMPLE)
