# Search Rollout & Observability

This document contains detailed search behavior, rollout controls, diagnostics, and frontend debug options.

## Overview

Business search supports controlled rollout and diagnostics through one semantic model.

## Request Query Params

- `query`: free-text search phrase (max 200 chars)
- `search_path`: `auto | fts | trigram | legacy`

Behavior:

- `auto` (default): FTS first, then trigram fallback for low/zero-result scenarios
- `fts`: force FTS only (diagnostics)
- `trigram`: force trigram only (diagnostics)
- `legacy`: force legacy SQL filter path (safe rollback)

## Response Headers

- `X-Search-Path`: `fts | trigram | legacy`
- `X-Search-Version`: `v2 | legacy`
- `X-Search-Latency-Ms`: integer latency in milliseconds

## Logged Search Metrics

Each `/businesses` request emits a structured `search_metrics` log line with:

- `path`
- `version`
- `latency_ms`
- `result_count`
- `zero_results`
- `query_hash` (first 12 chars of SHA-256, never raw query)
- `fallback_reason` (`forced_legacy`, `forced_trigram`, `fts_low_results`, `fts_zero_results`, `fts_timeout`, `fts_error`, `no_query`)

## Fail-safe Behavior

If FTS fails or times out, business-service automatically falls back to `legacy` and logs the reason.

## API Example

```bash
curl -H "Authorization: Bearer <JWT_TOKEN>" \
  "http://localhost:8000/businesses?query=pizza+tucson&search_path=auto&city=Phoenix"
```

## Frontend Dev Search Debug

Frontend has a dev-mode debug panel that shows search execution metadata (`X-Search-*`).

Enabled by default in non-production builds.
You can also force-enable it with:

`NEXT_PUBLIC_SHOW_SEARCH_DEBUG=1`

When enabled:

- Search form exposes a `Path` selector (`auto|fts|trigram|legacy`)
- Results page shows path, version, and latency reported by API Gateway
