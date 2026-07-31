.PHONY: test dev debug type
test:
	uv run pytest

dev:
	uv run endpoints.py serve --reload
debug:
	uv run -m pdb endpoints.py
type:
	uv run pyrefly check
migrate:
	uv run persistence/migration.py
