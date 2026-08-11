.PHONY: test dev debug type
test:
	uv run pytest

dev:
	uv run cli.py serve --reload
debug:
	uv run -m pdb cli.py
type:
	uv run pyrefly check
migrate:
	uv run persistence/migration.py
