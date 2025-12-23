.PHONY: test dev debug type
test:
	uv run pytest

dev:
	uv run fastapi dev endpoints.py
debug:
	uv run -m pdb endpoints.py
type:
	uv run pyrefly check
