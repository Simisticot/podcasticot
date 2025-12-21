.PHONY: test dev debug
test:
	uv run pytest

dev:
	uv run fastapi dev endpoints.py
debug:
	uv run -m pdb endpoints.py
