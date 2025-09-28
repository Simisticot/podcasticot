.PHONY: test dev
test:
	uv run pytest

dev:
	uv run fastapi dev endpoints.py
