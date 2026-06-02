# Architecture

This project is intentionally small, but the code is split around the same boundaries I would keep in a larger service.

```text
Client
  |
  v
HTTP router and validation
  |
  v
LinkStore
  |
  v
SQLite
```

## Components

- `app/main.py`: HTTP request handling, validation, responses, redirects, and rate limiting decisions.
- `app/storage.py`: SQLite schema, inserts, lookups, and visit count updates.
- `tests/test_app.py`: End-to-end API tests using a real local HTTP server and temporary SQLite database.
- `infra/terraform`: A deployment sketch for running the container on AWS ECS Fargate.

## Request Flow

### Create

```text
POST /urls
  -> parse JSON
  -> rate limit by client IP
  -> validate URL, alias, and TTL
  -> insert code into SQLite
  -> return shortUrl
```

### Redirect

```text
GET /{code}
  -> look up code
  -> reject missing or expired links
  -> increment visit_count
  -> return 302 Location: long_url
```

### Stats

```text
GET /stats/{code}
  -> look up code
  -> return metadata, visit count, and expiration state
```

## Data Model

```text
code TEXT PRIMARY KEY
long_url TEXT NOT NULL
created_at INTEGER NOT NULL
expires_at INTEGER NULL
visit_count INTEGER NOT NULL DEFAULT 0
```

The data model is deliberately simple. It supports the required create and redirect operations, plus lightweight analytics and TTL behavior.

## Deployment Sketch

The Terraform files describe:

- Application Load Balancer for public traffic
- ECS Fargate for container compute
- EFS mounted at `/data` for demo SQLite persistence
- CloudWatch Logs for runtime visibility
- Security groups separating ALB, service, and EFS traffic

For a production version, I would replace the SQLite/EFS persistence path with DynamoDB or Postgres before scaling beyond one task.
