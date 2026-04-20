FROM tiangolo/uvicorn-gunicorn-fastapi:python3.10-slim

# Used to associate the image with a source repository outside GHA
LABEL org.opencontainers.image.source=https://github.com/slaclab/coact-api

RUN mkdir -p /app
WORKDIR /app
COPY requirements.txt /app

RUN pip3 install -r /app/requirements.txt

COPY . /app

ENTRYPOINT [ "uvicorn", "main:app", "--host", "0.0.0.0", "--reload" ]
