# URL Shortener Demo

A small, dependency-free URL shortener service

The service supports:

- Creating a short URL from a long URL
- Redirecting a short URL to the original URL
- Optional custom aliases
- Optional link expiration through `ttlSeconds`
- Basic visit analytics through `/stats/{code}`
- Infrastructure-as-code sketch for AWS ECS Fargate

## Local Run

Requirements:

- Python 3.11+

Start the service:

```bash
python -m app.main
```

The app listens on:

```text
http://127.0.0.1:8000
```

You can use the small browser UI at the root path, or call the API directly.

Create a short URL:

```bash
curl -X POST http://127.0.0.1:8000/urls \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/a/long/path"}'
```

Create a short URL with a custom alias and TTL:

```bash
curl -X POST http://127.0.0.1:8000/urls \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/docs","customAlias":"docs","ttlSeconds":3600}'
```

Redirect:

```bash
curl -i http://127.0.0.1:8000/docs
```

Stats:

```bash
curl http://127.0.0.1:8000/stats/docs
```

Run tests:

```bash
python -m unittest discover -s tests
```

Use a custom database path:

```bash
DATABASE_URL=data/dev-links.db python -m app.main
```

On Windows PowerShell:

```powershell
$env:DATABASE_URL="data/dev-links.db"
python -m app.main
```

## API

### `POST /urls`

Request:

```json
{
  "url": "https://example.com/a/long/path",
  "customAlias": "optional-alias",
  "ttlSeconds": 3600
}
```

Response:

```json
{
  "code": "abcd1234",
  "shortUrl": "http://127.0.0.1:8000/abcd1234",
  "longUrl": "https://example.com/a/long/path",
  "expiresAt": 1710000000
}
```

### `GET /{code}`

Returns `302 Found` with a `Location` header pointing at the original URL.

### `GET /stats/{code}`

Returns basic metadata and visit count.

### `GET /healthz`

Returns a simple health check response for load balancers.

## Architecture

Local demo:

```text
Browser or API client
        |
        v
Python HTTP server
        |
        v
SQLite links table
```

The service is split into:

- `app/main.py`: HTTP routing, request validation, JSON responses, redirects
- `app/storage.py`: SQLite persistence, short code generation, visit counts
- `tests/test_app.py`: API and storage coverage using the standard library
- `infra/terraform`: AWS deployment definition

Data model:

```text
code TEXT PRIMARY KEY
long_url TEXT NOT NULL
created_at INTEGER NOT NULL
expires_at INTEGER NULL
visit_count INTEGER NOT NULL DEFAULT 0
```

## Design Decisions

Short code generation uses 8 random base62 characters. That gives a large keyspace while keeping URLs readable. Insert collisions are handled by retrying, and custom aliases are rejected if already taken.

The demo validates only absolute `http` and `https` URLs. This avoids obviously unsafe schemes such as `javascript:` and keeps redirect behavior predictable.

SQLite was chosen for the 2-4 hour version because it keeps the local demo easy to run and review. Storage is isolated in `LinkStore`, so a production version could replace it with DynamoDB, Postgres, or Redis-backed storage without rewriting HTTP routing.

The browser UI is intentionally small. The API is the primary deliverable, and the UI exists so reviewers can quickly try the service without crafting curl requests.

## Infrastructure

The Terraform sketch in `infra/terraform` deploys a containerized version of the service to AWS using:

- Application Load Balancer for public HTTP traffic
- ECS Fargate for container compute
- EFS mounted at `/data` so the demo SQLite database survives task restarts
- CloudWatch Logs for service logs
- Security groups for ALB, ECS task, and EFS traffic boundaries

Example Terraform flow:

```bash
cd infra/terraform
terraform init
terraform plan \
  -var='container_image=123456789012.dkr.ecr.us-east-1.amazonaws.com/url-shortener-demo:latest' \
  -var='vpc_id=vpc-...' \
  -var='public_subnet_ids=["subnet-...","subnet-..."]' \
  -var='private_subnet_ids=["subnet-...","subnet-..."]'
```

This is meant to demonstrate deployment thinking rather than be the final production architecture.

## Production Trade-offs

With more time, I would change or add:

- Replace SQLite/EFS with DynamoDB or Postgres for safer horizontal scaling
- Add HTTPS, custom domain, and DNS automation
- Add authentication for link management endpoints
- Add rate limiting and abuse protection
- Add URL threat scanning or allow/deny lists
- Add structured logs, metrics, dashboards, and alerts
- Add CI/CD to build, test, scan, and deploy the container
- Add background cleanup for expired links
- Add idempotency or duplicate URL handling depending on product requirements
- Add distributed tracing and better request correlation


