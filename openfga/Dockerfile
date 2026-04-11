FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copy the client library and openfga project files
COPY client /app/client
COPY openfga /app/openfga

WORKDIR /app/openfga

# Install dependencies and the project itself using uv.
# This will automatically install the local client dependency because it is in openfga/pyproject.toml.
RUN uv sync --frozen --no-dev

CMD ["uv", "run", "python", "main.py"]