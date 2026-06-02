# Trade-offs

This version is scoped for a 2-4 hour exercise. The goal is a working, reviewable service with enough structure to discuss production evolution.

## What Was Prioritized

- A working API over framework complexity
- Zero third-party dependencies so the reviewer can run it immediately
- Real SQLite persistence instead of an in-memory map
- Focused tests that exercise the HTTP layer and storage layer
- Infrastructure-as-code that shows deployment thinking without requiring a full AWS account setup to review the code

## Shortcuts

SQLite is fine for the local demo, but it is not the right long-term choice for a horizontally scaled URL shortener. The Terraform sketch uses EFS to make SQLite survive task restarts, but that is still a demo-oriented compromise.

The rate limiter is in-memory and per-process. It helps show abuse awareness, but it would not work correctly across multiple app instances. A production implementation would use Redis, DynamoDB conditional writes, API Gateway throttling, or a WAF rule depending on the deployment.

The service does not authenticate link creation. For a public product, I would add account-scoped API keys, OAuth, or another authentication layer depending on the user model.

The service validates URL shape but does not perform threat scanning. Production should consider phishing, malware, SSRF-like abuse, allow/deny lists, and a reporting or takedown workflow.

## Production Follow-ups

- Use DynamoDB or Postgres for durable, scalable storage
- Add HTTPS, DNS, and certificate automation
- Add structured JSON logs and request IDs
- Add CloudWatch metrics and alarms for error rate, latency, and redirect volume
- Add CI/CD for container build, vulnerability scan, and deploy
- Add background cleanup or lazy deletion for expired links
- Add duplicate URL handling if product requirements call for canonical links
- Add load tests to size short-code collision risk and storage throughput
- Add migration strategy for schema changes
