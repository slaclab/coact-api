FROM tiangolo/uvicorn-gunicorn-fastapi:python3.10-slim

RUN mkdir -p /app
WORKDIR /app
COPY pyproject.toml /app

RUN pip3 install .

COPY . /app

ENTRYPOINT [ "uvicorn", "main:app", "--host", "0.0.0.0", "--reload" ]
