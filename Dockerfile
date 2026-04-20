FROM python:3.12-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN mkdir -p /app
WORKDIR /app

COPY pyproject.toml uv.lock ./client /app/

RUN uv sync --frozen --no-install-project --no-dev

COPY . /app

RUN uv sync --frozen --no-dev

ENTRYPOINT [ "uvicorn", "main:app", "--host", "0.0.0.0", "--reload" ]
