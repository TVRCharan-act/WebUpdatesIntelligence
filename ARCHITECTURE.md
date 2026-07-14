# web-changes — Architecture & Tech Stack

## What this project is

`web-changes` is a **backend-only Python automation pipeline** — not a client/server web application. There is no browser UI, no REST API consumed by a frontend, and no database. It runs on a daily schedule (GitHub Actions cron), crawls a list of brand websites, detects new pages, uses an LLM to decide what's newsworthy, and emails a "daily brief" newsletter to a fixed recipient list.

Because of that, this doc is organized around **pipeline stages** rather than a traditional frontend/backend split. The closest thing to a "frontend" is the HTML email that gets rendered and sent — everything else is data-processing/backend code.

Repo: `github.com/actalyst/web-changes` (this is its own git repository, nested inside `web-changes/`; it is unrelated to the outer git repo rooted at the Windows user profile directory — see note at the bottom).

## Tech stack summary

| Layer | Technology |
|---|---|
| Language / runtime | Python 3.12 |
| HTTP client (async) | `aiohttp` |
| HTML parsing | `BeautifulSoup4` |
| Web scraping API | ZenRows (`api.zenrows.com`) — JS-rendered page fetch |
| LLM | Google Gemini via `google-genai` SDK (model: `gemini-3-flash-preview`) |
| Data validation | `pydantic` (schemas for crawler output, brand config, LLM responses) |
| Email rendering | `Jinja2` templates + hand-built Python HTML string templates |
| Email delivery | AWS SES via `boto3` |
| Storage | AWS S3 (`act-web-changes` bucket) in prod; local JSON files in dev |
| Config | `config.yaml` (single central file) + `python-dotenv` for secrets |
| Retry/backoff | `backoff` library (scraper), custom retry loop (crawler) |
| Fuzzy matching | `python-Levenshtein` (URL/title similarity in comparison stage) |
| Scheduling | GitHub Actions (`cron`), not a long-running server |
| `fastapi` dependency | Used only for its `HTTPException` class as a convenient typed-error object inside `gemini_service.py` — there is no FastAPI app/server anywhere in this repo |

`requirements.txt`:
```
git+ssh://git@github.com/actalyst/atoms.git@v0.1.13#egg=nucleus
aiohttp, python-Levenshtein, pyyaml, python-dotenv, requests,
beautifulsoup4, jinja2, boto3, firecrawl-py, fastapi, backoff,
google-genai, pytz
```

## Pipeline flow

Driven by [`run.sh`](run.sh), which runs these stages in sequence:

```
1. src/crawlers/zenrows_crawler.py   → crawl brand sites, extract all links
2. src/utils/comparison.py          → diff vs previous crawl → new_urls.json
3. src/utils/orchestrator.py        → LLM-process new URLs → newsletter content
       (orchestrator.py also triggers step 4 internally, at the end of main())
4. src/utils/email_ses.py / new_ses.py → render + send the newsletter via SES
```

### 1. Crawler — `src/crawlers/zenrows_crawler.py`
- `AsyncZenrowsCrawler` reads `data/input/brands.json` (brand name, base URL, seed URLs, per-brand flags like `include_external_urls`, `extract_external_pdf_urls`).
- For each seed URL, calls the ZenRows API (`js_render`, `wait_ms` configurable) to get rendered HTML, retrying on failure.
- Parses HTML with BeautifulSoup, strips nav/header/footer/pagination elements (`remove_navigation_elements`), then extracts and classifies every `<a href>` (news/document/image/pdf/etc., internal vs external, allowed-domain check).
- Validates records with pydantic models from `crawler_constants.py` (`ExtractedUrl`, `RunData`, `BrandInfo`, `AllRunsSchema`).
- Writes results to `sorted_results.json` and keeps a rolling history (`crawler_all_runs_history.json`, capped at 7 cycles) — both go to S3 in prod, local `data/output/` in dev.
- Runs brands concurrently (`asyncio.Semaphore`, configurable concurrency), retries each seed URL up to `max_crawl_retries` times and keeps the best-scoring run.

### 2. Comparison — `src/utils/comparison.py`
- Loads current `sorted_results.json` and prior history, normalizes URLs (case, trailing slash, subdomain) per `config.yaml` rules.
- Uses `Levenshtein.ratio` for fuzzy matching to catch near-duplicate URLs across runs.
- Produces `new_urls.json` (added) and `removed_urls.json` (gone) per brand, respecting a configurable `default_history_count` / per-brand history override.

### 3. Orchestrator — `src/utils/orchestrator.py` (`MainOrchestrator`)
This is the core decision-making stage. For every new URL it:
- Filters out unsupported types up front (`archive`, `.zip`, `.xbrl.zip`, etc.) — these are recorded as `skipped`, never sent to the scraper (see [`docs/url-processing-failure-handling.md`](docs/url-processing-failure-handling.md) for the incident that drove this design).
- Routes PDFs to `PDFSummaryModule` (Gemini's native `url_context` / file-understanding, via `google.genai.types`), and HTML pages to `ZenRowsScraper` (`src/services/zenrows_llm_scraper.py`, `aiohttp` + `backoff`-based retries) to get scraped markdown.
- Runs an LLM relevance check (`GeminiLLMService.check_url_relevance`) — content below `relevance_threshold` (default 0.6) is skipped.
- Extracts structured news data (`GeminiLLMService.extract_news_data`) — title, summary, category, published date — using prompt templates from `config/prompts.yml`.
- Applies date filtering (today/yesterday IST by default, or `custom_dates`), with an **early-stopping** optimization that can bail out of a brand once URLs stop matching the target date window.
- Runs an LLM-based **content deduplication** pass (`find_duplicate_news_items`) across all "sendable" candidates, e.g. catching the same press release published as both HTML and PDF, keeping one canonical item.
- Every outcome (`success` / `skipped` / `item_failed`) is written to two audit trails: a full `newsletter_url_audit.json` and an internal-only `url_processing_archive.json` — the hard invariant is that only `status == success AND newsletter_included == true` items ever reach the email.
- At the end of `main()`, it directly calls `send_daily_brief_email()` (success) or `send_daily_brief_failure_email()` (fatal exception → alerts `support@actalyst.ai`).

### 4. Email — `src/utils/new_ses.py` (current) and `src/utils/email_ses.py` (older path)
- Renders the newsletter as an inline-styled HTML email (`new_email_template.py` / `email_template.html`, brand color-coded cards, category badges) and sends via `boto3` SES `send_raw_email`/`send_email`.
- `EmailSubjectGenerator` (`email_sub_gen.py`) optionally calls Gemini to write a dynamic subject line (5–7 words, theme/category-based fallback if LLM fails).
- Recipient/from/support addresses, region, and subject-generation behavior are all config-driven (`config.yaml` → `email:` block).

### Supporting modules
- `src/utils/s3_helpers.py` — thin `boto3` S3 wrapper (`s3_load_json`, `s3_save_json`, `s3_upload_file`, `s3_delete_object`); every stage uses this for prod storage instead of talking to `boto3` directly.
- `src/utils/logger.py` — `LoggingService`: rotating file handlers (size-based, `RotatingFileHandler`) per component, console + file + dedicated error-file levels, all configured from `config.yaml`.
- `src/utils/prompt_loader.py` — loads YAML/JSON prompt templates from `config/json_prompts/` / `config/prompts/`, used by the Gemini clients.
- `src/utils/clear_s3_files.py` — standalone maintenance script to wipe S3 output objects (not part of the scheduled pipeline).
- `scripts/run_targeted_dedupe_newsletter_test.py` — manual test harness for the content-dedup logic.

## Configuration & environments

- **`config.yaml`** is the single source of truth: logging setup per component, S3 vs local paths (`environment: dev|prod`), crawler tuning (concurrency, timeouts, allowed domains), comparison thresholds, email settings, Gemini model name, and orchestrator constants (concurrency, date filters, relevance/dedup thresholds).
- **Secrets** come from environment variables (`.env`, loaded by `run.sh`, or GitHub Actions `secrets.*`): `ZENROWS_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_GEMINI_MODEL`, plus AWS credentials or an assumed `AWS_PROFILE`/OIDC role.
- **Environment switch**: `environment: prod` in `config.yaml` (overridable via `ENVIRONMENT` env var) routes all reads/writes to S3 (`s3://act-web-changes/web_changes/...`); anything else uses local `data/input` / `data/output` / `logs`.

## Deployment / scheduling

There is no Docker/server deployment for this component — it runs as a scheduled CI job:
- `.github/workflows/schedule-run.yaml` — "Site Monitor Pipeline", daily cron at 7:00 AM IST (`main` branch), assumes an AWS role via OIDC, installs `requirements.txt`, runs `./run.sh`, uploads `logs/` and `data/output/` as build artifacts.
- `.github/workflows/ai_news_schedule-run.yaml` — same shape, manual-dispatch only (cron commented out), runs against the `projectB` branch ref.
- Locally, `run.sh` validates required env vars, checks Python 3 is active, runs each pipeline script in order, and consolidates all component logs into one timestamped file per run.

## Tests

`tests/` (pytest-style, ~825 lines total) covers: empty-state daily brief behavior, live newsletter flow integration, orchestrator date-inference logic, and resending a selected newsletter — reflecting the failure-handling and dedup logic described in `docs/url-processing-failure-handling.md`.

## Note on the outer git repository

While documenting this, I noticed the top-level `.git` repository on this machine is rooted at the entire Windows user profile directory (`C:\Users\tvrch`), not at a project folder — it's tracking things like `AppData`-adjacent paths alongside unrelated project folders (`dashboard-server`, `db`, `common`, etc.). This `web-changes` folder is its own separate, properly-scoped git repository, so it isn't affected. Worth checking whether that outer repo was intentional, since committing from the wrong directory there could stage far more than intended.
