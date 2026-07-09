# Environment Variable Reference

**Single source of truth:** `Backend/app/core/config.py` (`Settings`). Values below are the
in-code defaults. Env vars are **case-sensitive**. List values accept either a JSON array
(`["a","b"]`) or a comma-separated string (`a,b`). Unknown vars are ignored (`extra=ignore`).

Frontend variables (`NEXT_PUBLIC_*`) are baked at **build time** and live in `UI/`.

## Validation rules (enforced at startup)

From `_production_safety_checks`:

- `SECRET_KEY` is required when `AUTH_REQUIRED=true`. If blank, a random per-process key is
  generated (dev only; restart invalidates issued tokens).
- When `USE_REAL_AGENTS=true`, the API key for `DEFAULT_LLM_PROVIDER` must be set.
- When `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY` is required.
- When `ENV=production`, **all** of the following are enforced: `AUTH_REQUIRED=true`,
  `SECRET_KEY` length >= 32, no `*` in `CORS_ORIGINS`, no `*` in `ALLOWED_HOSTS`, and (if
  `SEED_DEFAULT_USER=true`) `DEFAULT_ADMIN_PASSWORD` set and length >= 12.

## App

| Variable | Default | Notes |
|----------|---------|-------|
| `APP_NAME` | `GL Guardian Backend` | |
| `APP_VERSION` | `0.1.0` | |
| `ENV` | `development` | `development` \| `testing` \| `production` |
| `DEBUG` | `false` | Leaks error detail in responses when true |
| `LOG_LEVEL` | `INFO` | |

## API

| Variable | Default | Notes |
|----------|---------|-------|
| `API_HOST` | `0.0.0.0` | |
| `API_PORT` | `8000` | |
| `API_ROOT_PATH` | `/api/v1` | Prefix for all business routers |
| `CORS_ORIGINS` | `["http://localhost:3000","http://localhost:8000"]` | Must be explicit in prod |
| `CORS_ALLOW_CREDENTIALS` | `true` | |
| `ALLOWED_HOSTS` | `["*"]` | Must be explicit in prod (TrustedHostMiddleware) |

## Database (PostgreSQL)

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `postgresql://gl_guardian:gl_guardian_dev_password@localhost:5432/gl_guardian` | |
| `DATABASE_ECHO` | `false` | SQL echo |
| `DATABASE_POOL_SIZE` | `20` | |
| `DATABASE_MAX_OVERFLOW` | `10` | |
| `DATABASE_POOL_TIMEOUT` | `30` | seconds |
| `DATABASE_POOL_RECYCLE` | `3600` | seconds |

## Redis

| Variable | Default | Notes |
|----------|---------|-------|
| `REDIS_URL` | `redis://localhost:6379/0` | Cache DB |
| `REDIS_CACHE_TTL` | `3600` | |
| `REDIS_EVENT_CHANNEL_PREFIX` | `investigation_events` | |
| `USE_REDIS_EVENTS` | `false` | Cross-process WS delivery when true |
| `REDIS_SOCKET_TIMEOUT` | `0.25` | seconds |

## Celery

| Variable | Default | Notes |
|----------|---------|-------|
| `CELERY_BROKER_URL` | `redis://localhost:6379/1` | |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/2` | |
| `CELERY_TASK_SERIALIZER` | `json` | |
| `CELERY_ACCEPT_CONTENT` | `["json"]` | |
| `CELERY_TIMEZONE` | `UTC` | |
| `USE_CELERY` | `false` | Off = investigations run in the API process |

## EventStoreDB (audit)

| Variable | Default | Notes |
|----------|---------|-------|
| `USE_EVENTSTORE` | `false` | Off = Postgres hash-chain audit |
| `EVENTSTORE_URL` | `esdb://localhost:2113?tls=false` | |
| `EVENTSTORE_STREAM_PREFIX` | `investigations` | |
| `AUDIT_FALLBACK_TO_POSTGRES` | `true` | |

## LLM providers

| Variable | Default | Notes |
|----------|---------|-------|
| `DEFAULT_LLM_PROVIDER` | `anthropic` | `anthropic`\|`groq`\|`openai`\|`gemini`\|`deepseek` |
| `ANTHROPIC_API_KEY` / `GROQ_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` / `DEEPSEEK_API_KEY` | `""` | Required for the selected provider when `USE_REAL_AGENTS=true` |
| `ENABLE_LLM_FALLBACK` | `true` | |
| `LLM_FALLBACK_ORDER` | `["groq","openai"]` | |
| `LLM_REQUEST_TIMEOUT_SECONDS` | `45.0` | |
| `LLM_CACHE_ENABLED` | `true` | |
| `LLM_CACHE_TTL_SECONDS` | `1800` | |
| `LLM_MAX_PROMPT_TOKENS` | `18000` | |
| `LLM_PRICING_OVERRIDES_JSON` | `""` | JSON to override cost model |
| `CLAUDE_MODEL_REASONING` | `claude-sonnet-5` | |
| `CLAUDE_MODEL_LIGHTWEIGHT` | `claude-haiku-4-5-20251001` | |
| `GROQ_MODEL_REASONING` | `llama-3.3-70b-versatile` | |
| `GROQ_MODEL_LIGHTWEIGHT` | `llama-3.1-8b-instant` | |
| `OPENAI_MODEL_REASONING` | `gpt-4.1` | |
| `OPENAI_MODEL_LIGHTWEIGHT` | `gpt-4.1-mini` | |
| `GEMINI_MODEL_REASONING` | `gemini-2.0-flash` | |
| `GEMINI_MODEL_LIGHTWEIGHT` | `gemini-2.0-flash-lite` | |
| `DEEPSEEK_MODEL_REASONING` | `deepseek-reasoner` | |
| `DEEPSEEK_MODEL_LIGHTWEIGHT` | `deepseek-chat` | |
| `*_TEMPERATURE` (per provider) | 0.2 - 0.7 | See config for each |
| `CLAUDE_MAX_TOKENS` | `4000` | |
| `USE_REAL_AGENTS` | `false` | Off = deterministic stub agents (no token spend) |

## RAGAS real-time evaluation

| Variable | Default | Notes |
|----------|---------|-------|
| `RAGAS_REALTIME_ENABLED` | `true` | LLM-judge scoring per investigation |
| `RAGAS_JUDGE_MODEL` | `""` | Blank -> `CLAUDE_MODEL_REASONING`; judge always calls Anthropic |
| `RAGAS_JUDGE_TIMEOUT_SECONDS` | `45.0` | |

## Observability

| Variable | Default | Notes |
|----------|---------|-------|
| `METRICS_ENABLED` | `true` | Exposes `/metrics` |
| `LANGSMITH_TRACING` | `false` | Requires `LANGSMITH_API_KEY` when true |
| `LANGSMITH_API_KEY` | `""` | |
| `LANGSMITH_PROJECT` | `gl-guardian` | |
| `LANGSMITH_ENDPOINT` | `https://api.smith.langchain.com` | |

## Authentication

| Variable | Default | Notes |
|----------|---------|-------|
| `SECRET_KEY` | `""` | JWT signing key; >=32 chars in prod |
| `ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | |
| `AUTH_REQUIRED` | `false` | Forced `true` in prod |
| `SEED_DEFAULT_USER` | `true` | Seed an admin on startup |
| `DEFAULT_ADMIN_USERNAME` | `admin` | |
| `DEFAULT_ADMIN_PASSWORD` | `""` | Required (>=12) if seeding in prod |
| `DEFAULT_ADMIN_ROLE` | `partner` | |

## Investigation defaults / governance

| Variable | Default | Notes |
|----------|---------|-------|
| `DEFAULT_MATERIALITY_THRESHOLD` | `50000.0` | USD |
| `DEFAULT_CONFIDENCE_THRESHOLD` | `0.7` | |
| `DEFAULT_ESCALATION_THRESHOLD` | `0.5` | |
| `MAX_DEBATE_ROUNDS` | `2` | |
| `MAX_VERIFICATION_RETRIES` | `1` | |
| `INVESTIGATION_TIMEOUT_MINUTES` | `30` | |
| `ESTIMATED_AGENT_RUN_COST_USD` | `0.21` | |
| `ENFORCE_SEGREGATION_OF_DUTIES` | `true` | |
| `IMMUTABLE_AUDIT_LOG_REQUIRED` | `true` | |
| `AUDIT_RETENTION_YEARS` | `7` | |
| `IP_ALLOWLIST_ENABLED` | `false` | |
| `REQUEST_LOGGING_ENABLED` | `true` | |
| `REQUEST_LOG_EXCLUDED_PATHS` | health/docs/token/etc. | |
| `NOTIFICATIONS_ENABLED` | `false` | |
| `DISPLAY_CURRENCY` | `USD` | |
| `UI_THEME` | `system` | |

## External evidence APIs

| Variable | Default | Notes |
|----------|---------|-------|
| `FX_API_BASE_URL` | `https://api.frankfurter.app` | Live FX rates |
| `REGISTRY_API_BASE_URL` | `""` | Vendor registry |
| `EVIDENCE_VERIFICATION_PROVIDER_TIMEOUT_SECONDS` | `3.0` | |
| `EVIDENCE_VERIFICATION_*_TOLERANCE` | 0.0 - 0.30 | Per category (FX, flight, hotel, food, cab, fuel, GST) |
| `FLIGHT/HOTEL/FOOD/CAB/FUEL/GST_*_PROVIDER_URL` / `_API_KEY` | `""` | Optional benchmark providers |

## Frontend (`NEXT_PUBLIC_*`, build-time)

| Variable | Default | Notes |
|----------|---------|-------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000/api/v1` | API base baked into the UI image |
| `NEXT_PUBLIC_API_TOKEN` | (unset) | Option 1: pre-issued bearer token |
| `NEXT_PUBLIC_API_USERNAME` / `NEXT_PUBLIC_API_PASSWORD` | (unset) | Option 2: local password flow (do not use prod creds) |
