FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install dependencies first for Docker layer caching
COPY pyproject.toml uv.lock ./

RUN uv sync --locked --no-install-project

# Copy application
COPY load.py .

# Don't install the project itself
CMD ["uv", "run", "--no-sync", "load.py"]
