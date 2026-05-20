# coact-api

SLAC's Scientific User and Resource Management System API.

## Getting Started

Clone the repository:

```sh
git clone https://github.com/slaclab/coact-api.git
cd coact-api
cp .env.example .env
```

Start all services:

```sh
docker compose up --build
```

This brings up:

| Service      | Description                          | Port(s)            |
|--------------|--------------------------------------|--------------------|
| `coact-api`  | FastAPI/Strawberry GraphQL server    | `8000`             |
| `mongo`      | MongoDB 8 (seeded with init scripts) | internal only      |
| `mailhog`    | Local SMTP + web UI for emails       | `1025` / `8025`    |

The API will be available at <http://localhost:8000/graphql> once the services are healthy.

To view caught emails, open the MailHog web UI at <http://localhost:8025>.

## Stopping Services

```sh
docker compose down
```

To also remove the persisted MongoDB data volume:

```sh
docker compose down -v
```
