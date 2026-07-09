# Website Monitor — Fullstack Design

> A local operations console that watches company websites, RSS/Atom feeds, and JSON APIs for new content, summarizes changes with OpenAI, and emails the results to configured recipients.

---

## 1. High-Level Shape

```
React (Vite) SPA  --HTTP-->  FastAPI  --enqueue-->  Redis  --consume-->  Celery Worker
                                 |                                            |
                                 v                                            v
                             PostgreSQL  <------------------------------------+
                                                                               |
                                                                    Crawl4AI / Firecrawl /
                                                                    Playwright / OpenAI / SMTP
```

The frontend never talks to the crawling engine directly — it only calls the FastAPI REST API. FastAPI never crawls synchronously — it enqueues Celery tasks and returns immediately, so HTTP requests stay fast even though crawling/summarizing can take seconds to minutes.

---

## 2. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend framework | React 19 + TypeScript | **Not Next.js** — see §3 |
| Frontend build tool | Vite 6 | `vite.config.mjs`, dev server on port 3000 |
| Routing | Hand-rolled History-API router (`components/router.tsx`) | Mimics Next's `app/` folder convention, no actual Next.js runtime |
| Data fetching / cache | TanStack React Query v5 | Polling-based "live" updates, no WebSockets |
| HTTP client | Axios | Wrapped with timing + telemetry interceptors |
| UI kit | shadcn/ui ("new-york" style) on Radix primitives | `components/ui/*` |
| Styling | Tailwind CSS v3 | `darkMode: "class"` configured but no `.dark` theme vars defined |
| Icons / toasts | lucide-react, Sonner | |
| Backend framework | FastAPI ≥0.115 + Uvicorn | Python |
| ORM / migrations | SQLAlchemy 2.0 (declarative) + Alembic | |
| Primary database | PostgreSQL 16 | via `psycopg` v3 |
| Task queue | Celery ≥5.4 | Redis as both broker and result backend |
| Scheduler | Celery Beat | single 60s tick, DB-driven due-check (not per-source Beat entries) |
| Crawling / link discovery | Crawl4AI 0.9.0 | async BFS crawler, markdown/link extraction |
| Content scraping | Firecrawl (`firecrawl-py`) | fetches article markdown for summarization |
| Browser automation | Playwright (+ Patchright, a stealth fork) | headless Chromium network tracing for SPA/API discovery |
| LLM | OpenAI SDK ≥2.0, Chat Completions, model `gpt-5.4` | article summarization + API-endpoint discovery planning |
| Email | `smtplib` (`mysignal/notifications/smtp_email.py`) | Gmail app-password shortcut or full SMTP override |
| Observability | Custom JSONL logger → `logs/app-health.jsonl` | no Prometheus/OTel |
| Containerization | Docker Compose, 6 services | see §6 |

---

## 3. Frontend — Detailed Behavior

**Important quirk:** the `frontend/` directory has an `app/` folder laid out exactly like a Next.js App Router project (`app/companies`, `app/sources/[id]`, `page.tsx` files, `"use client"` directives at the top of components), but there is **no Next.js dependency anywhere**. It's a plain Vite SPA that reuses the naming convention for organization only. The real entry point is `frontend/src/main.tsx`.

### How routing actually works
- `frontend/index.html` loads `/src/main.tsx` as a module into `<div id="root">`.
- `src/main.tsx` statically imports every page component from `app/*/page.tsx` and renders one of them based on the current pathname via a manual `if/else` match (including a regex for the `/sources/:id` dynamic segment).
- `components/router.tsx` implements `RouterProvider`, `usePathname()`, `useRouter()` (push/replace), `useParams()` (hardcoded to the `/sources/:id` shape only), and a `Link` component that intercepts clicks and uses `history.pushState` for SPA-style navigation — a from-scratch router, not `react-router` or `next/navigation`.

### Pages (`frontend/app/`)
| Route | File | Purpose |
|---|---|---|
| `/` | `page.tsx` | Dashboard — metric cards (enabled sources, queued/running/completed/failed), discovery-engine health card, recent runs, "Run all" button |
| `/companies` | `companies/page.tsx` | CRUD for companies |
| `/sources` | `sources/page.tsx` | CRUD + run/baseline/delete actions for monitored sources |
| `/sources/:id` | `sources/[id]/page.tsx` | Source detail: metadata, discovery preview, recent runs, discovered URLs, summaries |
| `/storage` | `storage/page.tsx` | Read-only view of stored URLs, grouped by company → source, split by backend (JSON vs Postgres) |
| `/email` | `email/page.tsx` | SMTP status, manual/automatic mode toggle, recipient management, summary feed with manual "Send" |
| `/runs` | `runs/page.tsx` | Monitor run history with expandable per-run discovered-URL rows |
| `/settings` | `settings/page.tsx` | Displays configured API base URL |

### Data layer (`lib/api.ts`)
- Single Axios instance, `baseURL` from `VITE_API_BASE_URL` (defaults to `http://localhost:8000`).
- Request/response interceptors time every call and pipe the result into `recordHealthEvent()` — i.e. the frontend reports its own API-call telemetry back to the backend.
- All ~30 endpoint functions are fully typed (`Company`, `Source`, `MonitorRun`, `Summary`, `TaskStatus`, etc.) with a shared `getApiErrorMessage()` helper that unwraps FastAPI's `{detail: ...}` error shape.
- Mutating/heavy operations (`run-all`, source `run`, source `baseline`) return `{task_id, status: "queued"}` immediately; the frontend then polls `GET /tasks/:id` (React Query `refetchInterval`) via `TaskProgressDialog` until the Celery task reaches a terminal state.

### "Real-time" is actually polling + a telemetry beacon
There is no WebSocket or SSE channel. Two separate things:
1. **Task progress** — `TaskProgressDialog` polls `GET /tasks/{id}` every 2s.
2. **Health telemetry (outbound only)** — `lib/health-events.ts` posts `{event_type, action, metadata}` to `POST /health/events` using `navigator.sendBeacon` (falls back to `fetch(..., {keepalive:true})`), fired from the Axios interceptors (`frontend_api` events) and `route-logger.tsx` (`frontend_route` events on every SPA navigation). This is a one-way beacon into the shared JSONL health log, not a live push channel back to the browser.

### Deployment quirk
`frontend/Dockerfile` runs `npm run dev` (the Vite dev server bound to `0.0.0.0:3000`) as its container command — there is no `vite build` / static-serving stage. In this Compose setup, "production" frontend is actually the dev server, not an optimized static bundle.

### Color palette & shape (`app/globals.css`, `radius: 0.5rem`)
Light theme only — `darkMode: "class"` is wired up in Tailwind but no `.dark` CSS variables are defined, so toggling a dark class changes nothing visually.

| Token | HSL | Reads as |
|---|---|---|
| `background` | `210 33% 98%` | near-white, faint cool blue-gray page backdrop |
| `card` | `0 0% 100%` | pure white panels |
| `foreground` | `222 47% 11%` | near-black navy text |
| `primary` | `199 89% 32%` | saturated teal-blue (buttons, active nav, links) |
| `secondary` / `muted` | `210 24% 94%` | pale gray-blue (hover states, filled section headers) |
| `accent` | `158 46% 88%` | pale mint-green (unused in current pages, reserved) |
| `destructive` | `0 72% 51%` | clear red (delete buttons, error badges) |
| `border` | `214 21% 86%` | light gray-blue hairlines, 1px, on every card/table |

All cards/buttons/inputs share an 8px (`0.5rem`) corner radius. Every panel is a white `rounded-lg border shadow-sm` box — visually flat, no gradients, no imagery, icon-forward (lucide-react, ~16px inline / ~20px standalone).

### App shell (`components/app-shell.tsx`) — wraps every page
- **Desktop (≥1024px):** fixed 256px-wide white sidebar, full viewport height, right border. Top strip (64px): small teal rounded-square icon badge (Activity glyph) + "Website Monitor" bold + "Operations dashboard" gray caption below it. Below that, a vertical nav list of 7 items (Dashboard, Companies, Sources, Storage, Email, Runs, Settings), each a full-width row with icon + label; the active route gets a pale gray-blue pill background, inactive items are gray text that darkens on hover.
- **Mobile (<1024px):** sidebar is hidden; a hamburger button in the header opens the same sidebar as a 288px slide-over panel over a 30%-black scrim.
- **Header bar:** sticky, 64px tall, translucent/blurred white, spans the remaining width right of the sidebar. Left side: hamburger (mobile only) + page title (bold, derived from the current route) + a gray one-line subtitle ("Control monitor sources, baselines, and runs.").
- **Content well:** centered column, max width ~1280px, 16–24px side padding, vertical sections stacked with 24px gaps.

### Page-by-page visual layout
| Page | What's on screen, top to bottom |
|---|---|
| **Dashboard** `/` | Title + subtitle left, solid teal **"Run all"** button (▶ icon) right → row of **5 metric cards** (2-col mobile / 5-col desktop), each a small caption+icon header over a large bold number (Enabled Sources, Queued, Running, Completed Today, Failed Today) → **"Discovery health"** card with a 6-column strip of small stat blocks (colored status pill + model name for the OpenAI planner, a pill for browser tracing, big numbers for cached adapters / recent errors / scrape budget) → **"Recent runs"** card holding a 5-column table (ID/Source/Status pill/Started/Finished), capped at 10 rows. |
| **Companies** `/companies` | Title + subtitle → **"Create company"** card: one text input + teal "Create" button side-by-side → **"Company list"** card: table of editable name inputs, each row with an outline icon button that swaps pencil→save once edited, plus a red trash icon button. Empty state is a centered building-icon + heading + caption instead of an empty table. |
| **Sources** `/sources` | Title + subtitle, teal **"Add source"** button top-right → one **"Source list"** card: 7-column table (truncated URL with `#id` in gray underneath, Company, outline "strategy" badge, "N min" schedule, colored enabled/disabled pill, last-checked timestamp, and a 5-icon action cluster: eye/view, pencil/edit, play/run, rotate/baseline, red trash/delete). "Add/Edit" opens a modal dialog over a dimmed backdrop; Run/Baseline opens a polling progress modal. |
| **Source detail** `/sources/:id` | Ghost "← Back to sources" link → big URL as page title, company name as subtitle, 3 buttons top-right (teal Run, outline Baseline, red Delete) → 3-column row: **Metadata** card (label/value pairs: strategy badge, enabled pill, trace-JS yes/no, schedule, last checked) beside a wider **JS bundle sources** card listing each bundle URL as a monospace chip on gray → **"Discovery check"** card with a "Run check" button; results show an optional amber warning banner, a 4-box row of big numbers (Raw/Content/Already-Seen/New-Candidate URL counts), and a URL table with green "new" / gray "seen" badges → **Recent runs** table → bottom 2-column split: **Recent discovered URLs** (list of link rows in bordered boxes) and **Recent summaries** (cards with title, link, and summary paragraph). |
| **Storage** `/storage` | Title + subtitle → optional amber "data reconciliation" banner → 3 stat cards (Companies/Sources/Stored-URL totals) → one card per company, each containing a light gray-blue header bar (company name + source count badge) and, nested inside, one block per source: a header strip (source id link, strategy badge, URL-count badge, source URL, "JSON: n / DB: n" counts) over a table of stored URLs with green "json" vs gray "db" origin badges and an external-link button per row. |
| **Email** `/email` | Title + subtitle → 4 stat cards (SMTP status pill, Companies, Enabled Recipients, Ready Summaries) → **"Email notification mode"** card: description text left, two toggle buttons (Manual/Automatic) right, active one filled teal → **"SMTP app password setup"** card: 3-column Host/Sender/Port+TLS values, amber banner listing missing env vars if unconfigured → **"Company recipients"** card: one bordered block per company (header bar with inline "add recipient" input+button) over a recipient table with editable email cells, an enable/disable Switch + colored badge, and edit/save/delete icon buttons → **"LLM email summaries"** card with a company filter dropdown in its header, body is a stack of bordered summary cards each showing status/company/model badges, a title, a "To: …" line, a teal Send button, the full summary text in a shaded panel, and a 3-column metadata footer (created date / source link / sent-or-recipient-count), with an optional amber error banner. |
| **Runs** `/runs` | Title + subtitle → **"Run history"** card: table with a chevron-expand column, ID, source URL, status pill, started/finished timestamps, error text; clicking the chevron expands an inline shaded sub-row showing a 3-column info strip (Run ID/Source ID/discovered-URL count) plus a list of clickable discovered-URL rows. |
| **Settings** `/settings` | Title + subtitle → single **"API"** card with a server-icon title and one read-only input showing the configured API base URL. |

### Recurring UI motifs
- **`StatusBadge`** — a consistent color-coded pill used everywhere a status appears: green (success/completed/idle/configured/available), red (failed/error/unavailable/missing key), amber (running/pending/queued/locked), gray (anything else).
- **Buttons** — solid teal = primary action, white-with-gray-border = secondary/outline, solid red = destructive (always behind a native `confirm()` dialog for deletes).
- **`EmptyState`** — centered icon + bold title + gray caption, swapped in for any card whose table/list would otherwise render empty.
- **Toasts** (Sonner) fire on every mutation success/error across all pages.
- **Modals** (Radix `Dialog`) are used only for the source create/edit form and the task-progress poller; every other interaction happens inline on the page.

---

## 4. Backend — Detailed Behavior

### `backend/app/main.py`
- FastAPI app with a `lifespan` handler that logs startup/shutdown to the health log.
- CORS restricted to `http://localhost:3000` (the Vite dev server) only.
- A custom HTTP middleware times every request and logs it (`backend_request` events: method, path, status, duration).
- Registers 8 routers, no auth layer — the API is open, assumed to run on a trusted local network.

### Routers → responsibility
| Router | Prefix | Key endpoints |
|---|---|---|
| `health` | `/health` | `GET /health`, `GET /health/discovery` (engine health), `POST /health/events` (frontend telemetry ingestion) |
| `companies` | `/companies` | CRUD, 409 on duplicate name |
| `sources` | `/sources` | CRUD; `/runs`, `/discovered-urls`, `/summaries`, `/discovery-preview` (dry-run, no DB writes); `POST /baseline`, `POST /run` (enqueue Celery tasks) |
| `runs` | `/runs` | List runs / run detail with discovered URLs |
| `storage` | `/storage` | Merges the legacy JSON file store with the `discovered_urls` table into one view |
| `monitor` | `/monitor` | `POST /run-all` (enqueue all enabled sources), `GET /status` (dashboard counts) |
| `tasks` | `/tasks` | `GET /{task_id}` — wraps Celery `AsyncResult` for polling |
| `email` | `/email` | SMTP status, notification-mode settings, recipients CRUD, summaries list, manual send |

### Orchestration core — `backend/app/services/monitor_service.py`
This is where routers and Celery tasks actually converge:
- `run_baseline(source_id)` — seeds the JSON `seen_url_records.json` store via strategy-specific baseline functions, then mirrors those URLs into the `discovered_urls` table.
- `run_monitor(source_id)` — the polling loop for one source: if no baseline exists yet, does a baseline instead of full processing (prevents an email blast on first run); otherwise discovers new URLs (`mysignal.workflows.*`), and per new URL: records a `DiscoveredUrl`, scrapes + summarizes via `mysignal.workflows.new_url_processor`, persists a `Summary`, and — only if the global email mode is `automatic` — sends the notification.
- `run_all_enabled_sources()` — sequential loop calling `run_monitor` for every enabled source (backs `POST /monitor/run-all`).
- Recipient lookup falls back from the DB `NotificationRecipient` table to a legacy JSON file — evidence the app is mid-migration from a JSON-file CLI tool to a Postgres-backed system (see §5).

### Background jobs (`backend/app/workers/`)
- **`celery_app.py`** — `Celery("website_monitor", broker=REDIS_URL, backend=REDIS_URL)`; wires worker/beat/task signals into the same JSONL health logger; configures Celery Beat to fire `monitor.scheduler_tick` every **60 seconds**.
- **`monitor_worker.py`** — thin Celery task wrappers: `ping_worker`, `baseline_source_task`, `monitor_source_task`, `run_all_enabled_sources_task`, all delegating into `monitor_service`.
- **`scheduler.py`** — `scheduler_tick`: for every `Source`, checks `enabled`, whether it's due (`last_checked_at + schedule_minutes <= now`), and whether it's already running; if due, enqueues `monitor_source_task.delay(source.id)`. This single dynamic tick replaces having one Beat entry per source.

**Trigger paths, summarized:** every crawl/summarize operation is either a manual API call (`POST /sources/{id}/run|baseline`, `POST /monitor/run-all`) or the automatic 60-second scheduler tick — nothing runs synchronously inside a request except manual email sends (`POST /email/summaries/{id}/send`).

### Configuration
`backend/app/config.py` is a minimal frozen dataclass holding only `database_url` and `redis_url` (loaded via `python-dotenv`). Everything else — `OPENAI_API_KEY`, `FIRECRAWL_API_KEY`, SMTP settings, and a family of `DISCOVERY_*` tuning knobs (browser tracing on/off, LLM planner on/off, endpoint caps, heavy-discovery lock TTL) — is read ad hoc via `os.getenv()` deep inside `mysignal` and router code, not centralized.

### Observability (`observability.py`)
A single-purpose structured logger: `log_health_event(event_type, service, action, status, duration_ms, metadata)` appends one JSON line to `logs/app-health.jsonl`, thread-safe, with size-based rotation. It's the unified event log across HTTP requests, Celery task lifecycle, discovery engine events, and email sends — and it's what `GET /health/discovery` reads back to build the dashboard's health card. No Prometheus/Grafana/OpenTelemetry.

---

## 5. The `mysignal` Engine (Crawling / Discovery / Summarization)

`mysignal` is a Python library imported **in-process** by the FastAPI app and Celery workers — there's no HTTP/RPC boundary between them. It also has standalone CLI entry points (`mysignal/main.py`, `mysignal/monitor.py`) left over from before the FastAPI rewrite; those are **not** used by the running system but still share the same JSON data files.

| Subpackage | Purpose |
|---|---|
| `discovery/page_links.py` | HTML link extraction (Crawl4AI, falling back to requests+BeautifulSoup); classifies link DOM region (nav/sidebar/footer/main) |
| `discovery/api_discovery.py` (~2350 lines) | Deterministic JS/API endpoint discovery: framework fingerprinting (Next.js, Nuxt, WordPress, etc.), inline state extraction (`__NEXT_DATA__`, `__APOLLO_STATE__`), JS bundle scanning for `fetch`/`axios`/GraphQL calls, endpoint validation + scoring |
| `discovery/advanced_discovery.py` (938 lines, newest module) | Heavy discovery: Playwright browser network tracing + an OpenAI-assisted endpoint planner, cached per-domain to `discovery_adapters.json`, gated by a file lock to prevent concurrent heavy runs; also exposes `discovery_health_summary()` |
| `discovery/categorizer.py`, `filters.py`, `site_graph.py` | Keyword-based URL classification, used by the legacy CLI path |
| `crawler/crawl4ai_collector.py` | BFS site crawler (Crawl4AI `AsyncWebCrawler`) for the CLI hub-discovery flow |
| `collector/firecrawl_collector.py` | `FirecrawlApp.scrape_url(..., formats=["markdown"])` — the actual content scraper used for summarization |
| `filters/content_filter.py` | Blocks non-article extensions (`.png`, `.css`, `.js`, `.pdf`, `.json`, etc.) |
| `monitoring/inventory_store.py` | JSON file persistence: `seen_url_records.json` (the append-only "seen URL" ledger), `tracked_recursive_roots.json`, `inventory.json`, `discovery_adapters.json` |
| `workflows/parent_monitor.py`, `feed_monitor.py`, `api_monitor.py` | Per-strategy discovery + diff-against-seen logic |
| `workflows/new_url_processor.py` | Per-URL pipeline: scrape → summarize → (maybe) email → persist |
| `processors/article_processor.py` | Firecrawl scrape → `Article` model |
| `summarizers/openai_summarizer.py` | OpenAI Chat Completions, model `gpt-5.4`, fixed "technology news editor" system prompt producing a `HEADLINE:/UPDATE:/KEY DETAILS:/FOLLOW UP:` format |
| `notifications/smtp_email.py` | Builds/sends the notification email via `smtplib` |

**Known dual-source-of-truth:** URL de-duplication is tracked in *both* the Postgres `discovered_urls`/`seen_urls` tables *and* the JSON file `mysignal/data/seen_url_records.json`. The production write path (`monitor_service.py`, `new_url_processor.py`) still writes to the JSON file; `routers/storage.py` reconciles both sources for the `/storage` dashboard view. This is a migration-in-progress artifact, not a bug — but it's worth knowing if URLs ever appear "seen" in one place and not the other.

---

## 6. Database

- **Engine:** PostgreSQL 16, SQLAlchemy 2.0 declarative models, Alembic migrations (3 revisions so far: initial schema → `sources.last_checked_at` → email delivery fields + `app_settings`).
- **Tables:** `companies` (1:N `sources`, `notification_recipients`) · `sources` (url, strategy, trace_js, js_bundle_sources, enabled, schedule_minutes, last_checked_at) · `seen_urls` (DB analog of the JSON ledger, largely superseded by the JSON file in the live write path) · `monitor_runs` (status, started/finished_at, error) · `discovered_urls` (payload JSON, FK to run) · `summaries` (title, summary, model, email_status/sent_at/error) · `notification_recipients` · `app_settings` (currently just `email_notification_mode`).
- **Redis:** not a data store per se — used purely as the Celery broker + result backend.

---

## 7. Docker Compose Topology

| Service | Image / Build | Port | Role |
|---|---|---|---|
| `frontend` | `frontend/Dockerfile` | 3000 | Vite dev server (see §3 deployment note) |
| `backend` | `backend/Dockerfile` | 8000 | FastAPI (`uvicorn`), runs `alembic upgrade head` on boot |
| `celery-worker` | same Dockerfile | — | Executes crawl/baseline/summarize tasks (concurrency 2, `-Ofair`) |
| `celery-beat` | same Dockerfile | — | Fires `scheduler_tick` every 60s |
| `postgres` | `postgres:16` | 5432 | Primary datastore |
| `redis` | `redis:7` | 6379 | Celery broker/result backend |

`backend`, `celery-worker`, and `celery-beat` all bind-mount `./logs` and `./mysignal/data`, so the health log and legacy JSON state are shared and persisted across containers. `backend/Dockerfile` additionally installs Playwright **and** Patchright (a stealth Playwright fork) with Chromium — used for the "heavy" browser-based discovery path.

---

## 8. End-to-End Flow (one monitoring cycle)

1. User creates a `Company` and a `Source` (URL + strategy) from the dashboard.
2. `POST /sources/{id}/baseline` → Celery `baseline_source_task` seeds `seen_url_records.json` + mirrors to `discovered_urls` (no summaries yet, so the first run doesn't email a backlog).
3. Celery Beat's `scheduler_tick` runs every 60s, finds sources due for a check (`schedule_minutes` elapsed), and enqueues `monitor_source_task`.
4. The strategy workflow (`parent_monitor` / `feed_monitor` / `api_monitor`) discovers candidate URLs, filters them (`content_filter.py`), and diffs against the seen-URL stores.
5. Each new URL: Firecrawl scrapes content → `openai_summarizer.py` produces a structured summary → a `Summary` row is persisted.
6. If the global email mode is `automatic`, `smtp_email.py` sends it immediately; if `manual`, it waits in the `/email` dashboard view for a human click.
7. Every step along the way — HTTP requests, Celery task lifecycle, discovery events, email sends, frontend route views and API calls — is appended to `logs/app-health.jsonl`, which backs the `/health/discovery` dashboard card.

---

## 9. Notable Rough Edges (worth knowing before making changes)

- **`app/` naming is misleading** — it looks like Next.js but is a plain Vite SPA with a hand-rolled router; don't assume Next.js conventions (server components, file-based route generation, middleware) apply.
- **`"use client"` directives are dead comments** — no RSC boundary exists in a Vite build; they're a scaffolding leftover.
- **Frontend Docker image runs the dev server**, not a production build — fine for a local ops console, but not what you'd want behind a public load balancer.
- **Dual seen-URL storage** (Postgres + JSON file) — `routers/storage.py` is the only place both are reconciled; new code that dedups URLs should check both if it needs authoritative "have we seen this" answers.
- **No auth** on the API — CORS is locked to `localhost:3000`, but there's no token/session layer, consistent with this being a local/internal tool.
- **Config is split** between `backend/app/config.py` (DB/Redis only) and scattered `os.getenv()` calls throughout `mysignal` — there's no single source of truth for all environment configuration.
