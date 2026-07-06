# Security and Secrets Guide

**Verified against:** `Backend/app/core/security.py`, `config.py`, `app/main.py`,
`app/core/request_logging.py`. **Version:** `0.1.0`.

## 1. Authentication

- **Scheme:** OAuth2 password grant issuing a JWT (`HS256`), signed with `SECRET_KEY`.
- **Login:** `POST /api/v1/auth/token`. Register: `POST /api/v1/auth/register`.
  Current user: `GET /api/v1/auth/me`.
- **Passwords:** hashed with bcrypt (`hash_password` / `verify_password`).
- **Token lifetime:** `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30).
- **Enforcement:** governed by `AUTH_REQUIRED`. It defaults to `false` for local dev, and
  is **forced `true` when `ENV=production`** by a startup safety check.

## 2. Authorization (RBAC)

- Roles: `analyst` (default token role), `reviewer`, `manager`, `partner`, `admin`.
- Elevated roles: `ELEVATED_ROLES = {"partner", "admin"}` enforced by
  `require_elevated_role`.
- Segregation of duties: `ENFORCE_SEGREGATION_OF_DUTIES=true` by default (governance
  setting).

> Verify that destructive/administrative routes (e.g. `DELETE /investigations/all`,
> `DELETE /intake/imported`, settings writes) depend on `require_elevated_role`. Any route
> that does not is a finding for [Known Issues](KNOWN_ISSUES.md).

## 3. Secrets management

**Never commit real secrets.** Confirm `.env` files are gitignored:

```bash
git ls-files Backend/.env UI/.env        # must return nothing
```

If tracked: `git rm --cached Backend/.env && git commit -m "remove tracked env"` and
**rotate every exposed key** (LLM providers, DB password, SECRET_KEY).

- **Local:** `.env` files (from `.env.example` / `production.env.example`).
- **Production host (compose):** `.env.production` on the host, referenced via
  `docker compose --env-file .env.production`.
- **CI/CD:** GitHub Actions Secrets (`SECRET_KEY` is not stored in the repo). See
  [CICD.md](CICD.md) for the full secret/variable list.
- **Managed platforms:** Railway/K8s use platform secret stores; never bake secrets into
  images. `NEXT_PUBLIC_*` values are the exception - they are public by design and baked
  into the UI build.

### Secret inventory

| Secret | Where | Rotation |
|--------|-------|----------|
| `SECRET_KEY` | env / CI secret | On suspected compromise; invalidates all tokens |
| `POSTGRES_PASSWORD` | env / secret store | Quarterly + on compromise |
| LLM provider keys | env / secret store | On compromise; scope per provider |
| `DEFAULT_ADMIN_PASSWORD` | env (seed only) | After first login; prefer disabling seed |
| `PROD_SSH_KEY`, `GHCR_DEPLOY_TOKEN` | GitHub Secrets | Per policy |

Secret rotation procedure: [RUNBOOK.md](RUNBOOK.md#secret-rotation).

## 4. Transport and network

- **TLS:** terminate at a reverse proxy / load balancer (not in the app). See
  [Infrastructure](INFRASTRUCTURE.md).
- **Trusted hosts:** `TrustedHostMiddleware` uses `ALLOWED_HOSTS` (explicit in prod).
- **CORS:** `CORS_ORIGINS` explicit in prod (no `*`).
- **IP allowlist:** `IP_ALLOWLIST_ENABLED` (optional).

## 5. Auditability

- **Immutable audit log:** hash-chained (`audit_log`), optionally EventStoreDB
  (`USE_EVENTSTORE`), with Postgres fallback. Retention `AUDIT_RETENTION_YEARS` (7).
- **Request logging:** every request logged to `request_logs`
  (`REQUEST_LOGGING_ENABLED`), excluding health/docs paths.
- **Error responses:** the global handler returns a generic message + `request_id` unless
  `DEBUG=true`, so stack traces are not leaked in production.

## 6. Production security checklist

- [ ] `ENV=production`, `AUTH_REQUIRED=true`, `DEBUG=false`.
- [ ] `SECRET_KEY` >= 32 random chars, from a secret store.
- [ ] `CORS_ORIGINS` and `ALLOWED_HOSTS` explicit (no `*`).
- [ ] `SEED_DEFAULT_USER=false` (or a strong `DEFAULT_ADMIN_PASSWORD` rotated after login).
- [ ] `.env*` gitignored; no secrets in git history; keys rotated.
- [ ] TLS enforced at the proxy; HSTS on.
- [ ] Elevated-role guard confirmed on all destructive/admin routes.
- [ ] Backups encrypted; audit retention configured.
