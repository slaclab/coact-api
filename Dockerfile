FROM python:3.12-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN mkdir -p /app
WORKDIR /app

COPY pyproject.toml /app

RUN uv pip install --system --no-deps .

COPY . /app

RUN uv pip install --system .

ENTRYPOINT [ "uvicorn", "main:app", "--host", "0.0.0.0", "--reload" ]