# Solace AI — Clinical-Evidence Research Assistant

A multi-agent RAG system that turns one biomedical question into a structured,
fully-cited, evidence-graded literature review. Backend: FastAPI + (Groq LLMs).
Retrieval: live PubMed E-utilities. Frontend: single-page workbench served by the
same service. Hosting target: **Render** (one web service + managed PostgreSQL).

> Design docs live in [`build doc/`](build%20doc/). This README covers the runnable app.

**Status: build complete (P0–P5).** All phases are implemented and tested end-to-end locally.
Remaining steps are deployment-only: push to GitHub and click-deploy on Render (see below).

## Build status

| Part | Status |
|---|---|
| P0 — scaffold, config, Render blueprint, static serving | ✅ done |
| P1 — JWT auth (researcher-only), Postgres/SQLite models, frontend login/register | ✅ done |
| P2 — live PubMed retrieval + BM25 hybrid ranking | ✅ done |
| P3 — Groq client (primary+fallback keys) + 7-stage LangGraph pipeline | ✅ done |
| P4 — query API + real Answer/Explanation/Citations/Stats/Log + PDF/MD export | ✅ done |
| P5 — deploy config + polish (favicon, README, Blueprint) | ✅ done |

There is **no admin role** — researcher accounts only.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then edit .env (GROQ_API_KEY, JWT_SECRET, NCBI_EMAIL)
uvicorn backend.app.main:app --reload --port 8000
# open http://localhost:8000  → register a researcher account
```

Local dev uses SQLite (`solace_dev.db`) automatically; Render injects Postgres via `DATABASE_URL`.

## Configuration (environment variables)

| Var | Required | Notes |
|---|---|---|
| `GROQ_API_KEY` | for P3+ | free key at console.groq.com |
| `GROQ_MODEL_SMALL` / `GROQ_MODEL_LARGE` | no | defaults: `llama-3.1-8b-instant` / `llama-3.3-70b-versatile` |
| `JWT_SECRET` | yes | `openssl rand -hex 32` |
| `DATABASE_URL` | no (local) | SQLite by default; Render sets Postgres |
| `NCBI_EMAIL` | no | contact email for PubMed etiquette |
| `NCBI_API_KEY` | no | optional; raises PubMed rate limit |
| `ALLOW_OPEN_REGISTRATION` | no | `true` by default |

Secrets are **never** committed — `.env` is gitignored; set real values in Render's dashboard.

## Project layout

```
backend/app/
  main.py            # FastAPI app, serves API + static frontend
  config.py db.py    # settings + SQLAlchemy engine/session
  models.py          # users, refresh_tokens, queries, claims, citations, provenance, stage_logs
  security.py deps.py# argon2 hashing, JWT, get_current_user
  schemas.py
  routers/auth.py    # register / login / refresh / logout / me
  services/
    pubmed.py        # NCBI E-utilities client
    retrieval.py     # BM25 hybrid ranking over live results
frontend/index.html  # single-page workbench (served at /)
render.yaml          # Render Blueprint (web service + Postgres)
requirements.txt
```

## API (current)

```
GET  /health
GET  /api/v1/config
POST /api/v1/auth/register  {email, password, display_name?}  -> {access_token, refresh_token, user}
POST /api/v1/auth/login     {email, password}                 -> {access_token, refresh_token, user}
POST /api/v1/auth/refresh   {refresh_token}                    -> {access_token}
POST /api/v1/auth/logout    {refresh_token}                    -> 204
GET  /api/v1/auth/me        (Bearer)                           -> {id, email, display_name}

POST /api/v1/queries        (Bearer) {query}   -> runs the 7-stage pipeline, returns full result
GET  /api/v1/queries        (Bearer)           -> list your queries
GET  /api/v1/queries/{id}   (Bearer)           -> one result (ownership-checked)
GET  /api/v1/queries/{id}/export?format=md|pdf (Bearer)  -> download
```

### Pipeline (P3)

`backend/app/services/`: `llm.py` (Groq client — tiered small/large models, **primary→fallback
key failover**, retries, JSON mode) and `pipeline.py` (LangGraph 7-stage graph:
Researcher → Retriever → Graph-Builder → Corroborator → Fact-Checker → Synthesizer → Editor).
Grounded in live PubMed; degrades rather than fails (no sources → abstain; graph gaps → flat RAG).

### Research depth (tunable — env vars)

Deeper research = more sources + richer claims + a long structured explanation, all still
grounded/cited (precision preserved via "cite provided PMIDs or abstain"). Trade-off: a query
takes ~30–40s and ~10–15k Groq tokens. Turn these down to go faster/cheaper:

| Var | Default | Effect |
|---|---|---|
| `PIPELINE_MULTI_QUERY` | `true` | Retrieve per sub-question (union), not just the main query |
| `PUBMED_RETMAX` / `PIPELINE_SUBQUERY_RETMAX` | `30` / `15` | Abstracts fetched per main / sub search |
| `PIPELINE_TOP_K` | `12` | Passages kept after BM25 |
| `FACTCHECK_PASSAGES` / `FACTCHECK_ABSTRACT_CHARS` | `12` / `1400` | Sources & near-full abstracts shown to the fact-checker |
| `FACTCHECK_MAX_TOKENS` / `SYNTH_MAX_TOKENS` | `3500` / `4000` | Output length for claims / the deep-dive explanation |

## Deploy to Render

The repo ships a `render.yaml` **Blueprint** that provisions the web service **and** a managed
PostgreSQL, and wires `DATABASE_URL` automatically.

1. **Push this repo to GitHub** (see below).
2. In Render: **New + → Blueprint** → connect the repo → **Apply**. Render reads `render.yaml`
   and creates the `solace` web service + `solace-db` Postgres.
3. Open the `solace` service → **Environment** → set the two secrets (marked `sync: false`):
   - `GROQ_API_KEY` — your primary Groq key
   - `GROQ_API_KEY_FALLBACK` — your fallback key (optional)
   - `NCBI_EMAIL` — any contact email
   `JWT_SECRET` is auto-generated by Render; model IDs and depth defaults are pre-set.
4. **Deploy**. First boot runs DB migrations (table creation) automatically via the app lifespan.
5. Open the service URL → **Register** a researcher account → run a query.

**Free-tier notes:** the web service cold-starts after 15 min idle (~30–60s first hit); a deep
query holds the worker ~30–40s (fine for a demo — upgrade the instance for smoother concurrency).
Render free Postgres expires after 90 days; recreate or upgrade for longer-lived data.

## Push to GitHub

```bash
git remote add origin https://github.com/LeoPanthera07/Solace---Research-Assistant-.git
git push -u origin main
```

`.env` (your real keys) is gitignored and will **not** be pushed. Set secrets in Render's dashboard.
