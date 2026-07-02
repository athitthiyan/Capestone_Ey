# Skeptic Engine — Free-Tier Production Deployment Guide

A practical, step-by-step guide to get the whole app (FastAPI backend + Next.js UI +
Postgres) live on free hosting, with every third-party API key sourced for free.

---

## 0. Pre-flight: codebase health & must-fix items

**Health check:** the full backend compiles (`compileall app` clean), the LLM stack
(Anthropic, Groq, OpenAI, Gemini) imports and runs, migrations exist, and both
Dockerfiles are present. You're in good shape to deploy.

**Fix these BEFORE going live (important):**

1. **Rotate every API key.** Your `Backend/.env` currently has live Anthropic, Groq,
   OpenAI, Gemini, and aviationstack keys committed to the repo. Anyone with the git
   history has them. Rotate all of them and never commit real keys again.
2. **Confirm `.env` is gitignored.** Check `git ls-files Backend/.env` returns nothing.
   If it's tracked, run `git rm --cached Backend/.env` and commit.
3. **Set production security env** (details in §5): `AUTH_REQUIRED=true`,
   a 32+ char `SECRET_KEY`, explicit `CORS_ORIGINS`/`ALLOWED_HOSTS` (no `*`),
   and `ENV=production`.

---

## 1. What you actually need (minimal free stack)

You do **not** need Redis, Celery, or EventStoreDB to run in production. Keep them off
and the app runs everything in-process with audit logs stored in Postgres:

- `USE_CELERY=false` — investigations run inside the API request.
- `USE_REDIS_EVENTS=false` — realtime uses the in-process event bus.
- `USE_EVENTSTORE=false` + `AUDIT_FALLBACK_TO_POSTGRES=true` — audit trail in Postgres.

**Recommended free stack:**

| Piece | Service | Free tier | Why |
|---|---|---|---|
| Frontend (Next.js) | **Vercel** | Yes (Hobby) | Native Next.js, zero-config |
| Backend (FastAPI) | **Render** (or Railway/Fly.io) | Yes | Docker or Python native |
| Database (Postgres) | **Neon** (or Supabase) | Yes | Serverless Postgres, generous free tier |
| LLM (primary) | **Groq** and/or **Google Gemini** | Yes, truly free | See §2 |

> Trade-off: Render's free web service sleeps after ~15 min idle (cold starts ~30s).
> Railway/Fly.io give more always-on headroom on trial credit. For a demo, free Render
> is fine.

---

## 2. Get every third-party API key — free

### LLM providers (pick your default from the two truly-free ones)

| Provider | Free? | Where to get the key | Notes |
|---|---|---|---|
| **Groq** (Llama) | ✅ Free | https://console.groq.com → *API Keys* | Fast, generous free limits. Great default. |
| **Google Gemini** | ✅ Free | https://aistudio.google.com/app/apikey | Free tier with daily quota. Great default/fallback. |
| **Anthropic (Claude)** | 💳 Paid | https://console.anthropic.com | No standing free tier; pay-as-you-go (new accounts sometimes get trial credit). |
| **OpenAI (GPT)** | 💳 Paid | https://platform.openai.com/api-keys | Pay-as-you-go; new accounts sometimes get trial credit. |

**Recommendation:** set `DEFAULT_LLM_PROVIDER=groq` (or `gemini`) and
`LLM_FALLBACK_ORDER=gemini,groq` so you stay on free providers. Add Anthropic/OpenAI
only if you have credits. Fallback now also triggers on rate-limit, quota, and
model-not-found, so if one free provider is throttled it automatically tries the next.

### Evidence-verification providers

| Category | Provider | Free? | Where |
|---|---|---|---|
| Currency (FX) | **Frankfurter** | ✅ Free, **no key** | Already wired (`FX_API_BASE_URL`) |
| Flight | **aviationstack** | ✅ Free (100 req/mo) | https://aviationstack.com/product |
| GST (India) | **Appyflow** | ✅ Free tier | https://appyflow.in/gst-api |
| Fuel | **CollectAPI** | ✅ Free tier | https://collectapi.com/api/gasPrice |
| Hotel | **Amadeus Self-Service** | ✅ Free test tier | https://developers.amadeus.com |

Leave any provider URL/key blank and that category simply returns `API_UNAVAILABLE`
(nothing breaks). FX works out of the box with no key.

---

## 3. Deploy the database (Neon Postgres) — free

1. Sign up at https://neon.tech and create a project (pick a region near your users).
2. Copy the **connection string** — it looks like
   `postgresql://user:pass@ep-xxx.region.aws.neon.tech/dbname?sslmode=require`.
3. Keep it handy — it becomes `DATABASE_URL` for the backend.

That's it. Migrations run in the next step.

---

## 4. Deploy the backend (Render) — free

1. Push your repo to GitHub (with real secrets removed — see §0).
2. On https://render.com → **New → Web Service** → connect the repo.
3. Settings:
   - **Root directory:** `Backend`
   - **Runtime:** Docker (a `Dockerfile` is present) — or Python 3.11 with
     Build: `pip install -r requirements.txt`, Start: below.
   - **Start command:**
     ```
     alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```
     (The `alembic upgrade head` applies all DB migrations on boot.)
4. **Environment variables** (Render → Environment). Minimum set:
   ```
   ENV=production
   DEBUG=false
   DATABASE_URL=<your Neon connection string>
   SECRET_KEY=<32+ random chars>
   AUTH_REQUIRED=true
   SEED_DEFAULT_USER=true
   DEFAULT_ADMIN_USERNAME=admin
   DEFAULT_ADMIN_PASSWORD=<12+ char strong password>
   DEFAULT_ADMIN_ROLE=partner

   USE_REAL_AGENTS=true
   DEFAULT_LLM_PROVIDER=groq
   ENABLE_LLM_FALLBACK=true
   LLM_FALLBACK_ORDER=gemini,openai
   GROQ_API_KEY=<your groq key>
   GEMINI_API_KEY=<your gemini key>
   # optional: ANTHROPIC_API_KEY / OPENAI_API_KEY if you have credit

   USE_CELERY=false
   USE_REDIS_EVENTS=false
   USE_EVENTSTORE=false
   AUDIT_FALLBACK_TO_POSTGRES=true

   CORS_ORIGINS=["https://YOUR-UI.vercel.app"]
   ALLOWED_HOSTS=["YOUR-API.onrender.com"]

   # evidence providers (optional, all free tiers)
   FLIGHT_PRICE_PROVIDER_URL=https://api.aviationstack.com/v1/
   FLIGHT_PRICE_PROVIDER_API_KEY=<aviationstack key>
   ```
   Generate `SECRET_KEY` with: `python -c "import secrets; print(secrets.token_hex(32))"`.
5. Deploy. When it's live, note the URL, e.g. `https://skeptic-api.onrender.com`.
6. Verify: open `https://skeptic-api.onrender.com/health` → should return healthy.

> You can fill `CORS_ORIGINS`/`ALLOWED_HOSTS` after step 5 once you know the UI URL —
> just redeploy the backend after setting them.

---

## 5. Deploy the frontend (Vercel) — free

1. On https://vercel.com → **Add New → Project** → import the same repo.
2. Settings:
   - **Root directory:** `Ui`
   - Framework preset: **Next.js** (auto-detected). Build/install commands auto.
3. **Environment variables:**
   ```
   NEXT_PUBLIC_API_BASE_URL=https://skeptic-api.onrender.com/api/v1
   NEXT_PUBLIC_API_USERNAME=admin
   NEXT_PUBLIC_API_PASSWORD=<the DEFAULT_ADMIN_PASSWORD you set on the backend>
   ```
   (Or issue a bearer token and set `NEXT_PUBLIC_API_TOKEN` instead of user/pass.)
4. Deploy. Note the URL, e.g. `https://skeptic-engine.vercel.app`.
5. **Go back to Render** and set `CORS_ORIGINS=["https://skeptic-engine.vercel.app"]`
   and `ALLOWED_HOSTS=["skeptic-api.onrender.com"]`, then redeploy the backend.

---

## 6. Post-deploy verification

1. Open the Vercel URL → the dashboard should load and talk to the backend.
2. Go to **Upload data**, import a small ledger, **Create cases & run crew**.
3. Watch the **Case workspace** — the agent workflow and cost panel update live.
4. Check **Analytics** → the LLM cost total climbs (real agents are on).
5. Check **Quality scores** and a case's per-case RAGAS.
6. Try **Settings → LLM provider routing** — switch the default provider and confirm
   the next run uses it.

---

## 7. Production hardening checklist

- [ ] All API keys rotated; none committed. `.env` gitignored.
- [ ] `ENV=production`, `DEBUG=false`, `AUTH_REQUIRED=true`.
- [ ] `SECRET_KEY` ≥ 32 random chars.
- [ ] `CORS_ORIGINS` and `ALLOWED_HOSTS` are explicit (no `*`).
- [ ] Strong `DEFAULT_ADMIN_PASSWORD` (≥ 12 chars) or seeding disabled.
- [ ] `DATABASE_URL` uses `sslmode=require` (Neon does by default).
- [ ] Migrations applied (`alembic upgrade head` in the start command).
- [ ] LLM default + fallback point at providers you have working keys for.
- [ ] Set a per-provider `*_TEMPERATURE` (already tuned low for accuracy).
- [ ] Watch spend: the Analytics cost panel is your live meter; set provider budget caps.

The backend already **enforces** most of these — with `ENV=production` it will refuse
to boot if `AUTH_REQUIRED` is false, `SECRET_KEY` is weak, or CORS/hosts use `*`.

---

## 8. Scaling up later (optional, not needed for launch)

When volume grows, flip these on:

- **Redis (Upstash, free)** → set `REDIS_URL`, `USE_REDIS_EVENTS=true`, and Celery
  broker/result URLs. Enables multi-instance realtime + background jobs.
- **Celery workers** → `USE_CELERY=true` and run a worker process
  (`celery -A app.tasks.celery_app worker`). Investigations then run off the request path.
- **EventStoreDB** → `USE_EVENTSTORE=true` for a dedicated immutable audit stream.
- The included `docker-compose.production.yml` and `k8s-deployment.yaml` wire all of
  this if you'd rather self-host on a VPS or Kubernetes.

---

## 9. Things easy to miss (gotchas)

1. **Two different "model" settings.** *Settings → LLM provider routing* (default
   provider + fallback) is what actually controls which model runs. The governance
   *"reasoning model"* text field on the settings form is a display/policy value and
   does not by itself reroute calls. Switch providers via the routing card.
2. **Free LLM quotas are small.** Running 100 cases will exhaust Gemini/Groq free
   quotas fast — you'll see 429s (which now auto-fall back). Run in small batches or
   add billing for real volume.
3. **Model names drift.** Providers retire model IDs (that's what caused the Claude and
   Gemini "not found" errors). If a provider 404s, list its models and update the
   `*_MODEL_REASONING` / `*_MODEL_LIGHTWEIGHT` env vars:
   - Anthropic: `GET https://api.anthropic.com/v1/models` (header `x-api-key`)
   - Gemini: `GET https://generativelanguage.googleapis.com/v1beta/models?key=KEY`
4. **Render free tier sleeps.** First request after idle is slow. Use a cron pinger or
   upgrade if you need always-on.
5. **RAGAS scores need run cases.** The overall score now excludes un-run `intake`
   imports, but a case only earns scores after it's been through the crew.
6. **Set `NEXT_PUBLIC_*` at build time.** Vercel bakes these into the frontend build —
   changing them requires a redeploy.
7. **Aviationstack free tier is flight *status*, not fares** — the flight benchmark may
   return limited data; other categories (FX/GST/fuel/hotel) are more directly useful.
