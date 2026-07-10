# PulseActalyst — As-Built Product Documentation

> This used to be a forward-looking proposal. Most of it has since been built. This revision documents what's **actually running** — real routes, real components, real backend code, read directly from the codebase — and calls out, explicitly, what's still a stub or hasn't been touched. If you read only §4, you should be able to picture every screen without opening the app.

---

## 0. Status at a Glance

| Area | Status |
|---|---|
| Backend auth (`.env`-configured accounts, cookie session, `CurrentUser`/`AdminUser`) | **Built** |
| `owner_name` data scoping on every customer-facing router | **Built** — companies, sources, insights, runs, email, storage all filter by it |
| `companies.owner_name`, `summaries.severity`, `summaries.reviewed_at` columns | **Built** (migration `20260709_0004`) |
| Customer app: onboarding, Command Center, Monitors, Monitor detail, Insights, Trends, Notifications, Settings | **Built** |
| Admin app: `/admin/accounts` overview page | **Built** |
| Admin app: everything else (Companies/Sources/Storage/Email/Runs/Settings) | **Unchanged** from the original ops console — see [fullstack_design.md §3](fullstack_design.md) |
| Real analytics (`GET /insights/stats`) — daily counts, per-company, busiest sources, avg time-to-insight | **Built** — backs Dashboard, Trends, and Monitors sparklines (§4.6–§4.10) |
| Check frequency selectable at creation (onboarding + Add monitor) | **Built** — Hourly / Every 6 hours / Daily, real `schedule_minutes` values |
| "Check now" loading state | **Built** — `frontend/lib/use-source-check.ts` polls the Celery task and shows a spinner until it's terminal |
| Separate frontend builds / subdomains for customer vs. admin | **Not built** — one Vite SPA, gated client-side by route + role (§1) |
| Marketing site | **Not built** — no public pages exist |
| Real digest cadence (Daily/Weekly distinct from Instant) | **Not built** — all three currently write the same `automatic` value |
| Strategy auto-detection (feed/API vs. parent page) | **Not built** — every customer-created source is hardcoded `strategy: "parent"` |
| Team invites | **Not built** — Settings shows a read-only team list only |
| Billing | **Not built** — static "Pilot" badge, no plans/usage/Stripe |
| Theme toggle (dark mode) | **Half-built** — real `.dark` CSS tokens exist, but nothing in the app switches to that class yet |
| Admin sidebar rebrand | **Not done** — still literally reads "Website Monitor" / "Operations dashboard" |

---

## 1. Architecture — What's Actually Running

```
                    FastAPI Backend (unchanged stack: Postgres/SQLAlchemy/Celery/Redis)
                    + backend/app/auth.py (env-configured accounts, signed cookie)
                    + _owner_filter(user) applied in every customer-facing router
                               │
                               │  single origin, CORS locked to http://localhost:3000
                               │
                    ┌──────────▼───────────┐
                    │   One Vite SPA        │
                    │   frontend/           │
                    │   (not two builds)    │
                    └──────────┬────────────┘
                               │
              client-side role gate in frontend/src/main.tsx
                               │
                ┌──────────────┴───────────────┐
                │                               │
        pathname starts with "/admin"   everything else
                │                               │
        <AppShell> (original ops UI)   <CustomerShell> (new)
```

This is a real deviation from the original proposal (§1 of the prior version proposed separate subdomains and separate build targets). What actually shipped is simpler: **one SPA**, and `frontend/src/main.tsx`'s `Routes()` component does all the gating:

```tsx
if (pathname === "/login") return <LoginPage />;
if (pathname === "/admin/login") return <LoginPage admin />;
// ...
if (!auth.session) { window.location.replace(pathname.startsWith("/admin") ? "/admin/login" : "/login"); return null; }
if (pathname.startsWith("/admin") && auth.session.role !== "admin") { window.location.replace("/dashboard"); return null; }
if (pathname === "/") { window.location.replace(auth.session.role === "admin" ? "/admin/dashboard" : "/dashboard"); return null; }
```

**Important nuance:** this client-side redirect is a UX convenience, not the security boundary. The actual boundary is server-side — every router requires the `CurrentUser` (or `AdminUser`) FastAPI dependency, and every customer-facing query is filtered by `owner_name`. If someone hit an admin-only API endpoint directly with a customer's cookie, the backend would 403 regardless of what the frontend router does. That part is solid; just don't mistake the `/admin` path prefix for a real trust boundary by itself.

Because it's one SPA, both experiences also share one `frontend/app/globals.css` and one Tailwind config — a color or radius change to that file affects both the customer app and the admin console. There is no independent design system per surface.

---

## 2. Authentication — As Implemented

`backend/app/auth.py`, unchanged in spirit from the original design, fully built:

- **Accounts** are loaded once at process start from environment variables: `ADMIN_NAME`/`ADMIN_PASSWORD` (exactly one admin), and any number of `USER_<n>_NAME`/`USER_<n>_PASSWORD` pairs (role `customer`). No user database, no signup.
- **Session cookie**: `pulseactalyst_session`, `httponly`, `samesite=lax`, 7-day max age. It's a hand-rolled `base64(payload).hmac_sha256(payload)` token (not a JWT library — plain stdlib `hmac`/`hashlib`/`base64`/`json`), signed with `AUTH_SECRET` (falls back to a value derived from `DATABASE_URL` if unset — fine for local dev, **set `AUTH_SECRET` explicitly anywhere shared**).
- **Endpoints** (`backend/app/routers/auth.py`): `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`.
- **Dependencies**: `CurrentUser` (any valid session, 401 otherwise) and `AdminUser` (`CurrentUser` + `role == "admin"`, 403 otherwise) are imported into every router that needs them.
- **Scoping pattern**, copy-pasted verbatim into `companies.py`, `sources.py`, `insights.py`, `runs.py`, `email.py`, and `storage.py`:
  ```python
  def _owner_filter(user: CurrentUser) -> str | None:
      return None if user.role == "admin" else user.name
  ```
  Every list/get/create/update/delete in those six routers passes the result into the matching `crud.py` function, which adds a `WHERE companies.owner_name = :owner_name` (or a join to get there) whenever it isn't `None`. Admins get `None` → no filter → see every account's data.
- **`/monitor/run-all` is `AdminUser`-only** — a customer cannot trigger a global run-all across every source in the system. `/monitor/status` is `CurrentUser` (any role), but nothing in the customer app currently calls it — the customer Dashboard computes its own metrics from the already-owner-scoped `/companies`, `/sources`, and `/insights` responses instead.
- **`/admin/accounts`** (`backend/app/routers/admin.py`) — `AdminUser`-only. Reads the configured customer accounts from `auth.configured_accounts()` and joins them against `crud.account_usage_by_owner()` (a single grouped query counting companies/sources per `owner_name`) to return name, company count, monitor count, and last login time for each.
- **`/insights/stats?days=N`** (`backend/app/routers/insights.py` → `crud.get_insight_stats`) — `CurrentUser`, same `_owner_filter` scoping as everything else. One query joins `Summary → DiscoveredUrl → Source → Company` for every summary created in the last `N` days, then aggregates in Python (not SQL `GROUP BY date_trunc`, deliberately — the dataset size doesn't need it, and it keeps the aggregation portable) into: a zero-filled daily count series, insight counts per company, the top 5 busiest sources, a per-source daily count matrix (for card sparklines), and the average seconds between `DiscoveredUrl.discovered_at` and `Summary.created_at` across the window. This single endpoint backs every chart in the customer app — nothing else computes analytics.

---

## 3. Data Model Changes

Migration `20260709_0004_add_account_scoping_and_insight_review.py`, applied via the existing `alembic upgrade head` boot step — no new tables:

| Column | Table | Purpose |
|---|---|---|
| `owner_name` (nullable, indexed) | `companies` | Which configured account owns this company (and everything under it) |
| `severity` (default `"medium"`) | `summaries` | `low` / `medium` / `high` — drives the severity badges and "needs attention" filtering everywhere in the customer app |
| `reviewed_at` (nullable) | `summaries` | Set the moment a customer clicks "Mark reviewed"; `null` = still needs attention |

---

## 4. Frontend — Page by Page, in Enough Detail to Picture It

### 4.1 Actual Route Table

| Route | Component | Notes |
|---|---|---|
| `/login` | `LoginPage` | Customer login |
| `/admin/login` | `LoginPage admin` | Same component, `admin` prop changes copy + post-login role check |
| `/` | — | Redirects to `/dashboard` or `/admin/dashboard` based on role |
| `/dashboard` | `CustomerDashboardPage` | Command Center |
| `/onboarding` | `OnboardingPage` | |
| `/monitors` | `MonitorsPage` | |
| `/monitors/:id` | `MonitorDetailPage` | |
| `/insights` | `InsightsPage` | |
| `/trends` | `TrendsPage` | |
| `/notifications` | `NotificationsPage` | |
| `/settings` (and anything under `/settings/*`) | `WorkspaceSettingsPage` | One page handles Workspace/Team/Billing/Account — there is no separate `/settings/team` or `/settings/billing` route yet, despite the nav linking to `/settings/workspace` |
| `/admin/dashboard` | `DashboardPage` (`frontend/app/page.tsx`, the **original** ops dashboard) | Reused as-is |
| `/admin/accounts` | `AdminAccountsPage` | New |
| `/admin/companies` | `CompaniesPage` | Unchanged |
| `/admin/sources`, `/admin/sources/:id` | `SourcesPage`, `SourceDetailsPage` | Unchanged |
| `/admin/storage` | `StoragePage` | Unchanged |
| `/admin/email` | `EmailPage` | Unchanged |
| `/admin/runs` | `RunsPage` | Unchanged |
| `/admin/settings` | `SettingsPage` | Unchanged |

For everything marked "Unchanged," the exact visual layout is already documented in [fullstack_design.md §3](fullstack_design.md) — not repeated here.

### 4.2 Color System (shared by both surfaces)

`frontend/app/globals.css` — light tokens deepened slightly from the original single-surface app, and a **real** `.dark` block now exists (it didn't before):

| Token | Light | Dark |
|---|---|---|
| `background` | `210 33% 98%` (pale blue-gray) | `222 47% 8%` (near-black navy) |
| `card` | `0 0% 100%` (white) | `222 40% 11%` |
| `primary` | `199 89% 32%` (teal-blue) | `199 89% 38%` (slightly brighter, for dark-ground contrast) |
| `accent` | `158 46% 88%` (pale mint) | `174 38% 18%` (deep teal-green) |
| `destructive` | `0 72% 51%` | `0 72% 55%` |
| `radius` | `0.7rem` (up from `0.5rem`) | same |

`body` also now sets `font-feature-settings: "tnum" 1` globally, and several new numeric displays (KPI tiles, tabular data) additionally use Tailwind's `tabular-nums` utility explicitly.

**The dark tokens are dormant.** No component in the app currently toggles a `.dark` class on `<html>` or `<body>` — there's no theme switcher UI. The CSS is ready; nothing invokes it yet.

### 4.3 Customer Shell (`components/customer-shell.tsx`) — wraps every `/dashboard`, `/monitors`, `/insights`, `/trends`, `/notifications`, `/settings*` page

This is a from-scratch component, visually distinct from the admin `AppShell`:

- **Sidebar** (256px, desktop-fixed / slide-over on mobile): solid **dark navy** background (`bg-[hsl(222_47%_9%)]`), white text — a deliberate contrast with the admin console's all-white shell. Top strip: teal rounded-square icon badge (Activity glyph) + "PulseActalyst" bold + "AI intelligence" in translucent white (`text-white/55`).
- **Nav** (6 items, icon + label): Command Center (`/dashboard`), Monitors, Insights, Trends, Notifications, Settings (`/settings/workspace`). Active item gets a `bg-white/10` pill; hover states use the same translucent-white treatment.
- **Bottom of sidebar**: a `bg-white/10` pill showing the logged-in account name + "Customer workspace" caption, then a ghost "Sign out" button (calls `auth.logout()`, redirects to `/login`).
- **Header**: sticky, blurred, page title derived from the active nav item (e.g. "Command Center"), fixed subtitle "What changed, why it matters, and what needs your attention." on every page (not per-page copy).
- **Content well**: same `max-w-7xl` centered column pattern as the admin shell.

### 4.4 Login (`app/login/page.tsx`) — shared component, `admin` prop toggles copy

- Full-height page, a **radial gradient background** anchored top-left using the `--accent` token fading into `--background` (`bg-[radial-gradient(circle_at_10%_10%,hsl(var(--accent)),transparent_34%),hsl(var(--background))]`) — the one place in the app with a gradient.
- Two-column layout on desktop (`grid-cols-[1fr_420px]`): left side is marketing-style copy, right side is the actual form in a `Card` with `shadow-xl`.
- **Left column**: icon badge + wordmark ("PulseActalyst" or "PulseActalyst Ops" depending on `admin`), a large serif-free headline ("Welcome back to your command center." / "Sign in to operate the fleet."), and a one-line description pointing at the right credential source (admin: "the admin credentials configured in the backend environment"; customer: "the account name and password your PulseActalyst admin provisioned for you").
- **Right column card**: a small lock-icon label ("Customer login" / "Admin login"), Name field, Password field, full-width submit button ("Continue" → "Signing in" while pending) with an arrow icon.
- On submit: calls `auth.login()`; if `admin` mode and the returned role isn't `admin`, it toasts an error, logs the (wrong-surface) session back out, and stops — it does **not** silently let a customer land in `/admin/*`. On success, replaces to `/admin/dashboard` or `/dashboard` per the returned role.

### 4.5 Onboarding (`app/onboarding/page.tsx`)

- Centered single column, max width ~896px.
- Heading "What do you want to track?" + one-line description.
- **Three template cards** in a row (Competitor site / Industry blog / Own changelog — icons: trophy, newspaper, globe) — purely cosmetic selection state (`selected`), doesn't change what gets submitted; the active card gets a `border-primary bg-accent` treatment, others are plain cards with a hover lift.
- **Form card** below: "What should we call this?" (company name) + "Website URL" + a **"Check frequency" select** (Hourly / Every 6 hours / Daily, defaulting to Hourly — the same three presets used everywhere else `schedule_minutes` is shown), then a static **checklist panel** (`bg-secondary`) listing "Reading the page / Understanding structure / Preparing your first insight" with checkmark icons — always shown, not actually wired to real progress state (it's decorative, not a live task-status poll).
- Submit button: creates a `Company`, then a `Source` (`strategy: "parent"` hardcoded — **there's no auto-detection of feed/API strategy yet**, despite that being called out as a goal in the original terminology mapping — `schedule_minutes` now comes from the selector above, not a hardcoded `60`), then immediately calls `baselineSource()`. On success, toasts "Initial scan queued." and redirects straight to `/dashboard`.

### 4.6 Command Center (`app/dashboard/page.tsx`)

- **Greeting card**: full-width bordered card, a small pill-shaped "PulseActalyst Command Center" eyebrow (sparkle icon), "Good day, {name}." headline, a dynamic subtitle ("N updates need your attention." or "Everything important has been reviewed."), and a "Track a website" button linking to `/monitors`.
- **4 KPI tiles** (`sm:grid-cols-2 xl:grid-cols-4`, hover-lift): Active Monitors, New Insights This Week, Needs Review — computed client-side from real data (`sources`/`insights` queries) — and **Avg. Time to Insight**, now sourced from `GET /insights/stats`'s `avg_seconds_to_insight` and rendered through `formatDurationShort()` (e.g. "42m", "3h", "2d", or "No data yet" with zero insights) instead of a hardcoded string. Numbers render in `font-mono tabular-nums`.
- **Empty-state banner** (only when there are zero sources): two-column card — left: "Track your first website in under a minute." + description + "Start onboarding" button; right: a `bg-secondary` panel repeating the same 3-step checklist as onboarding.
- **Two-column grid below** (`xl:grid-cols-[1fr_380px]`):
  - **Left — "Latest Intelligence"**: up to 6 insight cards, each with a rounded-full initials avatar (from `getInitials(companyName)`, computed via source→company lookup maps built client-side from the sources/companies lists), headline + severity badge, a 180-char-truncated summary, and a footer row (company name, relative time via `Intl.RelativeTimeFormat`, "View original page" link).
  - **Right, stacked**:
    - **"Needs Your Attention"** — up to 4 insights where `!reviewed_at && severity !== "low"`, each with a severity badge, an inline "Mark reviewed" button (calls `PATCH /insights/{id}/review`), title, truncated summary.
    - **"18-day Trend"** — an 18-bar mini bar chart, now the last 18 entries of `GET /insights/stats?days=30`'s real daily counts, each bar height scaled against the window's max day and titled with the exact date + count on hover. Renders "No insights yet." instead of bars when the window is empty. A button links to `/trends`.

### 4.7 Monitors (`app/monitors/page.tsx`)

- Header row: title + subtitle, and a search input (with a search icon) filtering the source list client-side by URL/company text.
- **"Add monitor" card**: four-field inline form (Tracked company name, Website URL, **Check frequency select** — Hourly / Every 6 hours / Daily, Add button) — creates a `Company` + `Source` (with the chosen `schedule_minutes`, no longer hardcoded to 60) + baseline in one submit. `strategy` is still hardcoded to `"parent"`.
- **Card grid** (`md:grid-cols-2 xl:grid-cols-3`), one `MonitorCard` per source:
  - Rounded-full initials avatar (`bg-accent`) + company name (links to `/monitors/:id`) + truncated URL.
  - Active/Paused badge.
  - A **12px-tall real sparkline** — 14 bars, one per day, sourced from `GET /insights/stats?days=14`'s `by_source_daily[source.id]` (fetched once for the whole page, passed down per-card). Shows "No activity in the last 14 days" instead of flat bars when the source has zero insights in that window.
  - Freshness (`formatRelativeTime(last_checked_at)`) and check frequency, the latter shown via a `cadenceLabel()` helper that buckets `schedule_minutes` into "Hourly" (≤60), "Every 6 hours" (≤360), or "Daily" (else) — a real friendly-preset mapping, not raw minutes.
  - **"Check now" button** — calls the shared `useSourceCheck(sourceId)` hook (`frontend/lib/use-source-check.ts`): posts `POST /sources/{id}/run`, then polls `GET /tasks/{task_id}` every 2s until the Celery task reaches a terminal state (`SUCCESS`/`FAILURE`/`REVOKED`). While in flight, the button shows a spinning `Loader2` icon and the label "Checking", and is disabled; on completion it toasts success/failure and invalidates the sources and insights queries so the card, freshness badge, and sparkline all refresh. Plus an external-link icon button opening the real site.
- Empty state: centered icon + "No monitors yet" + description, swapped in when the filtered list is empty and not loading.

### 4.8 Monitor Detail (`app/monitors/[id]/page.tsx`)

- Back link ("← Back to monitors"), company name as the page title (not the raw URL — a deliberate customer-facing improvement over the admin source-detail page, which titles on the URL), Active/Paused badge, the real URL as a clickable link below.
- Action buttons: "Check now" (same `useSourceCheck` hook as the Monitors page — `RefreshCw` icon swaps for a spinning `Loader2` and the label becomes "Checking" while the task is in flight) and "Pause"/"Resume" (toggles `source.enabled` via `PATCH /sources/{id}`).
- **Two-column layout** (`xl:grid-cols-[1fr_340px]`):
  - **Left — "AI Insight Timeline"**: every summary for this source, each parsed by a client-side `splitInsight()` function that looks for the literal labels `HEADLINE:`, `UPDATE:`, `KEY DETAILS:`, `FOLLOW UP:` inside the raw summarizer text and slices them into sections — genuinely turning the summarizer's plain-text output into structured, icon-labeled blocks (`bg-secondary` panels, one per section) instead of a text dump. If none of the labels are found, the whole string falls back into an "UPDATE" section. Each card also shows a severity badge and an "Original" link to the source page.
  - **Right sidebar**: "About This Monitor" (created date, last-checked relative time, cadence, insight count) and an "Alerts" card that just points to `/notifications` rather than managing recipients inline.
- Empty state: "No insights yet. Run a check now, or wait for the next scheduled scan."

### 4.9 Insights (`app/insights/page.tsx`)

- Header + search input + a "Needs attention" toggle button (filled when active) that restricts the list to `!reviewed_at && severity !== "low"`.
- Single card, "{N} insights" title, list of full-width insight rows (title + severity badge + a "reviewed" success badge once acknowledged + truncated 260-char summary + relative time + original-page link + inline "Mark reviewed" button for unreviewed ones).
- This is the only page that queries up to 200 insights at once (`listInsights(200)`) — everywhere else caps at 100 or 6.

### 4.10 Trends (`app/trends/page.tsx`)

All four sections now come from a single `GET /insights/stats?days=30` call (`companies` is the only other query on this page):

- 4 KPI tiles: **Insight volume (30d)** (sum of the real daily series), **Tracked companies** (real count), **Busiest monitor** (the top entry's count from `busiest_sources`), **Time to insight** (`formatDurationShort(avg_seconds_to_insight)`).
- **"Insight Volume Over Time"**: a 30-bar chart driven directly by the `daily` array, bar height scaled to the window's max day; renders "No insights in the last 30 days." when the total is zero.
- **"Breakdown By Company"**: for each entry in `by_company` (sorted by count, descending), a labeled progress bar whose width is scaled against the highest-count company — genuinely insight volume per company now, not a monitor-count proxy.
- **"Busiest Monitors"** (new section): the top 5 sources from `busiest_sources`, each row showing the truncated URL and its insight count for the 30-day window — replaces the old mislabeled KPI tile with an actual ranked list.

### 4.11 Notifications (`app/notifications/page.tsx`)

- **"Alert cadence"** card: 4 selectable option tiles — Instant, Daily digest, Weekly digest, Manual review. **Instant/Daily/Weekly all write the same backend value, `"automatic"`** — there is no real distinction between them yet; only "Manual review" (`"manual"`) is functionally different. The UI presents four choices; the backend only has two states.
- **"Alert recipients"** card: one section per company, recipient emails shown as removable pill chips (not a table, unlike the admin Email page), an inline add-recipient form per company.

### 4.12 Settings (`app/settings/workspace/page.tsx`) — one page, four cards, `xl:grid-cols-2`

- **Workspace**: display name (= logged-in account name), tracked company count, active monitor count.
- **Team**: a single-row "team list" showing only the logged-in user themselves (initials avatar + "Provisioned account"), with copy explicitly stating "Need to add a teammate? Contact your PulseActalyst admin." — matches the as-designed read-only model, no invite UI.
- **Billing**: a static `Badge variant="secondary"` reading "Pilot", monitor usage count, and "Plan changes are handled directly by your PulseActalyst admin." No real billing data anywhere.
- **Account**: name, role (literally prints `auth.session?.role`, i.e. "admin" or "customer"), and "Password changes are handled in the backend environment configuration."

### 4.13 Admin Console Changes

`components/app-shell.tsx` (the original ops shell) got exactly two changes:
1. A new nav item, **Accounts** (`BarChart3` icon, `/admin/accounts`), inserted second in the list.
2. A **Sign out** button added to the bottom of the sidebar (previously the admin shell had no logout affordance at all, since there was no auth) — calls `auth.logout()`, redirects to `/admin/login`.

Everything else in the admin shell is byte-for-byte what's documented in [fullstack_design.md §3](fullstack_design.md), **including the header copy, which still literally reads "Website Monitor" / "Operations dashboard"** — the rename to "PulseActalyst Ops" happened on the login page and in this document, but not in the actual admin sidebar component. Worth fixing if/when someone next touches `app-shell.tsx`.

`app/admin/accounts/page.tsx` (new): a single card, "Configured customers" title, a 4-column table (Name, Companies, Monitors, Last login) sourced from `GET /admin/accounts`. Empty state: "No customer accounts" + "Add USER_n_NAME and USER_n_PASSWORD entries to the backend environment." if the configured list is empty.

---

## 5. Terminology Mapping — Confirmed Against the Running Code

| Backend term | Customer-facing term | Confirmed as |
|---|---|---|
| `Company` | "Tracked company" | `companies.owner_name` scopes it per account |
| `Source` | **Monitor** | Nav item, page titles, `MonitorCard`, `MonitorDetailPage` |
| `strategy` | *hidden in the customer app* | Still hardcoded to `"parent"` on every customer-created source — auto-detection was proposed but **not implemented** |
| `schedule_minutes` | "Check frequency" (Hourly / Every 6 hours / Daily) | `cadenceLabel()` displays it everywhere it's shown; a matching 3-option `Select` now sets it at creation time in both onboarding and the Monitors "Add monitor" form — no longer a display-only mapping |
| Baseline run | "Initial scan" | Toast copy in onboarding/monitors ("Initial scan queued.") |
| `Summary` | **Insight** | `severity`, `reviewed_at` fields now exist to support this directly |
| `MonitorRun` | *hidden* | Replaced by `formatRelativeTime(last_checked_at)` freshness badges |
| `NotificationRecipient` | "Alert recipient" | Notifications page pill chips |

---

## 6. What Would Turn This From "Working Demo" Into "Real Product"

In rough priority order, based on what's stubbed above. ~~Struck through~~ items were fixed since the previous revision of this doc.

1. ~~Real trend data~~ — **done**: `GET /insights/stats` now backs the Dashboard trend, Trends page charts/breakdown/busiest-monitors, and Monitors card sparklines with real, owner-scoped data.
2. ~~Check frequency at creation~~ — **done**: onboarding and Add-monitor both expose a real Hourly/Every 6 hours/Daily selector wired to `schedule_minutes`.
3. ~~"Check now" feedback~~ — **done**: `useSourceCheck` polls the task to completion and shows a real loading state instead of a fire-and-forget click.
4. **Strategy auto-detection** — every customer-created source is still hardcoded `parent`; feeds and APIs still require the admin console.
5. **Distinct notification cadences** — Daily/Weekly digest still need their own backend value and an actual scheduled digest job, not an alias for `automatic`.
6. **Admin shell copy** — still needs the rename finished in `app-shell.tsx`.
7. **Theme toggle** — the CSS is ready; still needs a switch that flips a `.dark` class.
8. **Team invites / billing** — both are intentionally deferred per the original design (§5.8 of the prior version); still true today.
