# Environment Variables

This project uses a layered environment-variable strategy to keep local development practical and production deployment safe.

## Env strategy

Use three layers:

- Root [./.env.example](../.env.example): committed template with safe placeholder values
- Root `.env`: local private file for development (never commit)
- Production/staging: CI/CD or secret manager injection (never ship secrets from repository files)

## Local setup

1. Copy the template:

```bash
cp .env.example .env
```

2. Update local secrets in `.env`.
At minimum, set:

- database password
- JWT secret
- Redis password (if testing cache locally)

3. For test profile, copy `./.env.test.example` to `.env.test` and adjust credentials as needed.

## Git safety

[../.gitignore](../.gitignore) is configured to ignore env files while keeping the template committed:

- `.env`
- `.env.*`
- `!.env.example`

## Docker behavior

[docker-compose.yml](../docker-compose.yml) reads values from root `.env` via `env_file` and also supports defaults through `${VAR:-default}`.

For production deployments:

- inject values from CI/CD or a secret manager
- do not commit `.env`
- do not bake secrets into Docker images

Note: the full Yelp dataset is intentionally not baked into Docker images or the Docker Postgres volume. In development, the large dataset is kept in a local database/import flow to avoid oversized images and slow rebuilds.

## Startup validation

Critical settings are validated during service startup:

- `DATABASE_URL` is required for business-service, recommendation-service, and ingestion-service
- `JWT_SECRET` is required for api-gateway
- in `production` / `staging`, placeholder values such as `change_me` or the default dev JWT secret are rejected

This catches misconfiguration early and reduces "works on my machine" issues.

## Recommended practice

- keep `.env.example` accurate and safe
- keep real secrets only in `.env` or external secret stores
- use different secrets for local, test, and production
- rotate JWT and Redis secrets before any public deployment
