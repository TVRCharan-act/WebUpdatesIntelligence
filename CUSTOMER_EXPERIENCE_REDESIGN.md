# PulseActalyst — Customer Experience Redesign

> From "a dashboard for a monitoring tool" to "an analyst that watches the web for you." This is a design proposal, not yet built — see §10 for exactly what's a reskin vs. what needs real backend work.

---

## 0. The Thesis

Right now, a customer who logs in sees KPI tiles, a card grid, and a list of AI-generated text blocks. It's honest and functional, but it reads as **infrastructure they're operating**, not **intelligence being delivered to them**. Nothing before this redesign was fake in a misleading way — the charts are real (§ previous revisions of this doc) — but the *presentation* still asks the customer to do the synthesis themselves: scan a table, notice a badge, infer what matters.

The shift this proposal makes: **stop showing customers their data, and start showing them conclusions.** Every screen should read like a briefing prepared by a sharp analyst who already did the work — here's what changed, here's why you should care, here's what to do about it. The customer's job should never be "figure out what's important here"; it should be "decide what to do about what PulseActalyst already flagged."

---

## 1. Ground Truth Check — What Has to Change in the Backend First

This section exists because the previous revision of this document spent real effort replacing fake charts with real ones, and this proposal should not quietly reintroduce fabricated data under a prettier UI. Before any visual work, here's what's actually possible today vs. what requires a real backend change:

| Requested signal | Status today | What's needed |
|---|---|---|
| **What changed** | Real — `Summary.summary` (parsed `UPDATE:` section) | Nothing |
| **Time detected** | Real — `Summary.created_at`, `DiscoveredUrl.discovered_at` | Nothing |
| **Source** | Real — `DiscoveredUrl.url`, `Source.url` | Nothing |
| **Severity** | **Not real today.** The `severity` column exists (migration `20260709_0004`) but nothing in `monitor_service.py` or `openai_summarizer.py` ever sets it — every generated insight defaults to `"medium"` and stays there forever. | The summarizer prompt must classify severity per-article; `new_url_processor.py` must write the model's classification instead of relying on the DB default. |
| **Why it matters / Business impact** | **Not real today.** The current prompt (`mysignal/summarizers/openai_summarizer.py`) only produces `HEADLINE / UPDATE / KEY DETAILS / FOLLOW UP` — there is no "why it matters" or "business impact" framing anywhere in the pipeline. | Rewrite the system prompt to a 6-part structure (§3.2) that asks the model to produce these explicitly. |
| **Recommended action** | **Not real today, and currently mislabeled.** `FOLLOW UP:` in the current prompt is defined as *"Read the full update here: <source URL>"* — a literal read-more link, not guidance. The frontend's `splitInsight()` already renders it as if it were a "Follow Up" insight, which is misleading. | Same prompt rewrite — a genuine `RECOMMENDED_ACTION` field, separate from the source link (which the UI already renders elsewhere as "View original page"). |
| **AI confidence** | **Doesn't exist at all.** No column, no prompt field, nothing. | New `confidence` field: prompt asks the model to self-rate (e.g., `high` / `medium` / `low`, or a 0–100 score), new `summaries.confidence` column, parsed and stored like `severity`. |
| **Emerging trends** | Computable now — `GET /insights/stats` already returns daily counts; comparing this week's volume to a trailing average is pure aggregation, no AI needed. | Extend `crud.get_insight_stats` to also return a week-over-week delta. Pure backend query work, no LLM involved. |
| **Time saved** | Not a real measurement — there's no baseline for "time a human would have spent." | Must be presented as an **estimated, disclosed metric** with a stated formula (§7), never as if it were measured. This is the one metric in this whole proposal that is illustrative by construction, and it should say so in the UI, not hide it. |
| **Company favicons/logos** | Real and cheap — every `Source.url` has a real domain; a live favicon fetch (e.g. via a favicon service, keyed off the source's actual domain) is a genuine image of the genuine site, not decoration. | Frontend-only. |

**Bottom line:** roughly half of this proposal is a pure frontend/visual/copy layer over data that already exists. The other half — severity, confidence, why-it-matters, business impact, recommended action — requires rewriting the summarizer prompt once (§3.2) and adding one migration (`confidence` column, mirroring how `severity` already works). That rewrite is the single highest-leverage piece of backend work in this whole proposal, because nearly every visual idea below depends on those fields being real.

---

## 2. Brand & Visual Identity

### 2.1 Personality

PulseActalyst should feel like **a sharp, calm analyst**, not a chatbot and not a dashboard. Confident, concise, a little dry — never hypey, never apologetic, never robotic. It notices things before you do and tells you plainly why they matter.

### 2.2 Signature Visual Element: "The Signal"

One motif, reused everywhere, so a screenshot is recognizable at a glance: a **continuous pulse/waveform line** — a literal signal, tying directly to the product name. This is not a new gimmick invented for this redesign; it already exists as the wordmark glyph (the small waveform tick next to "PulseActalyst" in the current login page and shell). This proposal extends that one motif consistently instead of introducing a second, unrelated visual language:

| Where | How it's used |
|---|---|
| Dashboard briefing header | A large, slow, ambient waveform behind the greeting — subtle, low-opacity, ties the "briefing" feel to the brand mark. Amplitude can genuinely reflect the account's real weekly activity level (busier week → slightly more active line) — a real data binding, not just decoration. |
| Intelligence Feed cards | A small **signal-strength indicator** (1–4 filled bars, phone-signal style) represents **AI confidence** — a distinct visual language from severity, so the two dimensions never get confused. |
| Monitor cards & dossier | The existing bar-based sparkline becomes a smooth **pulse/area line** — same real per-source daily data (`by_source_daily`), just rendered as a continuous line with a soft fill instead of discrete bars. Visually ties every monitor's trend back to the same signal language. |
| Loading / "AI is working" states | A pulse line sweeping left-to-right during onboarding's initial scan and any "check now" wait — replacing the current static checklist with something that feels alive, and reusing an element the user already recognizes from elsewhere in the product. |

This gives one system three real jobs (ambient brand mark, confidence indicator, trend chart) instead of three unrelated new widgets — which is what makes it "signature" rather than "decorative."

### 2.3 Color

Keep the existing brand teal (`hsl(199 89% 32%)`) — it's already established and shouldn't be replaced wholesale. Add exactly one new token, used for exactly one purpose, so it stays meaningful:

| Token | Value (suggested) | Used for |
|---|---|---|
| `--confidence` | a cool indigo-violet (e.g. `hsl(243 70% 60%)`) — deliberately *not* red, amber, or green | AI confidence indicators only — never reused for severity, status, or anything else. |

This token is deliberately not a warm red/amber/gold tone, because the severity badge palette already spans red (high) → amber (medium) → green/gray (low/reviewed). If confidence used any color from that same warm family, a "medium confidence" indicator next to a "medium severity" badge would visually read as the same signal when they mean opposite things. Confidence is also rendered as a *different shape* (filled bars, §2.2) rather than a badge pill, so the two dimensions are distinguishable by form as well as hue.

Severity keeps the existing red/amber/gray badge language exactly as-is (§ current `StatusBadge`/`Badge` variants) — no new severity colors needed, just real values driving them instead of a permanent `"medium"`.

### 2.4 Typography & Spacing

No new typeface needed — the existing system-font stack is fine for a product this data-dense. The change is disciplined **hierarchy**, not a new font: one large, confident number or headline per section (the thing the customer should read first), everything else visually quieter. Increase whitespace around the Dashboard's top briefing section specifically — it should feel like the one place in the app that's allowed to breathe, in contrast to the denser feed/monitor list below it.

---

## 3. Copy Voice & the AI Analyst Framing

### 3.1 Voice Principles

- **Plain, specific, confident.** "Acme raised Pro pricing 20%" beats "Significant pricing update detected."
- **Never say "record," "run," "task," "source" (as in database row), "discovered_url," or any implementation noun.** Say "update," "check," "monitor," "the page."
- **Numbers over adjectives.** "3 updates need review" beats "Some updates need review."
- **The AI explains itself.** Every insight should read as if a person is briefing you, not as if a system logged an event.

### 3.2 The 6-Part Insight Framework (requires the prompt rewrite in §1)

Replace the current 4-part `HEADLINE / UPDATE / KEY DETAILS / FOLLOW UP` structure with:

```
HEADLINE: <news-style headline, unchanged from today>
WHAT_HAPPENED: <what changed — this replaces UPDATE>
WHY_IT_MATTERS: <why this specific change is significant, in plain business terms>
BUSINESS_IMPACT: <concrete consequence — competitive, financial, operational>
RECOMMENDED_ACTION: <one specific, concrete next step — not a link, an action>
SEVERITY: low | medium | high
CONFIDENCE: low | medium | high
```

The source link moves entirely into the UI chrome (the existing "View original page" button) — it stops being a field the model has to produce, since it's already known (`DiscoveredUrl.url`) and doesn't need AI generation.

### 3.3 Before / After Copy

| Context | Before | After |
|---|---|---|
| Dashboard greeting | "Good day, Charan." | "Good morning, Charan. Here's what changed while you were away." |
| Empty insight state | "New insights will appear here after monitored pages change." | "PulseActalyst is watching. You'll hear from us the moment something worth knowing happens." |
| KPI label | "Needs Review" | "Needs Your Decision" |
| Monitor empty state | "No monitors yet" | "Nothing being watched yet — point PulseActalyst at your first website." |
| Check-now button | "Check now" | "Look now" *(optional — keeps the analyst framing; "check" reads slightly more operational)* |
| Insight card section | "FOLLOW UP" | *(removed as a labeled section — folded into "Recommended Action")* |

---

## 4. Dashboard Redesign — "Your Morning Briefing"

### 4.1 The Core Idea

The Dashboard stops being a KPI-tiles-plus-list layout and becomes a single vertical **briefing document** — read top to bottom once, understood in under 10 seconds. Every element answers exactly one of the four questions from the brief: *what changed, what matters most, why, what to do next.*

### 4.2 Layout, Top to Bottom

1. **Briefing header** (ambient Signal waveform background, §2.2): "Good morning, Charan." + one auto-generated sentence that synthesizes the whole account, e.g. *"3 high-priority updates across 2 companies need your attention — Acme's pricing change is the one to look at first."* This sentence is assembled from real data (top severity insight + count + company names), not free-text-generated by the LLM per visit — cheap, real, and fast.
2. **The One Thing** — a single, large, unmissable card for the single highest-priority unreviewed insight (highest severity, most recent). Full 6-part framework rendered large: headline, what happened, why it matters, business impact, recommended action, confidence signal, "Mark reviewed" / "View source." This is the "wow" moment — one card, full attention, real synthesis.
3. **Quick-glance metrics row** — reframed per §7, not the current infra-flavored KPI row.
4. **Everything else that needs a decision** — the rest of the unreviewed high/medium-severity insights, in the existing compact "Needs Your Attention" list style, now driven by real severity.
5. **What's quiet** (new, optional) — a small, low-emphasis line: *"12 monitors had no notable changes this week"* — this matters because silence is also information (nothing broke, nothing changed, you don't need to look). Prevents the product from feeling like it only ever shows you things.
6. **Trend strip** — existing real 18-day pulse-line chart (§2.2), now a smooth line instead of bars, linking to Trends.

### 4.3 First-Visit State

When there are zero insights yet (brand new account), the entire briefing area is replaced by a calm, confident "PulseActalyst is getting started" state — not an apologetic empty state, but a forward-looking one: *"Your first monitor is live. We're reading it now — check back shortly for your first briefing."* Paired with the Signal pulse animation (§2.2), not a static checklist.

---

## 5. Intelligence Feed Redesign — The Centerpiece

### 5.1 What Changes

Today's feed (`/insights`) is a searchable list of text blocks. The redesign turns it into a genuine **activity feed** — vertically dense, scrollable, alive, closer to a well-designed timeline than a search results page.

### 5.2 Card Anatomy (every card, every one of the 7 requested elements present)

```
┌─────────────────────────────────────────────────┐
│ [favicon]  Acme Corp · Pricing page   ●●●○ 4h ago │  ← company favicon, name+source, confidence bars, time
│                                                     │
│  Pro plan pricing quietly raised 20%     [HIGH]    │  ← headline + severity badge
│                                                     │
│  ▸ What happened   Pro tier moved $49→$59...       │
│  ▸ Why it matters   Closes half the gap with...    │
│  ▸ Business impact  Sales should expect renewal...  │
│  ▸ Recommended action  Flag to sales before Q3...   │
│                                                     │
│  [ Mark reviewed ]              [ View original ]  │
└─────────────────────────────────────────────────┘
```

- **Favicon**, not initials — real image of the real monitored domain, initials as fallback only if the favicon fails to load.
- **Confidence** rendered as the signal-bar indicator (§2.2), never as raw text like "87%" — a glanceable visual, not a number to parse.
- **Severity** as the existing colored badge — unchanged visual language, now driven by real classification.
- The four narrative fields render as labeled, iconography-light blocks — restrained, not four separate boxed cards; this should read like paragraphs in a briefing, not four form fields.

### 5.3 Interaction & Motion

- New cards entering the feed (on refresh) get a brief, subtle highlight/fade-in — signals "this is new" without a jarring animation. Respect `prefers-reduced-motion`.
- Reviewing an insight collapses its narrative detail to a single summary line with a "reviewed" checkmark — keeps the feed scannable once you've acted on things, without deleting history.
- Filters stay (search, "needs attention"), but add a severity filter chip row now that severity is real and varies.

---

## 6. Monitor Experience Redesign

### 6.1 Monitor Card (List View)

Replace the current URL-plus-badge card with one built around **what the monitor is telling you**, not what it is:

- Favicon + company name (unchanged position, real image now).
- **Monitoring health**, not just Active/Paused — a small status line: "Watching normally" / "Hasn't found anything new in 12 days" / "Paused" — turns a binary badge into an actual signal about whether this monitor is doing its job.
- **Last important event** — one line, the most recent *high-or-medium*-severity insight's headline (not just "last checked"), so the card itself communicates value without a click.
- **Activity pulse** — the smooth line version of the real per-source sparkline (§2.2), replacing the bar chart.
- **Confidence** — small signal-bar average across this monitor's recent insights.
- "Look now" action with the existing spinner-while-checking behavior — unchanged, it already works well.

### 6.2 Monitor Detail — "The Intelligence Dossier"

Reframe the whole page as a dossier on one tracked entity, not a settings page for one database row:

1. **Header**: company name, favicon, monitoring health line (as above), Look now / Pause.
2. **At a glance strip**: 3–4 small stats — insights this month, average confidence, current severity mix (e.g. "1 high · 2 medium this week"), monitoring cadence in plain language ("Checked hourly").
3. **Activity over time** — the real pulse/area chart, full width, more prominent than today's tiny sidebar stat.
4. **The Intelligence Timeline** — same 6-part-framework cards as the Feed (§5.2), scoped to this monitor, in chronological order — this *is* the dossier's substance.
5. **Sidebar** stays lightweight: created date, alert recipients link — administrative facts, deliberately de-emphasized relative to the timeline.

---

## 7. Metrics Reframing

| Metric | Replaces | Real / Estimated | Computation |
|---|---|---|---|
| **Important updates detected** | "New Insights This Week" | Real | Count of insights this week, unchanged data, reframed label |
| **High-priority insights** | "Needs Review" | Real (once severity is real, §1) | Count where `severity == "high"` and unreviewed |
| **Websites actively monitored** | "Active Monitors" | Real | Unchanged |
| **AI confidence** (account-wide) | *(new)* | Real, once `confidence` field exists (§1) | Average confidence across recent insights |
| **Emerging trend** | *(new)* | Real | Week-over-week % change in insight volume, from an extended `/insights/stats` |
| **Activity level** | *(new, qualitative)* | Real | A plain-language label ("Quiet" / "Normal" / "Busy") derived from the same trend comparison — no new data needed |
| **Time saved** | *(new)* | **Estimated — must be visually marked as an estimate** | e.g. `reviewed_insights × 4 minutes` (a disclosed, editable assumption — "estimated minutes a manual check-and-read would take"), shown with a small "estimated" label and a tooltip explaining the formula. This is the one number in the product that isn't a direct count — it must never be presented as if it were measured. |

**Guardrail:** every metric above is either a real count/average from real data, or explicitly labeled as an estimate with its formula disclosed on hover. Nothing here is decorative.

---

## 8. Onboarding Redesign — "Meet Your Analyst"

Keep the existing structural flow (template choice → URL + name + cadence → baseline → land on dashboard) — it's sound. Elevate the *feel*:

1. **Template step**: unchanged, but reframe copy from generic labels to outcome-oriented ones — "Track a competitor," "Watch an industry source," "Monitor your own site" (same three options, sharper wording).
2. **The scan step**: replace the static checklist with the Signal pulse animation (§2.2) and copy that narrates comprehension, not process — *"Reading acme.com/pricing…"* → *"Understanding what's on this page…"* → *"Ready. We'll tell you the moment something changes."* This should feel like the product is genuinely paying attention, not running a script (even though, honestly, it is running a script — the point is the copy should describe what it's doing for the customer, not what's happening in Celery).
3. **The reveal**: land on the Dashboard's "One Thing" card (§4.2) pre-populated with the real first-look insight from the baseline scan — the "wow" moment isn't a toast notification, it's arriving on a Dashboard that already has something real and specific to show, in the first 60 seconds.

---

## 9. Visual Language System — Reusable Components

A short inventory of what needs to exist as an actual shared component (not re-implemented per page), so the product stays consistent as it grows:

| Component | Used in |
|---|---|
| `ConfidenceSignal` (1–4 bar indicator) | Feed cards, monitor cards, dossier |
| `ActivityPulse` (smooth line/area chart) | Dashboard trend, monitor card, dossier |
| `SeverityBadge` (existing, just fed real data) | Feed, dashboard, dossier |
| `CompanyFavicon` (real image + initials fallback) | Everywhere a company/monitor currently shows initials |
| `InsightCard` (the full 6-part layout) | Feed, dossier — one component, two contexts |
| `AnalystEmptyState` (Signal-animated, confident copy) | Every empty state in the customer app |
| `ThinkingState` (Signal sweep animation) | Onboarding scan, check-now wait states |

---

## 10. Implementation Roadmap

| Tier | Scope | Depends on |
|---|---|---|
| **Tier 1 — pure frontend** | Favicons, `ConfidenceSignal`/`ActivityPulse` visual components (using existing real data), Dashboard restructure, copy pass, empty/loading state redesign | Nothing — buildable immediately |
| **Tier 2 — backend content upgrade** | Rewrite `openai_summarizer.py` system prompt to the 6-part framework; add `summaries.confidence` column + migration; wire real severity/confidence into `new_url_processor.py`; extend `/insights/stats` with week-over-week trend | Required before Feed/Dossier cards can show real why-it-matters, business impact, recommended action, confidence, or varying severity |
| **Tier 3 — polish** | Card entrance animations, ambient waveform data-binding on the Dashboard header, "time saved" estimate tooltip | Nice-to-have, no dependencies beyond Tier 1 |

Tier 1 and Tier 2 can ship independently and in either order — Tier 1 makes the *existing* fields (headline, what-happened, severity-as-is, time, source) look dramatically better immediately; Tier 2 is what makes the new fields (why it matters, business impact, recommended action, confidence, real severity) genuinely true rather than placeholder copy.

---

## 11. Guardrails

- **No fabricated metrics.** Every number either comes from a real query or is explicitly labeled as an estimate with its formula visible (§7).
- **Confidence and severity are different axes** — never conflate "how sure the AI is" with "how bad this is" in either color or copy.
- **Respect `prefers-reduced-motion`** on every animated element (Signal waveform, card entrances, loading sweeps).
- **The Signal motif is used for exactly three things** (ambient brand mark, confidence, activity trend) — resist the urge to add a fourth unrelated use; that's what keeps it feeling like a considered system instead of a decoration applied everywhere.
- **Don't let the briefing framing replace functionality** — search, filtering, pause/resume, cadence editing, and everything else that currently works must survive this redesign untouched underneath the new presentation.

---
---

# Part II — Build Spec (Tier 1: Frontend-Only, Honest-Data)

> Part I (§0–§11) is the strategy. Part II is the **execution layer**: exact wireframes, component APIs, copy strings, motion timings, visual-hierarchy calls, and accessibility rules for the version we can ship **without any backend change**. Everything here was reconciled against the running code on 2026-07-10 (`frontend/app/*`, `frontend/lib/*`, `backend/app/models.py`, `mysignal/summarizers/openai_summarizer.py`). Where Part I designs around a field that isn't real yet, Part II says so and specifies the honest fallback.

## 12. The Honesty Contract — What Ships Now vs. What's a Reserved Slot

This is the single most important table in Part II. **Frontend-only means we present only what the code actually produces today.** The verification behind each row:

| Signal | Reality in code today | Tier-1 (frontend-only) treatment |
|---|---|---|
| Headline | Real — `Summary.title`, or parsed `HEADLINE:` from `summary` | **Ship.** Primary line of every card. |
| What happened | Real — parsed `UPDATE:` section | **Ship.** Body of every card. |
| Key details | Real — parsed `KEY DETAILS:` bullets | **Ship**, as a collapsible detail. |
| Time detected | Real — `Summary.created_at` | **Ship.** Relative time, `formatRelativeTime()`. |
| Source / original page | Real — `Summary.discovered_url` | **Ship.** "View original" chrome. The `FOLLOW UP:` section is currently *only* a "Read the full update here: <url>" line (`openai_summarizer.py:37-40`) — **stop rendering it as an insight section** (today `splitInsight()` shows it as a "Follow Up" block, which is misleading); it collapses into the "View original" button. |
| Company favicon | Real & frontend-only — every `Source.url` has a domain | **Ship.** `CompanyFavicon` (§14.1), initials fallback. |
| Per-monitor activity trend | Real — `InsightStats.by_source_daily[source.id]` | **Ship.** `ActivityPulse` line chart (§14.2). |
| Account activity trend | Real — `InsightStats.daily[]` | **Ship.** Dashboard trend strip + Trends page. |
| Emerging trend / activity level | **Real, computable frontend-only** — this week vs. trailing weeks from `daily[]` (a 30-day window already returned by `getInsightStats(30)`). *Part I §1 said this needs a backend change; it does not — the daily array is sufficient.* | **Ship.** `deriveTrend(daily)` helper (§14.7). |
| Time saved | Estimate — `reviewedCount × assumedMinutes`; no measured baseline exists | **Ship, but only with an explicit "Estimated" tag + formula tooltip** (§7 guardrail). Never a bare number. |
| **Severity** | Column exists (`models.py:142`), but **nothing in `mysignal/` ever sets it** — every insight is permanently `"medium"`. | **Degrade honestly.** Keep `SeverityBadge` (it reads a real field), but **do not build prioritization, colored sorting, or a severity filter that implies variety that isn't there.** Rank by recency. The badge is wired and correct; it simply won't vary until Tier 2. Design so a wall of identical "medium" badges never looks broken (§14.3). |
| **AI confidence** | **Does not exist** — no column, no prompt field. | **Reserve, don't render.** `ConfidenceSignal` is *specified* (§14.8) so the layout has a home for it, but it is **not mounted** in Tier 1. No fake bars, no "87%". |
| **Why it matters / Business impact / Recommended action** | **Not produced** — prompt emits only HEADLINE/UPDATE/KEY DETAILS/FOLLOW UP. | **Reserve, don't fabricate.** `InsightCard` has a defined region for these; in Tier 1 that region is simply **absent** (not a skeleton, not "coming soon" copy on every card — that would read as broken). One single, honest, dismissible product note may appear once (§15.3), not per-card. |

**The rule that governs all of Part II:** a slot with no real data is *not drawn* in Tier 1. We do not ship placeholder shimmer that never resolves, and we do not ship invented text. The layouts below are designed so they look **complete and intentional with today's data**, and the reserved regions light up later without a re-layout.

## 13. Design Tokens — Additions & Changes (globals.css)

Only what Tier 1 actually uses. All are additive; none change the two existing surfaces' current look except where noted.

```css
:root {
  /* --- existing tokens unchanged (primary teal 199 89% 32%, radius .7rem, etc.) --- */

  /* Signature "Signal" ink — the waveform/pulse motif. Derived from primary,
     used ONLY for the ambient waveform + ActivityPulse stroke/fill. */
  --signal: 199 89% 42%;
  --signal-fill: 199 89% 42%;      /* used at low alpha for area fills */

  /* Reserved — NOT referenced by any Tier-1 component. Documented so Tier 2
     doesn't invent a color. Cool indigo, deliberately outside the severity
     red/amber/green family (Part I §2.3). */
  --confidence: 243 70% 60%;

  /* Briefing surface — the one area allowed to breathe (Dashboard header). */
  --briefing-bg: 199 60% 97%;      /* light */
}
.dark {
  --signal: 199 89% 55%;
  --briefing-bg: 205 44% 12%;
  --confidence: 243 74% 68%;
}
```

Motion tokens (referenced throughout §17):

```css
:root {
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);   /* entrances, "settle" */
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --dur-fast: 120ms;    /* hover, press */
  --dur-base: 220ms;    /* card entrance, expand/collapse */
  --dur-slow: 420ms;    /* new-item highlight fade, page-level */
  --dur-ambient: 8s;    /* Signal waveform drift loop */
}
```

**Type scale** (no new font — enforce hierarchy with size/weight only):

| Role | Size / weight | Where |
|---|---|---|
| Briefing headline | `text-3xl`→`text-4xl` / 600 | Dashboard greeting only |
| Hero insight headline | `text-2xl` / 600 | "The Latest" card |
| Section title | `text-lg` / 600 | Card headers |
| Card headline | `text-base` / 600 | Feed / dossier insight cards |
| Metric value | `text-3xl` / 600 `font-mono tabular-nums` | Metric tiles (existing) |
| Body | `text-sm` / 400 | Narrative, summaries |
| Meta | `text-xs` / 500 `text-muted-foreground` | Time, source, labels |

## 14. Shared Component Inventory & API Specs

New file locations: `frontend/components/intel/*` for product-specific pieces; keep `components/ui/*` for primitives. TypeScript signatures below are the contract — props not listed should not exist.

### 14.1 `CompanyFavicon` — **ship**

```ts
// components/intel/company-favicon.tsx
interface CompanyFaviconProps {
  url: string;              // Source.url — domain is extracted internally
  name: string;             // company name, for initials fallback + alt text
  size?: 24 | 32 | 40 | 44; // default 40; matches current avatar sizes
  className?: string;
}
```
- Renders `https://www.google.com/s2/favicons?sz=64&domain={host}` (or your chosen favicon service) inside a `rounded-xl` (not full-circle — a subtle brand shift from today's `rounded-full` initials) tile with a hairline border and `bg-card`.
- `onError` → swap to the existing `getInitials(name)` treatment (reuse `bg-accent text-accent-foreground`). Never shows a broken-image glyph.
- `alt=""` when initials are also shown; otherwise `alt={name}`. Decorative when adjacent to the name text (which is the common case) — mark `aria-hidden`.

### 14.2 `ActivityPulse` — **ship** (this is the Signal motif as a chart)

```ts
// components/intel/activity-pulse.tsx
interface ActivityPulseProps {
  data: number[];                 // per-day counts, oldest→newest (by_source_daily / daily)
  height?: number;                // px, default 48 (card), 96 (dashboard), 288 (trends)
  variant?: "line" | "area";      // default "area"
  emptyLabel?: string;            // shown when data is all-zero / empty
  ariaLabel: string;              // e.g. "14-day activity for Acme"
}
```
- Replaces the three separate bar-chart implementations currently duplicated in `dashboard/page.tsx`, `monitors/page.tsx` (`MonitorCard`), and `trends/page.tsx`. **One component, three sizes.** This dedup is itself a Tier-1 win.
- Smooth `<path>` (Catmull-Rom→bezier) stroke in `hsl(var(--signal))`, area fill `hsl(var(--signal-fill)/0.12)`. Baseline gridline at 0.
- Renders as inline SVG, `role="img"`, `aria-label` required. Purely CSS/SVG — no chart lib, no new dependency.
- All-zero data → centered `emptyLabel` (e.g. "No activity in the last 14 days"), not a flat line that reads as "down".
- Respects `prefers-reduced-motion`: the draw-on-enter stroke animation (§17) is skipped; the final path renders immediately.

### 14.3 `SeverityBadge` — **ship (honest-uniform)**

```ts
interface SeverityBadgeProps { severity: "low" | "medium" | "high"; }
```
- Thin wrapper over the existing `Badge` variants (`destructive`/`warning`/`secondary`). No new visuals.
- **Guidance, not code:** because every value is `"medium"` today, do **not** use severity as a sort key, a filter dimension, or a color-coded left-border on cards in Tier 1. The badge is present and correct; it just doesn't carry information yet. Revisit sort/filter in Tier 2. (This is a deliberate downgrade of Part I §5.3's "severity filter chip row" — hold it until values vary.)

### 14.4 `InsightCard` — **ship (with reserved region)**

```ts
// components/intel/insight-card.tsx
interface InsightCardProps {
  insight: Summary;               // existing type
  companyName: string;
  density?: "feed" | "compact";   // feed = full; compact = dashboard "needs review" list
  onReview?: (id: number) => void;
  isReviewing?: boolean;
}
```
Anatomy (feed density), top to bottom — **only real fields**:
```
┌──────────────────────────────────────────────────────────┐
│ [◧ favicon]  Acme Corp · acme.com/pricing        · 4h ago  │  ← CompanyFavicon + source + time
│                                                            │
│  Pro plan pricing quietly raised 20%          [ reviewed ] │  ← headline (parsed) + review state
│                                                            │
│  Acme moved its Pro tier from $49 to $59/mo and added a    │  ← WHAT HAPPENED (parsed UPDATE)
│  usage cap to the entry plan…                              │
│                                                            │
│  ▸ Key details (3)                                         │  ← collapsible; parsed KEY DETAILS bullets
│                                                            │
│ ····· reserved: Why it matters · Business impact ·         │  ← NOT rendered in Tier 1 (no data)
│ ····· Recommended action · Confidence  (Tier 2) ·····      │
│                                                            │
│  [ Mark reviewed ]                        [ View original ]│
└──────────────────────────────────────────────────────────┘
```
- The dotted reserved line above is **documentation only** — in shipped Tier-1 markup that region is absent, and the card's padding is tuned to look complete without it.
- `splitInsight()` moves out of `monitors/[id]/page.tsx` into `lib/parse-insight.ts` (shared by feed + dossier), and **drops `FOLLOW UP` from the rendered sections** (it becomes the "View original" href only).
- Reviewing collapses the card to a single summary line + checkmark (Part I §5.3), animated per §17.4.

### 14.5 `AnalystEmptyState` — **ship**

```ts
interface AnalystEmptyStateProps {
  title: string;
  body: string;
  action?: { label: string; href: string };
  animated?: boolean;   // default true → renders the ThinkingState pulse; false → static
}
```
Replaces the four+ ad-hoc `border-dashed` empty blocks. Confident, forward-looking copy (§16), never apologetic.

### 14.6 `ThinkingState` — **ship**

```ts
interface ThinkingStateProps {
  lines?: string[];     // narrated steps, cycled; default onboarding copy (§16)
  ariaLabel?: string;
}
```
- A left→right sweeping Signal pulse (SVG stroke with an animated `stroke-dashoffset`), used for onboarding's initial scan and any "Check now" wait.
- Under `prefers-reduced-motion`: no sweep; show a static pulse glyph + the current line only.

### 14.7 `deriveTrend(daily)` — **ship (pure function, no backend)**

```ts
// lib/trend.ts
interface TrendResult {
  level: "Quiet" | "Normal" | "Busy";
  deltaPct: number | null;   // this-week vs prior-week avg; null if <14 days data
  direction: "up" | "down" | "flat";
}
function deriveTrend(daily: DailyInsightCount[]): TrendResult;
```
Computed entirely from the `daily[]` already returned by `getInsightStats(30)`. Backs the "Emerging trend" and "Activity level" metrics honestly (Part I §7) with zero backend work.

### 14.8 `ConfidenceSignal` — **RESERVED, do not mount in Tier 1**

```ts
interface ConfidenceSignalProps { level: "low" | "medium" | "high"; }
```
Specified so Tier 2 has an exact target (1–4 filled phone-style bars in `hsl(var(--confidence))`, distinct shape from severity per Part I §2.3). **Not imported by any Tier-1 screen.** Listed here only to prevent re-invention.

## 15. Screen-by-Screen — Wireframe · Hierarchy · Copy · States

For each screen: the reading order we're engineering (**1** = eye lands here first), an ASCII wireframe, per-screen copy changes, and the loading/empty states. Only real data appears.

### 15.1 Dashboard — "Your Morning Briefing" (`app/dashboard/page.tsx`)

**Visual hierarchy:** **1** greeting + one-sentence synthesis → **2** "The Latest" hero card → **3** metrics row → **4** everything else needing review → **5** what's quiet → **6** trend strip.

```
╔══════════════════════════════════════════════════════════════╗
║  ◜ ambient Signal waveform, low-opacity, drifts (§17.1) ◝      ║
║  PULSEACTALYST · BRIEFING                                      ║   1
║  Good morning, Charan.                                         ║
║  6 updates landed since Tuesday — the newest is Acme's         ║   ← synthesized from REAL data
║  pricing page change, 4 hours ago.                             ║      (count + recency + company)
╚══════════════════════════════════════════════════════════════╝
┌── THE LATEST ────────────────────────────────────────────────┐
│ [◧] Acme Corp · acme.com/pricing · 4h ago                     │   2  ← hero = most-recent unreviewed
│ Pro plan pricing quietly raised 20%                           │      (recency rank; honest, not
│ Acme moved its Pro tier $49→$59 and added a usage cap…        │       severity — see §14.3)
│ ▸ Key details (3)          [ Mark reviewed ] [ View original ]│
└───────────────────────────────────────────────────────────────┘
┌ Websites watched ┐┌ Updates this wk ┐┌ To review ┐┌ Time saved* ┐  3
│        12         ││        6        ││     4     ││   ~48 min   │  *estimated, tooltip
└──────────────────┘└─────────────────┘└───────────┘└─────────────┘
┌── NEEDS YOUR REVIEW (4) ─────────┐ ┌── ACTIVITY ─────────────┐
│ • Beta Inc · Careers  · 1d       │ │  ╱╲    ╱╲   ╱ (ActivityPulse│ 6
│ • Acme · Blog        · 2d        │ │ ╱  ╲__╱  ╲_╱   18-day)     │
│ • …                              │ │            [ Open trends ]  │
└──────────────────────────────────┘ └─────────────────────────┘   4
┌──────────────────────────────────────────────────────────────┐
│ 8 monitors had nothing worth flagging this week. (that's good) │   5  ← "what's quiet"
└──────────────────────────────────────────────────────────────┘
```

Copy deck:

| Element | Before (today) | After |
|---|---|---|
| Eyebrow | "PulseActalyst Command Center" | "Briefing" (with the Signal glyph) |
| Greeting | "Good day, Charan." | Time-aware: "Good morning, Charan." (`< 12h` / `< 18h` / else) |
| Synthesis | "6 updates need your attention." | "6 updates landed since {lastVisit or 'your last visit'} — the newest is {company}'s {pageLabel} change, {relTime}." — assembled in JS from real counts + newest unreviewed insight. No LLM call. |
| Hero label | *(none — it's just the first list item)* | "The Latest" |
| Metric labels | "Active Monitors / New Insights This Week / Needs Review / Avg. Time to Insight" | "Websites watched / Updates this week / To review / Time saved" (see §18) |
| Empty (0 sources) | "Track your first website in under a minute." | keep, but route through `AnalystEmptyState` with the pulse; headline "Point PulseActalyst at your first website." |
| Empty (0 insights, ≥1 source) | "New insights will appear here after monitored pages change." | "PulseActalyst is watching. The moment something worth knowing changes, it lands here first." |

States: **loading** → briefing header renders immediately (name is local); hero + metrics show skeletons for `≤600ms`. **First-visit (source exists, scan running)** → hero replaced by `ThinkingState` with "Taking a first look at {domain}…".

### 15.2 Intelligence Feed (`app/insights/page.tsx`) — the centerpiece

**Hierarchy:** **1** filter bar (search + "To review" toggle) → **2** the stream of `InsightCard`s (newest first) → grouping by day.

```
Insights                                   [🔍 Search]  [ To review ]
──────────────────────────────────────────────────────────────────
TODAY ────────────────────────────────────────────────────────────
  ┌ InsightCard (feed density, §14.4) ────────────────────────────┐
  └────────────────────────────────────────────────────────────────┘
  ┌ InsightCard ───────────────────────────────────────────────────┐
  └────────────────────────────────────────────────────────────────┘
YESTERDAY ─────────────────────────────────────────────────────────
  ┌ InsightCard (reviewed → collapsed to one line + ✓) ────────────┐
  └────────────────────────────────────────────────────────────────┘
```
- **Day-grouped** timeline (`Today / Yesterday / {date}`) using `created_at` — turns the flat list into something that reads chronologically, "alive."
- Keep search + "To review" toggle (real, works today). **Do not add the severity filter** (§14.3).
- New cards on refetch get the entrance highlight (§17.3).

Copy: page subtitle "What changed across everything you watch — newest first." · toggle "Needs attention" → "To review" · empty (filtered) "Nothing matches — try clearing filters." · empty (none at all) → `AnalystEmptyState` "Your feed is quiet. PulseActalyst will surface updates here the instant a page you watch changes."

### 15.3 The one honest product-note (not per-card)

Because why-it-matters/impact/action aren't real yet, show a **single** dismissible line at the top of the feed (persisted in `localStorage`), never repeated per card:
> "Today PulseActalyst reports *what* changed. Deeper analysis — why it matters and what to do — is coming soon." `[ Got it ]`

This is the *only* place the product acknowledges the reserved fields. Everywhere else, absent = silent.

### 15.4 Monitors list (`app/monitors/page.tsx`)

**Hierarchy per card:** **1** favicon + company → **2** monitoring-health line → **3** activity pulse → **4** last update headline → **5** actions.

```
┌──────────────────────────────────────────┐
│ [◧] Acme Corp                     ● Active │  1
│     acme.com/pricing                       │
│ Watching normally · checked 2h ago         │  2  ← health line (derived, §below)
│  ╱╲__╱╲___╱╲  (ActivityPulse, 14d)         │  3
│ Last update: "Pro pricing raised 20%" · 4h │  4  ← newest insight headline for THIS source
│ [ Check now ]                          [↗] │  5
└──────────────────────────────────────────┘
```
- **Monitoring-health line** — derived, honest, frontend-only: `!enabled` → "Paused"; else if `last_checked_at` is stale relative to `schedule_minutes` → "Overdue for a check"; else if no insights in 14d (from `by_source_daily`) → "Watching · nothing new in 14 days"; else "Watching normally · checked {relTime}". Replaces the bare Active/Paused badge with an actual signal.
- **Last update** requires the newest insight per source. Today's Monitors page doesn't fetch summaries. Two honest options: (a) reuse `getInsightStats` (no per-source headline available → omit the headline, keep only the health + pulse), or (b) add a cheap `listInsights` call and map by source. **Recommend (b)** — still frontend-only, uses the existing endpoint. If you keep (a), drop line 4 rather than fake it.
- Keep "Add monitor" form and search unchanged (they work).

Copy: subtitle "Everything PulseActalyst is watching for you." · empty → `AnalystEmptyState` "Nothing being watched yet — point PulseActalyst at your first website." · button "Check now" stays (clear, works; Part I's "Look now" is optional).

### 15.5 Monitor detail — "The Intelligence Dossier" (`app/monitors/[id]/page.tsx`)

**Hierarchy:** **1** identity header (favicon, name, health, actions) → **2** at-a-glance strip → **3** full-width activity pulse → **4** the timeline → **5** de-emphasized admin sidebar.

```
← Back to monitors
[◧] Acme Corp                      ● Active   [ Check now ] [ Pause ]
    acme.com/pricing ↗ · Watching normally · checked 2h ago            1
┌ Updates (30d) ┐┌ Last update ┐┌ Checked ┐┌ Cadence ┐
│      6        ││    4h ago   ││  2h ago ││ Hourly  │                 2
└───────────────┘└─────────────┘└─────────┘└─────────┘
┌── ACTIVITY (30 days) ──────────────────────────────────────────┐
│    ╱╲      ╱╲╱╲        ╱╲   (ActivityPulse, area, full width)    │  3
└─────────────────────────────────────────────────────────────────┘
┌── INTELLIGENCE TIMELINE ─────────────┐  ┌ About ───────────┐
│  ┌ InsightCard (dossier) ──────────┐ │  │ Created   Jun 3  │
│  └──────────────────────────────────┘ │  │ Cadence   Hourly │  5
│  ┌ InsightCard ────────────────────┐ │  │ Alerts →         │
│  └──────────────────────────────────┘ │  └──────────────────┘
└───────────────────────────────────────┘                          4
```
- Fixes the existing bug where cadence prints `"{n} min"` for anything ≠ 60 (`monitors/[id]/page.tsx:216`) — use the shared `cadenceLabel()` from the Monitors page (lift to `lib/`).
- Timeline reuses `InsightCard` (dossier density) — same parser, same reserved region, no `FOLLOW UP` block.
- Header title stays the **company name** (already a good call), favicon added.

### 15.6 Onboarding — "Meet your analyst" (`app/onboarding/page.tsx`)

Keep the 3-step structure. Change the **scan step** and copy.

| Element | Before | After |
|---|---|---|
| H1 | "What do you want to track?" | keep |
| Template labels | "Competitor site / Industry blog / Own changelog" | "Track a competitor / Watch an industry source / Monitor your own site" |
| Static checklist | "Reading the page / Understanding structure / Preparing your first insight" (decorative, always shown) | Replace with `ThinkingState` that narrates **after submit**, during the real baseline queue: "Reading {domain}…" → "Learning what's on this page…" → "Set. We'll tell you the moment it changes." |
| Submit | "Start monitoring" | keep |
| Post-submit | toast + redirect to dashboard | redirect to dashboard where the hero shows `ThinkingState` until the first insight lands (the "reveal", Part I §8.3) |

Honest note: the checklist is decorative today; the `ThinkingState` is *also* not wired to real task progress unless you poll the baseline task (`use-source-check.ts` already has the polling primitive). If you don't poll, keep the narration **time-based and generic** ("Reading… / Learning…") — never claim a step "completed" that you didn't observe.

### 15.7 Trends (`app/trends/page.tsx`)

Mostly reskin: swap the two bar charts for `ActivityPulse`, reframe the KPI tiles (§18), keep "Breakdown by company" and "Busiest monitors" (real, good). Add the `deriveTrend()` "Activity level: Busy ↑ 40% vs. last week" line under the volume chart — real, frontend-only.

### 15.8 Notifications (`app/notifications/page.tsx`)

Honesty problem to fix: three of four cadence tiles ("Instant / Daily digest / Weekly digest") all write the same `"automatic"` value — the UI implies choices the backend doesn't have. **Frontend-only honest fix:** collapse to **two** truthful tiles — "Automatic (send as they arrive)" and "Manual review (send only what your team approves)". Drop Daily/Weekly until a real digest job exists. Keep recipients (real, works). Subtitle: "Decide when PulseActalyst reaches out, and who it reaches."

### 15.9 Login (`app/login/page.tsx`)

Minimal: add the ambient Signal waveform (low-opacity) behind the left marketing column so the entry screen carries the motif; keep the form. Copy already good.

## 16. Copy Voice — Master Rules

- Plain, specific, confident; numbers over adjectives ("6 updates", not "several").
- Banned in customer-facing copy: *record, run, task, source (as a DB row), discovered_url, baseline, strategy, Celery, summary (as a noun for the AI text — say "update"/"insight")*.
- The product is the subject that acts: "PulseActalyst is watching," "We took a first look." First person plural for the analyst voice, sparingly.
- Empty states are forward-looking, never apologetic ("is watching," not "no data").
- **Never** state or imply a signal we don't have (severity variety, confidence, why-it-matters) — see §12.

## 17. Motion & Interaction Spec

All animations gate on `@media (prefers-reduced-motion: reduce)` → reduce to opacity-only or none. Timings use the tokens in §13.

| # | Interaction | Spec |
|---|---|---|
| 17.1 | Dashboard ambient waveform | SVG path, `--dur-ambient` (8s) linear infinite horizontal drift of a duplicated path; opacity `0.06` light / `0.10` dark. Amplitude may scale to `deriveTrend().level` (Quiet/Normal/Busy → 0.6/1/1.4×) — real binding. Reduced-motion: static path, no drift. |
| 17.2 | Card / tile entrance | `opacity 0→1`, `translateY 6px→0`, `--dur-base`, `--ease-out`, `stagger 40ms` capped at 8 items. |
| 17.3 | New insight highlight | On refetch, cards whose `id` wasn't in the previous set: `--signal` left-edge glow fades `--dur-slow` then out. No layout shift. |
| 17.4 | Review collapse | Card height animates to the collapsed single-line + ✓ over `--dur-base`, `--ease-in-out`; content cross-fades. |
| 17.5 | ActivityPulse draw-in | `stroke-dashoffset` full→0 over `--dur-slow`, once, on first mount. Reduced-motion: rendered drawn. |
| 17.6 | ThinkingState sweep | A short gradient segment travels the pulse path, 1.6s loop; narration lines cross-fade every 2.5s. |
| 17.7 | Hover/press | Existing `hover:-translate-y-px hover:shadow-md` kept; standardize to `--dur-fast`. |

## 18. Metrics Reframing — Exact Tile Copy (all real or labeled)

| Tile | Value source (frontend-only) | Label | Note |
|---|---|---|---|
| Websites watched | `sources.filter(enabled).length` | "Websites watched" | real |
| Updates this week | insights where `created_at ≥ 7d` | "Updates this week" | real |
| To review | insights where `!reviewed_at` | "To review" | real (drop the `severity!=="low"` clause — all are medium, so it's a no-op that just looks arbitrary) |
| Time saved | `reviewedCount × 4min` | "Time saved" + `*Estimated` tag | tooltip: "Estimated from ~4 min saved per update you didn't have to check manually." Only labeled-estimate tile. |
| Activity level | `deriveTrend(daily)` | "Activity: Busy ↑40%" | real, frontend-computed |
| ~~AI confidence~~ | — | — | **omit** (no data; Tier 2) |

Drop "Avg. Time to Insight" from the customer dashboard — it's an operational/infra metric (Part I: reduce infra emphasis). Keep it on Trends if you like it, relabeled "Typical time to first insight".

## 19. Accessibility Checklist (applies to every screen)

- Every `ActivityPulse`/waveform: `role="img"` + descriptive `aria-label`; decorative ambient waveform `aria-hidden`.
- Color is never the sole carrier: severity badge has text; health line has words, not just a dot.
- `CompanyFavicon` fallback keeps an accessible name; no broken-image announcements.
- All new interactive elements keyboard-reachable, visible `:focus-visible` ring (`--ring`).
- Contrast: `--signal` stroke on `--card` and `--muted-foreground` meta text both ≥ 4.5:1 (verify the `--signal` lightness in dark mode — 55% passes on the `222 40% 11%` card).
- Respect `prefers-reduced-motion` on all of §17.
- Day-group headings in the feed are real `<h2>`/`<h3>` for screen-reader navigation, not styled divs.

## 20. Build Order (Tier-1 PR slicing)

1. **Foundations** — tokens (§13), `lib/parse-insight.ts` (lift + drop FOLLOW UP), `lib/cadence.ts`, `lib/trend.ts`, `components/intel/company-favicon.tsx`, `activity-pulse.tsx`, `analyst-empty-state.tsx`. *No visible change yet; unblocks everything.*
2. **Feed + InsightCard** (§15.2, §14.4) — highest "wow per line".
3. **Dashboard briefing** (§15.1) — greeting synthesis, hero, reframed metrics (§18), ActivityPulse trend.
4. **Monitors list + Dossier** (§15.4–15.5) — health line, favicons, ActivityPulse, cadence-bug fix.
5. **Onboarding + ThinkingState + empty states** (§15.6, §14.6).
6. **Notifications truthful-cadence fix + Trends reskin + Login waveform** (§15.7–15.9).
7. **Motion pass** (§17) last, behind reduced-motion.

Each slice is independently shippable and leaves the app working. None touches `backend/` or `mysignal/`. When Tier 2 (real severity + `confidence` + 6-part prompt) lands, only `InsightCard`'s reserved region and `ConfidenceSignal` mount — no screen re-layout, because the slots were designed in from the start.

## 21. What This Part II Deliberately Does *Not* Do

- No confidence UI, no severity-based sorting/filtering, no why-it-matters/impact/action text — all gated on Tier 2 (§12).
- No new charting/animation dependencies — everything is SVG/CSS.
- No changes to auth, routing, the admin console, or any backend endpoint.
- No fabricated or unlabeled metrics (§18, §11 guardrails).
