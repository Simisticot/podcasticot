FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /podcasticot

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_TOOL_BIN_DIR=/usr/local/bin

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY . /podcasticot

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

ENTRYPOINT []

EXPOSE 8700

CMD ["uv", "run", "--no-dev", "gunicorn", "server:app", "-b", "0.0.0.0:8700", "-w", "4"]
