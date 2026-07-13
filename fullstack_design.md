# Sentinel Actalyst — Fullstack Design

> An AI sentinel that keeps watch over company websites, RSS/Atom feeds, and JSON APIs, detects newly-published content, summarizes each change as a short analyst briefing (with a severity and an AI-confidence rating) via OpenAI, and surfaces it in a **customer intelligence app** — with a separate **admin ops console** underneath and optional email delivery.

> **Naming note:** the product brand is **Sentinel Actalyst** (customer app) / **Sentinel Actalyst Ops** (admin). Several *internal* identifiers are historical and unchanged: the Python package is still `website_monitor`, the FastAPI title is `Website Monitor API`, the Celery app is `website_monitor`, and the default docker-compose project/volume names derive from the directory. These are invisible to users; don't mistake them for the brand.

---

## 1. High-Level Shape

```
React (Vite) SPA  --HTTP(+cookie)-->  FastAPI  --enqueue-->  Redis  --consume-->  Celery Worker
   customer app + admin console          |                                            |
   (one SPA, role-gated)                 v                                            v
                                     PostgreSQL  <------------------------------------+
                                                                                       |
                                                                            Crawl4AI / Firecrawl /
                                                                            Playwright / OpenAI / SMTP
```

The frontend never talks to the crawling engine directly — it only calls the FastAPI REST API (now with a session cookie). FastAPI never crawls synchronously — it enqueues Celery tasks and returns immediately, so HTTP requests stay fast even though crawling/summarizing can take seconds to minutes. A single SPA serves **two audiences** gated by the authenticated user's role (§3).

---

## 2. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend framework | React 19 + TypeScript | **Not Next.js** — see §3 |
| Frontend build tool | Vite 6 | dev server on port 3000 |
| Routing | Hand-rolled History-API router (`components/router.tsx`) | Mimics Next's `app/` folder convention, no Next.js runtime |
| Data fetching / cache | TanStack React Query v5 | Polling-based "live" updates, no WebSockets |
| HTTP client | Axios | `withCredentials: true` (session cookie) + timing/telemetry interceptors |
| UI kit | shadcn/ui ("new-york") on Radix primitives | `components/ui/*`; product-specific pieces in `components/intel/*` |
| Styling | Tailwind CSS v3 | `darkMode: "class"`; **real light + dark tokens now defined**; `radius: 0.7rem` |
| Icons / toasts | lucide-react, Sonner | brand mark is `ShieldCheck` |
| Backend framework | FastAPI ≥0.115 + Uvicorn | Python |
| Auth | Hand-rolled HMAC-signed cookie session (`backend/app/auth.py`) | env-configured + file-provisioned accounts, no user DB — see §4 |
| ORM / migrations | SQLAlchemy 2.0 (declarative) + Alembic | 6 revisions (§6) |
| Primary database | PostgreSQL 16 | via `psycopg` v3 |
| Task queue | Celery ≥5.4 | Redis as broker + result backend |
| Scheduler | Celery Beat | single 60s tick, DB-driven due-check |
| Crawling / link discovery | Crawl4AI 0.9.0 | async crawler, markdown/link extraction |
| Content scraping | Firecrawl (`firecrawl-py`) | fetches article markdown for summarization |
| Browser automation | Playwright (+ Patchright stealth fork) | headless Chromium network tracing for SPA/API discovery |
| LLM | OpenAI SDK ≥2.0, Chat Completions, model `gpt-5.4` | analyst-style summaries + severity/confidence + API-endpoint discovery planning |
| Email | `smtplib` (`mysignal/notifications/smtp_email.py`) | Gmail app-password shortcut or full SMTP override |
| Observability | Custom JSONL logger → `logs/app-health.jsonl` | no Prometheus/OTel |
| Containerization | Docker Compose, 6 services | see §7 |

---

## 3. Frontend — Detailed Behavior

**Important quirk (unchanged):** the `frontend/` directory has an `app/` folder laid out like a Next.js App Router project (`app/*/page.tsx`, `"use client"` directives), but there is **no Next.js dependency**. It's a plain Vite SPA reusing the naming convention. The real entry point is `frontend/src/main.tsx`.

### One SPA, two audiences, role-gated

`src/main.tsx` is the router + auth gate. It:
- Renders `/login` and `/admin/login` without a session.
- Otherwise checks the session (`GET /auth/me` via the auth provider); with no session it redirects to the appropriate login.
- Sends `/admin/*` routes to the **admin console** (`components/app-shell.tsx`, "Sentinel Actalyst Ops"), and everything else to the **customer app** (`components/customer-shell.tsx`, "Sentinel Actalyst"). A customer hitting `/admin/*` is bounced to `/dashboard`.

**This client-side gate is UX only, not the security boundary.** The real boundary is server-side: every customer router is `owner_name`-scoped and admin-only endpoints require the `AdminUser` dependency (§4).

### Customer app pages (`CustomerShell`)
| Route | File | Purpose |
|---|---|---|
| `/dashboard` | `dashboard/page.tsx` | "On watch" morning briefing: synthesized greeting line, "The Latest" hero insight, reframed value metrics, "needs review" list, activity pulse + trend, "what's quiet" line |
| `/monitors` | `monitors/page.tsx` | Monitor cards (favicon, monitoring-health line, activity sparkline, last update, priority badge, cadence) + an Add-monitor form (company, URL, **priority**, **check-every number + unit**) + per-card delete |
| `/monitors/:id` | `monitors/[id]/page.tsx` | Intelligence dossier: identity header (health line, priority), at-a-glance stats, full-width activity chart, insight timeline, editable cadence (number + unit), pause/resume, delete |
| `/insights` | `insights/page.tsx` | Intelligence feed of `InsightCard`s with search, "to review" filter, and a **sort dropdown** (newest/oldest, company priority, severity, confidence, company added newest/earliest, company A–Z); day-grouped for time sorts |
| `/trends` | `trends/page.tsx` | Aggregate rollup: volume-over-time pulse + week-over-week trend, breakdown by company, busiest monitors, KPI tiles |
| `/notifications` | `notifications/page.tsx` | Alert cadence (Automatic / Manual review) + per-company recipient chips |
| `/settings/workspace` | `settings/workspace/page.tsx` | Workspace / team (read-only) / billing (static) / account |
| `/onboarding` | `onboarding/page.tsx` | Single-form "post your first sentinel": name, URL, **priority**, **check-every number + unit**; a `ThinkingState` pulse narrates the baseline scan |
| `/login` | `login/page.tsx` | Customer login (ambient Signal waveform) |

### Admin console pages (`AppShell`, "Sentinel Actalyst Ops")
| Route | File | Purpose |
|---|---|---|
| `/admin/dashboard` | `page.tsx` | Ops dashboard — monitor-status metrics, discovery-engine health, recent runs, "Run all" |
| `/admin/accounts` | `admin/accounts/page.tsx` | List configured customers (companies/monitors/last login) + **register a new customer account** (writes the accounts file, live without restart) |
| `/admin/companies` · `/admin/sources` · `/admin/sources/:id` · `/admin/storage` · `/admin/email` · `/admin/runs` · `/admin/settings` | respective `page.tsx` | Original ops CRUD/inspection surfaces (sources, storage reconciliation, SMTP/recipients, run history, API base URL) |
| `/admin/login` | `login/page.tsx admin` | Staff login |

### Data layer (`lib/api.ts`)
- Single Axios instance, `withCredentials: true` so the session cookie rides along; `baseURL` from `VITE_API_BASE_URL` (default `http://localhost:8000`).
- Request/response interceptors time every call and pipe into `recordHealthEvent()` (frontend reports its own API telemetry).
- Fully-typed endpoint functions incl. `Company` (with `priority`), `Source`, `Summary` (with `severity`, `confidence`, `reviewed_at`), `InsightStats`, `AccountOverview`, auth, and the admin account-create call. Shared `getApiErrorMessage()` unwraps FastAPI's `{detail}`.
- Heavy operations (`run-all`, source `run`/`baseline`) return `{task_id, status:"queued"}`; the shared `lib/use-source-check.ts` hook polls `GET /tasks/:id` to a terminal state with a spinner, then invalidates queries.

### Design system (`app/globals.css`) — the "Signal" visual language
- **Radius `0.7rem`**; **both light and dark token sets are defined** (`.dark` block is real, though no in-app theme toggle mounts it yet).
- Brand teal `primary 199 89% 32%`; a signature **`--signal`** token drives the waveform motif; **`--confidence`** (indigo) is reserved for the confidence indicator; `--briefing-bg` for the dashboard header; motion tokens (`--dur-*`, `--ease-*`) + keyframes (`signal-draw`, `signal-drift`, `signal-sweep`, `pa-enter`, `pa-highlight`), all gated behind `prefers-reduced-motion`.
- Product components in **`components/intel/`**: `ActivityPulse` (SVG pulse/area chart — the one chart, three sizes), `AmbientSignal` (drifting header waveform), `ConfidenceSignal` (bar indicator), `SeverityBadge`, `PriorityBadge`, `CompanyFavicon` (real favicon + initials fallback), `InsightCard` (headline + one analyst paragraph + severity/confidence/priority), `CadenceField` (number + unit), `ThinkingState`, `AnalystEmptyState`, `ConfirmDialog`.

### "Real-time" is polling + a telemetry beacon (unchanged)
No WebSocket/SSE. (1) Task progress polls `GET /tasks/{id}` every 2s. (2) `lib/health-events.ts` posts `{event_type, action, metadata}` to `POST /health/events` via `navigator.sendBeacon` from the Axios interceptors and `route-logger.tsx` — a one-way beacon into the JSONL health log.

### Deployment quirk (unchanged)
`frontend/Dockerfile` runs `npm run dev` (Vite dev server on `0.0.0.0:3000`) — there is no `vite build`/static stage. "Production" frontend here is the dev server. **Consequence: the frontend image bakes the source at build time (no code bind-mount), so frontend changes require `docker compose build frontend`.** Same is true for the Python image and `mysignal`/migrations.

---

## 4. Backend — Detailed Behavior

### `backend/app/main.py`
- FastAPI app with a `lifespan` handler logging startup/shutdown.
- CORS restricted to `http://localhost:3000` and `http://127.0.0.1:3000`, **`allow_credentials=True`** (required for the cookie session).
- Custom HTTP middleware times/logs every request (`backend_request` events).
- Registers **11 routers** and an auth layer: `health, auth, admin, companies, email, insights, sources, storage, runs, monitor, tasks`.

### Authentication (`backend/app/auth.py`) — new
- **No signup, no user table.** Accounts load at process start from env vars: one `ADMIN_NAME`/`ADMIN_PASSWORD` (role `admin`) plus any number of `USER_<n>_NAME`/`USER_<n>_PASSWORD` (role `customer`).
- **Runtime-provisioned accounts** are merged from `mysignal/data/accounts.json` (a mounted, persisted file), so an admin can register customers from the UI and they work **immediately, no restart** (the in-memory `CONFIG_ACCOUNTS` dict is updated on registration). Env accounts win on a name clash. *(Passwords are stored plaintext, same posture as the env vars; the file is gitignored. Live-without-restart assumes the single uvicorn worker this compose runs.)*
- **Session:** `pulseactalyst_session` cookie — `base64(payload).hmac_sha256`, signed with `AUTH_SECRET` (falls back to a `DATABASE_URL`-derived value for local dev), `httponly`, `samesite=lax`, 7-day.
- **Dependencies:** `CurrentUser` (any valid session → 401 otherwise) and `AdminUser` (`CurrentUser` + `role=="admin"` → 403). Every customer-facing router derives an `_owner_filter(user)` (`None` for admin = see everything; the account name for customers) and passes it into CRUD, which adds a `WHERE companies.owner_name = :owner` (directly or via join).

### Routers → responsibility
| Router | Prefix | Auth | Key endpoints |
|---|---|---|---|
| `health` | `/health` | open | `GET /health`, `GET /health/discovery`, `POST /health/events` |
| `auth` | `/auth` | — | `POST /login`, `GET /me`, `POST /logout` |
| `admin` | `/admin` | AdminUser | `GET /accounts` (usage rollup), `POST /accounts` (register customer) |
| `companies` | `/companies` | CurrentUser (owner-scoped) | CRUD incl. `priority`; 409 on duplicate name; delete cascades |
| `sources` | `/sources` | CurrentUser (owner-scoped) | CRUD; `/runs`, `/discovered-urls`, `/summaries`, `/discovery-preview`; `POST /baseline`, `POST /run` |
| `insights` | `/insights` | CurrentUser (owner-scoped) | `GET ""` (summaries feed), `GET /stats` (daily/company/busiest/avg-time), `PATCH /{id}/review` |
| `runs` | `/runs` | CurrentUser | list / run detail |
| `storage` | `/storage` | CurrentUser | JSON store + `discovered_urls` reconciled view |
| `monitor` | `/monitor` | `run-all` AdminUser · `status` CurrentUser | `POST /run-all`, `GET /status` |
| `tasks` | `/tasks` | CurrentUser | `GET /{task_id}` (Celery `AsyncResult` poll) |
| `email` | `/email` | CurrentUser (owner-scoped) | SMTP status, mode, recipients CRUD, summaries, manual send |

### Orchestration core — `backend/app/services/monitor_service.py`
- `run_baseline(source_id)` — seeds `seen_url_records.json` via strategy-specific baseline functions, then mirrors those URLs into `discovered_urls` (no summaries → first run never emails a backlog).
- `run_monitor(source_id)` — the per-source loop: if unbaselined, baseline instead; else discover new URLs (`mysignal.workflows.*`), and per new URL: record a `DiscoveredUrl`, scrape+summarize via `new_url_processor`, persist a `Summary` (with parsed **severity + confidence**), and email only if global mode is `automatic`.
- **Summary capture + parse:** `_capture_article()` monkeypatches the summarizer entry point under a lock; it runs `parse_insight_output()` (`mysignal.summarizers.insight_format`) on the raw model text to split out a clean **headline + paragraph** and the **severity/confidence** values, rewrites the article to the clean prose (so email/logs get the paragraph, not the labels), and hands them to `_log_summary()`.
- `run_all_enabled_sources()` — sequential loop over enabled sources.
- Recipient lookup falls back from the DB `NotificationRecipient` table to a legacy JSON file (migration-in-progress artifact, §5).

### Background jobs (`backend/app/workers/`) — unchanged
- `celery_app.py` — `Celery("website_monitor", broker/back­end=REDIS_URL)`; Beat fires `monitor.scheduler_tick` every **60s**.
- `monitor_worker.py` — thin task wrappers (`ping_worker`, `baseline_source_task`, `monitor_source_task`, `run_all_enabled_sources_task`).
- `scheduler.py` — `scheduler_tick`: for each `Source`, checks enabled + due (`last_checked_at + schedule_minutes <= now`) + not-already-running, and enqueues `monitor_source_task`. One dynamic tick replaces per-source Beat entries.

### Configuration & Observability — unchanged
- `backend/app/config.py` holds only `database_url` + `redis_url`; everything else (`OPENAI_API_KEY`, `FIRECRAWL_API_KEY`, SMTP, `DISCOVERY_*` knobs, `AUTH_SECRET`, account vars) is read ad hoc via `os.getenv()`.
- `observability.py` — `log_health_event(...)` appends one JSON line to `logs/app-health.jsonl` (thread-safe, size-rotated); backs `GET /health/discovery`. No Prometheus/OTel.

---

## 5. The `mysignal` Engine (Crawling / Discovery / Summarization)

`mysignal` is imported **in-process** by FastAPI and the Celery workers — no HTTP/RPC boundary. Legacy CLI entry points (`mysignal/main.py`, `mysignal/monitor.py`) remain but aren't used by the running system.

| Subpackage | Purpose |
|---|---|
| `discovery/page_links.py` | HTML link extraction (Crawl4AI → requests+BeautifulSoup fallback); classifies DOM region |
| `discovery/api_discovery.py` | Deterministic JS/API endpoint discovery: framework fingerprinting, inline state extraction, JS bundle scanning, endpoint validation/scoring |
| `discovery/advanced_discovery.py` | Heavy discovery: Playwright network tracing + OpenAI-assisted endpoint planner, cached per-domain to `discovery_adapters.json`, file-locked; exposes `discovery_health_summary()` |
| `crawler/crawl4ai_collector.py` | BFS site crawler (legacy CLI hub-discovery) |
| `collector/firecrawl_collector.py` | `FirecrawlApp.scrape_url(..., formats=["markdown"])` — the content scraper for summarization |
| `filters/content_filter.py` | Blocks non-article extensions |
| `monitoring/inventory_store.py` | JSON file persistence: `seen_url_records.json` (append-only "seen URL" ledger), `tracked_recursive_roots.json`, `inventory.json`, `discovery_adapters.json` |
| `workflows/parent_monitor.py`, `feed_monitor.py`, `api_monitor.py` | Per-strategy discovery + diff-against-seen (extract → normalize → set-difference vs the seen ledger → record new) |
| `workflows/new_url_processor.py` | Per-URL pipeline: scrape → summarize → (maybe) email → persist to the seen ledger **only on success** (so a failed scrape stays queued for retry) |
| `processors/article_processor.py` | Firecrawl scrape → `Article` model |
| `summarizers/openai_summarizer.py` | OpenAI Chat Completions (`gpt-5.4`). System prompt is now a **business-intelligence analyst**: returns `HEADLINE:` + `SUMMARY:` (one flowing paragraph, significance woven in — no bullet/section labels) + `SEVERITY:` (low/medium/high) + `CONFIDENCE:` (low/medium/high) |
| `summarizers/insight_format.py` | Dependency-free parser for that output → `{headline, body, severity, confidence}`; tolerant of the older `HEADLINE/UPDATE/KEY DETAILS/FOLLOW UP` format and of unlabeled text |
| `notifications/smtp_email.py` | Builds/sends the notification email via `smtplib` |

**Known dual-source-of-truth (unchanged):** URL de-dup lives in *both* Postgres (`discovered_urls`/`seen_urls`) *and* `mysignal/data/seen_url_records.json`. The live write path uses the JSON ledger; `routers/storage.py` reconciles both. Migration-in-progress artifact, not a bug.

> `mysignal/data/` also now holds `accounts.json` (runtime-provisioned auth accounts, written by `backend/app/auth.py` — not a `mysignal` concern, it just shares the mounted, persisted directory).

---

## 6. Database

- **Engine:** PostgreSQL 16, SQLAlchemy 2.0 declarative, Alembic. **6 revisions:**
  1. `0001` initial schema → 2. `0002` `sources.last_checked_at` → 3. `0003` email delivery fields + `app_settings` → 4. `0004` account scoping + insight review (`companies.owner_name`, `summaries.severity`, `summaries.reviewed_at`) → 5. `0005` `summaries.confidence` → 6. `20260711_0006` `companies.priority`.
- **Tables:**
  - `companies` — `name`, **`owner_name`** (which account owns it), **`priority`** (high/medium/low; customer-set, drives feed sorting); 1:N `sources`, `notification_recipients`.
  - `sources` — `url`, `strategy`, `trace_js`, `js_bundle_sources`, `enabled`, `schedule_minutes`, `last_checked_at`.
  - `summaries` — `title`, `summary` (clean analyst paragraph), `model`, **`severity`**, **`confidence`**, **`reviewed_at`**, `email_status`/`sent_at`/`error`.
  - `seen_urls` (DB analog of the JSON ledger, largely superseded in the live path) · `monitor_runs` · `discovered_urls` (payload JSON, FK to run) · `notification_recipients` · `app_settings` (currently `email_notification_mode`).
- **Auth accounts are NOT in the DB** — env vars + `mysignal/data/accounts.json` (§4).
- **Redis:** Celery broker + result backend only.

> **Cross-branch migration note:** feature branches may each introduce their own `..._0006` revision off `0005` (this branch's is `20260711_0006` for `priority`). Merging two such branches produces multiple Alembic heads and needs an `alembic merge`. Per-branch DB volumes (§7) keep their *state* from colliding at runtime.

---

## 7. Docker Compose Topology

| Service | Image / Build | Port | Role |
|---|---|---|---|
| `frontend` | `frontend/Dockerfile` | 3000 | Vite dev server (see §3 note) |
| `backend` | `backend/Dockerfile` | 8000 | FastAPI (`uvicorn`), runs `alembic upgrade head` on boot |
| `celery-worker` | same Dockerfile | — | Executes crawl/baseline/summarize tasks (concurrency 2, `-Ofair`) |
| `celery-beat` | same Dockerfile | — | Fires `scheduler_tick` every 60s |
| `postgres` | `postgres:16` | 5432 | Primary datastore |
| `redis` | `redis:7` | 6379 | Celery broker/result backend |

`backend`, `celery-worker`, `celery-beat` bind-mount `./logs` and `./mysignal/data` (health log, JSON ledger, **`accounts.json`**, adapter cache — shared/persisted). `backend/Dockerfile` installs Playwright **and** Patchright with Chromium for heavy browser discovery.

**Per-branch isolation:** a committed `post-checkout` git hook (`.githooks/post-checkout`, enabled via `git config core.hooksPath .githooks`) writes `COMPOSE_PROJECT_NAME=sentinel-<branch>` into `.env` on every branch switch, so each git branch gets its **own containers and its own Postgres volume**. This prevents the classic "DB is stamped at a migration this branch's code doesn't contain" failure when hopping branches. Because all branches publish the same host ports, only one branch's stack should be `up` at a time (`docker compose down` before switching).

---

## 8. End-to-End Flow (one monitoring cycle)

1. A customer (or admin) posts a `Company` + `Source` (URL, strategy, **priority**, **check interval as number + unit → `schedule_minutes`**) from onboarding or the Monitors page.
2. `POST /sources/{id}/baseline` → Celery `baseline_source_task` seeds `seen_url_records.json` + mirrors to `discovered_urls` (no summaries → no first-run backlog email).
3. Celery Beat's `scheduler_tick` (every 60s) finds due sources and enqueues `monitor_source_task`.
4. The strategy workflow discovers candidate URLs, filters them, and diffs against the seen ledger → the genuinely new URLs.
5. Each new URL: Firecrawl scrapes content → `openai_summarizer` produces an analyst paragraph + severity + confidence → `insight_format` parses it → a `Summary` row is persisted (seen ledger updated only on success).
6. If email mode is `automatic`, `smtp_email` sends immediately; if `manual`, it waits for a click in the admin `/email` view.
7. The customer sees the update in the **Insights feed** (sortable by priority/severity/confidence/recency/company), the **dashboard briefing**, and the monitor **dossier**; they can mark it reviewed.
8. Every step — HTTP, Celery lifecycle, discovery, email, frontend routes/API calls — is appended to `logs/app-health.jsonl`, which backs `/health/discovery`.

---

## 9. Notable Rough Edges (worth knowing before making changes)

- **`app/` naming is misleading** — plain Vite SPA with a hand-rolled router; Next.js conventions (server components, file-based routing, middleware) do **not** apply. `"use client"` directives are dead scaffolding.
- **Images bake the source at build time** — the frontend and Python images have **no code bind-mount**, so any backend/`mysignal`/migration/frontend change needs a `docker compose build` before it takes effect. A stale image whose migrations lag the DB will crash on boot (`Can't locate revision …`).
- **Auth is cookie-session, not a trust boundary at the client** — the `/admin` path gate in `main.tsx` is UX; the real enforcement is `owner_name` scoping + `AdminUser` server-side. `AUTH_SECRET` must be set explicitly anywhere shared.
- **Plaintext account passwords** — env vars and `accounts.json` both store plaintext; `accounts.json` is gitignored. Live account registration assumes the single uvicorn worker this compose runs.
- **Dual seen-URL storage** (Postgres + JSON ledger) — `routers/storage.py` is the only reconciliation point; code needing authoritative "seen?" answers should consult both. The live path only marks a URL seen after a *successful* summary (so a Firecrawl outage leaves new URLs queued, not silently swallowed).
- **Frontend Docker image runs the dev server**, not a production build — fine locally, not for a public LB.
- **Config is split** between `config.py` (DB/Redis) and scattered `os.getenv()` calls.
- **"Month" cadence = 30 days**; the interval is always stored as `schedule_minutes` regardless of the unit the customer picked.
