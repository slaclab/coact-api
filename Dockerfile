FROM python:3.12-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Used to associate the image with a source repository outside GHA
LABEL org.opencontainers.image.source=https://github.com/slaclab/coact-api

RUN mkdir -p /app
WORKDIR /app

COPY pyproject.toml uv.lock ./client /app/

RUN uv sync --frozen --no-install-project --no-dev

COPY . /app

RUN uv sync --frozen --no-dev

ENTRYPOINT [ "/app/.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--reload" ]
