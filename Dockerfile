FROM ghcr.io/astral-sh/uv:0.13.7 AS uv
FROM python:3.12-slim-bookworm

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock README.md ./
COPY LICENSE LICENSE-2 ./

RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY data/scenarios ./data/scenarios

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "uvicorn", "flowtm.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
