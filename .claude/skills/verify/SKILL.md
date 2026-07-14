---
name: verify
description: Build, launch, and drive the Sentinel Actalyst app locally to verify frontend/backend changes end-to-end.
---

# Verifying Sentinel Actalyst locally

## Build / typecheck

```bash
cd frontend && npm run build   # runs tsc --noEmit + vite build
```

## Launch (no Docker, no AWS needed)

Backend — must run from the **repo root** (imports are `backend.app.*`), with
in-memory storage so S3/AWS credentials are not required. Env vars set on the
command line win over `.env` (`load_dotenv()` does not override):

```bash
STORAGE_BACKEND=memory ENVIRONMENT=dev TASK_EXECUTION_BACKEND=local \
AUTH_SECRET=<any-string> AUTH_COOKIE_SECURE=false \
ADMIN_NAME=<admin> ADMIN_PASSWORD=<pass> \
USER_1_NAME=demo USER_1_PASSWORD=<pass> \
python -m uvicorn backend.app.main:app --port 8000 --host 127.0.0.1
```

Frontend dev server (defaults `VITE_API_BASE_URL=http://localhost:8000`,
CORS default already allows localhost:3000):

```bash
cd frontend && npm run dev   # port 3000
```

## Drive

- Login at `/login`: fields labeled **Name** / **Password**, submit button says
  **Continue** (not "Sign in"). `USER_N_NAME/PASSWORD` env vars seed customer
  accounts; `ADMIN_NAME/PASSWORD` seeds the admin (login at `/admin/login`).
- Playwright works headless with the cached Chromium (`npm i playwright` in a
  scratch dir; browsers already in `%LOCALAPPDATA%/ms-playwright`).
- Customer surface is two pages: `/dashboard` (Home: briefing + feed + pulse
  rail) and `/monitors` (Watchtower: monitors / alerts / workspace tabs).
  Legacy routes deep-link: `/insights`, `/trends` → Home; `/notifications`,
  `/settings`, `/onboarding`, `/monitors/[id]` → Watchtower.

## Monitoring pipeline test

A controllable end-to-end test: serve a static "newsroom" page with article
links (`python -m http.server 8765`), create a company+source on it via the
API, baseline it, add a link to the index, then `POST /sources/{id}/run` —
the run result should show exactly the added URL in `new_urls`. Analysis
model is picked by `ANALYSIS_PROVIDER` (`auto` | `gemini` | `openai`);
blank out `FIRECRAWL_API_KEY= fire_crawler_api=` on the command line so
acquisition uses `requests` (Firecrawl is a cloud service and cannot reach
localhost). Analyzer fallback events land in `logs/app-health.jsonl`
(`"action": "fallback"`), not stdout.

## Gotchas

- Adding a monitor queues a real baseline scrape (local task backend); with
  `https://example.com` it completes harmlessly.
- Browser console shows benign errors: a 401 from the pre-login session probe
  and 404s from `google.com/s2/favicons` for domains with no favicon (the UI
  falls back to initials).
- The Bash tool's working directory persists between calls — `cd frontend`
  fails if you're already inside it; prefer absolute paths.
