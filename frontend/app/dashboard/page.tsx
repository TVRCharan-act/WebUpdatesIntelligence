"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  ArrowUpDown,
  Bell,
  Clock3,
  Radar,
  Search,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth-provider";
import { AnalystEmptyState } from "@/components/intel/analyst-empty-state";
import { ActivityPulse } from "@/components/intel/activity-pulse";
import { InsightCard } from "@/components/intel/insight-card";
import { PRIORITY_RANK } from "@/components/intel/priority-badge";
import {
  AddMonitorDialog,
  AlertsSection,
  MonitorDetailDialog,
  MonitorsSection,
} from "@/app/monitors/page";
import { useParams, usePathname, useRouter } from "@/components/router";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getApiErrorMessage,
  getInsightStats,
  listCompanies,
  listInsights,
  listSources,
  updateInsightReview,
  type Summary,
} from "@/lib/api";
import { type Attribution, hostOf, makeAttributor } from "@/lib/attribution";
import { queryKeys } from "@/lib/query-keys";
import { deriveTrend } from "@/lib/trend";
import { formatDurationShort, truncate } from "@/lib/utils";

// The whole app is one page. A briefing hero that says what needs you, the
// full update feed (search / sort / review filter) with a Pulse rail, then
// Monitors and Alerts stacked below as anchored sections — no route changes,
// just scroll (or the header's jump nav). Legacy routes (/monitors,
// /monitors/[id], /notifications, /settings, /onboarding, /insights, /trends)
// still deep-link straight to the right section / dialog.

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

const MINUTES_SAVED_PER_REVIEW = 4;

type SortKey =
  | "recent"
  | "oldest"
  | "priority"
  | "severity"
  | "confidence"
  | "company_new"
  | "company_old"
  | "company_az";

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "recent", label: "Newest update first" },
  { value: "oldest", label: "Oldest update first" },
  { value: "priority", label: "Company priority (high → low)" },
  { value: "severity", label: "Severity (high → low)" },
  { value: "confidence", label: "AI confidence (high → low)" },
  { value: "company_new", label: "Company added (newest)" },
  { value: "company_old", label: "Company added (earliest)" },
  { value: "company_az", label: "Company name (A → Z)" },
];

const LEVEL_RANK: Record<"low" | "medium" | "high", number> = { high: 3, medium: 2, low: 1 };

interface Enriched {
  insight: Summary;
  attr: Attribution;
}

function timeOf(iso: string | null | undefined): number {
  return iso ? new Date(iso).getTime() : 0;
}

function dayLabel(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diffDays = Math.round((startOf(now) - startOf(d)) / 86400000);
  if (diffDays <= 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(d);
}

function comparator(sort: SortKey): (a: Enriched, b: Enriched) => number {
  const recent = (a: Enriched, b: Enriched) =>
    timeOf(b.insight.created_at) - timeOf(a.insight.created_at);
  switch (sort) {
    case "oldest":
      return (a, b) => timeOf(a.insight.created_at) - timeOf(b.insight.created_at);
    case "priority":
      return (a, b) =>
        PRIORITY_RANK[b.attr.company?.priority ?? "medium"] -
          PRIORITY_RANK[a.attr.company?.priority ?? "medium"] || recent(a, b);
    case "severity":
      return (a, b) =>
        LEVEL_RANK[b.insight.severity] - LEVEL_RANK[a.insight.severity] || recent(a, b);
    case "confidence":
      return (a, b) =>
        LEVEL_RANK[b.insight.confidence] - LEVEL_RANK[a.insight.confidence] || recent(a, b);
    case "company_new":
      return (a, b) =>
        timeOf(b.attr.company?.created_at) - timeOf(a.attr.company?.created_at) || recent(a, b);
    case "company_old":
      return (a, b) =>
        (timeOf(a.attr.company?.created_at) || Infinity) -
          (timeOf(b.attr.company?.created_at) || Infinity) || recent(a, b);
    case "company_az":
      return (a, b) =>
        (a.attr.companyName || a.attr.domain || "~").localeCompare(
          b.attr.companyName || b.attr.domain || "~",
        ) || recent(a, b);
    default:
      return recent;
  }
}

const ANCHOR_FOR_LEGACY_PATH: Record<string, string> = {
  "/insights": "overview",
  "/trends": "overview",
  "/monitors": "monitors",
  "/onboarding": "monitors",
  "/notifications": "alerts",
};

function anchorForPath(pathname: string): string | null {
  if (pathname in ANCHOR_FOR_LEGACY_PATH) return ANCHOR_FOR_LEGACY_PATH[pathname];
  if (pathname.startsWith("/monitors/")) return "monitors";
  return null;
}

export default function HomePage() {
  const auth = useAuth();
  const queryClient = useQueryClient();
  const pathname = usePathname();
  const router = useRouter();
  const [search, setSearch] = React.useState("");
  const [toReviewOnly, setToReviewOnly] = React.useState(false);
  const [sortBy, setSortBy] = React.useState<SortKey>("recent");
  const [companyFilter, setCompanyFilter] = React.useState<string>("all");

  // Legacy deep links land on this same page; on first mount, jump straight
  // to the section (and dialog) they used to open on their own route.
  const initialPathname = React.useRef(pathname).current;
  React.useEffect(() => {
    const anchor = anchorForPath(initialPathname);
    if (!anchor) return;
    requestAnimationFrame(() => {
      document.getElementById(anchor)?.scrollIntoView({ block: "start" });
    });
  }, [initialPathname]);

  const { id: monitorIdParam } = useParams<{ id: string }>();
  const selectedMonitorId = monitorIdParam ? Number(monitorIdParam) : null;

  const [addOpen, setAddOpen] = React.useState(false);
  const addDialogOpen = addOpen || pathname === "/onboarding";

  function closeAddDialog() {
    setAddOpen(false);
    if (pathname === "/onboarding") router.replace("/dashboard");
  }

  function openTrackWebsite() {
    setAddOpen(true);
    requestAnimationFrame(() => {
      document.getElementById("monitors")?.scrollIntoView({ block: "start" });
    });
  }

  const companiesQuery = useQuery({ queryKey: queryKeys.companies, queryFn: listCompanies });
  const sourcesQuery = useQuery({ queryKey: queryKeys.sources, queryFn: listSources });
  const insightsQuery = useQuery({ queryKey: queryKeys.insights, queryFn: () => listInsights(200) });
  const statsQuery = useQuery({ queryKey: queryKeys.insightStats(30), queryFn: () => getInsightStats(30) });

  const reviewMutation = useMutation({
    mutationFn: (id: string) => updateInsightReview(id, true),
    onSuccess: () => {
      toast.success("Insight marked reviewed.");
      queryClient.invalidateQueries({ queryKey: queryKeys.insights });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const sources = sourcesQuery.data || [];
  const companies = companiesQuery.data || [];
  const stats = statsQuery.data;
  const insights = React.useMemo(
    () =>
      (insightsQuery.data || [])
        .slice()
        .sort((a, b) => timeOf(b.created_at) - timeOf(a.created_at)),
    [insightsQuery.data],
  );

  const attribute = React.useMemo(() => makeAttributor(sources, companies), [sources, companies]);
  const nameFor = (url: string) => {
    const { companyName, domain } = attribute(url);
    return companyName || domain || "Website update";
  };

  const weekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
  const newThisWeek = insights.filter((i) => timeOf(i.created_at) >= weekAgo).length;
  const unreviewed = insights.filter((i) => !i.reviewed_at);
  const reviewedCount = insights.filter((i) => i.reviewed_at).length;
  const trend = deriveTrend(stats?.daily);

  // "What's quiet" — monitors with no activity in the last 7 days of the window.
  const bySourceDaily = stats?.by_source_daily || {};
  const quietCount = sources.filter((s) => {
    const series = bySourceDaily[s.id] || [];
    return series.slice(-7).reduce((sum, n) => sum + n, 0) === 0;
  }).length;

  const synthesis = (() => {
    if (!insights.length) return "Your sentinel is on watch. Your first briefing will appear here soon.";
    if (unreviewed.length === 0) return `You're all caught up — ${reviewedCount} updates reviewed.`;
    const newest = unreviewed[0];
    const rel = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
    const hrs = Math.round((Date.now() - timeOf(newest.created_at)) / 3600000);
    const when = hrs < 24 ? rel.format(-hrs, "hour") : rel.format(-Math.round(hrs / 24), "day");
    const n = unreviewed.length;
    return `${n} update${n === 1 ? "" : "s"} ${n === 1 ? "is" : "are"} waiting for you — the newest is from ${nameFor(newest.discovered_url)}, ${when}.`;
  })();

  const heroStats = [
    { label: "Websites watched", value: String(sources.filter((s) => s.enabled).length) },
    { label: "Updates this week", value: String(newThisWeek) },
    { label: "To review", value: String(unreviewed.length) },
    {
      label: "Time saved",
      value: formatDurationShort(reviewedCount * MINUTES_SAVED_PER_REVIEW * 60),
      estimated: true,
      tooltip: `Estimated from ~${MINUTES_SAVED_PER_REVIEW} min saved per update you didn't have to check manually (${reviewedCount} reviewed).`,
    },
  ];

  // ---- Feed: search / sort / review filter, day grouping, new-item highlight ----
  const term = search.trim().toLowerCase();
  const enriched: Enriched[] = React.useMemo(() => {
    return insights
      .filter((insight) => {
        const text = `${insight.title || ""} ${insight.summary} ${insight.discovered_url}`.toLowerCase();
        const matchesSearch = text.includes(term);
        const matchesReview = !toReviewOnly || !insight.reviewed_at;
        return matchesSearch && matchesReview;
      })
      .map((insight) => ({ insight, attr: attribute(insight.discovered_url) }))
      .filter(({ attr }) => companyFilter === "all" || String(attr.company?.id ?? "") === companyFilter)
      .sort(comparator(sortBy));
  }, [insights, term, toReviewOnly, sortBy, attribute, companyFilter]);

  // Highlight insights genuinely new since the last fetch (tracked on full set).
  const allIds = React.useMemo(() => insights.map((i) => i.id), [insights]);
  const prevIdsRef = React.useRef<Set<string> | null>(null);
  const highlightIds = React.useMemo(() => {
    const prev = prevIdsRef.current;
    if (!prev) return new Set<string>();
    return new Set(allIds.filter((id) => !prev.has(id)));
  }, [allIds]);
  React.useEffect(() => {
    prevIdsRef.current = new Set(allIds);
  }, [allIds]);

  // Group by day only for the time-based sorts; otherwise a single flat list.
  const grouped = sortBy === "recent" || sortBy === "oldest";
  const sections = React.useMemo(() => {
    if (!grouped) return [["", enriched]] as [string, Enriched[]][];
    const map = new Map<string, Enriched[]>();
    for (const item of enriched) {
      const label = dayLabel(item.insight.created_at);
      const bucket = map.get(label);
      if (bucket) bucket.push(item);
      else map.set(label, [item]);
    }
    return Array.from(map.entries());
  }, [enriched, grouped]);

  // ---- Pulse rail (all of the old Trends page) ----
  const daily = stats?.daily || [];
  const totalInsights30 = daily.reduce((sum, day) => sum + day.count, 0);
  const byCompanyMax = Math.max(1, ...(stats?.by_company || []).map((row) => row.count));

  const noSources = sources.length === 0 && !sourcesQuery.isLoading;
  const hasAnyInsights = insights.length > 0;

  return (
    <div className="grid gap-8 pb-10">
      <section id="overview" className="grid scroll-mt-24 gap-5">
      <section className="rounded-2xl border bg-[hsl(var(--briefing-bg))] p-5 shadow-sm sm:p-6">
        <div className="grid gap-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-2xl">
              <div className="mb-2 inline-flex items-center gap-2 rounded-full border bg-card px-3 py-1 text-xs font-medium text-muted-foreground">
                <span className="live-dot size-1.5" />
                On watch
              </div>
              <h2 className="text-2xl font-semibold sm:text-3xl">
                {greeting()}, {auth.session?.name || "there"}.
              </h2>
              <p className="mt-2 text-muted-foreground">{synthesis}</p>
            </div>
            <Button className="shrink-0" onClick={openTrackWebsite}>
              Track a website
              <ArrowRight />
            </Button>
          </div>

          {!noSources ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {heroStats.map((stat) => (
                <div
                  key={stat.label}
                  className="rounded-xl border bg-card px-4 py-3"
                >
                  <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                    {stat.label}
                    {stat.estimated ? (
                      <span
                        title={stat.tooltip}
                        className="cursor-help rounded bg-secondary px-1 text-[10px] uppercase tracking-wide"
                      >
                        est.
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-1 text-2xl font-semibold tabular-nums sm:text-3xl">
                    {stat.value}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </section>

      {noSources ? (
        <AnalystEmptyState
          title="Post your sentinel at its first website."
          body="Add one URL and your sentinel takes up watch — surfacing future changes as business-readable updates, usually within a minute."
          action={{ label: "Track your first website", onClick: openTrackWebsite }}
        />
      ) : (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_300px] xl:grid-cols-[minmax(0,1fr)_340px]">
          <section className="flex min-w-0 flex-col gap-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted-foreground" />
                <Input
                  className="pl-9"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search updates"
                />
              </div>
              {companies.length > 1 ? (
                <Select value={companyFilter} onValueChange={setCompanyFilter}>
                  <SelectTrigger className="sm:w-48" aria-label="Filter by company">
                    <SelectValue placeholder="All companies" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All companies</SelectItem>
                    {companies.map((company) => (
                      <SelectItem key={company.id} value={String(company.id)}>
                        {company.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : null}
              <Select value={sortBy} onValueChange={(v) => setSortBy(v as SortKey)}>
                <SelectTrigger className="sm:w-56" aria-label="Sort updates">
                  <ArrowUpDown className="size-4 text-muted-foreground" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SORT_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant={toReviewOnly ? "default" : "outline"}
                onClick={() => setToReviewOnly((value) => !value)}
              >
                To review
                {unreviewed.length ? (
                  <span className="ml-1 rounded-full bg-card/25 px-1.5 text-xs tabular-nums">
                    {unreviewed.length}
                  </span>
                ) : null}
              </Button>
            </div>

            {insightsQuery.isLoading ? (
              <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
                Loading updates…
              </div>
            ) : !hasAnyInsights ? (
              <AnalystEmptyState
                title="Standing watch for your first update"
                body="Your sentinel is reading the pages it guards. The moment one changes, the update appears here."
              />
            ) : !enriched.length ? (
              <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
                Nothing matches — try clearing your filters.
              </div>
            ) : (
              <div className="flex flex-col gap-6">
                {sections.map(([label, items]) => (
                  <section key={label || "all"} className="flex flex-col gap-3">
                    {label ? (
                      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        {label}
                      </h3>
                    ) : null}
                    {items.map(({ insight, attr }, i) => (
                      <InsightCard
                        key={insight.id}
                        insight={insight}
                        companyName={attr.companyName || attr.domain || "Website update"}
                        sourceLabel={hostOf(insight.discovered_url) || undefined}
                        priority={attr.company?.priority}
                        onReview={(id) => reviewMutation.mutate(id)}
                        isReviewing={reviewMutation.isPending}
                        index={i}
                        highlight={highlightIds.has(insight.id)}
                      />
                    ))}
                  </section>
                ))}
              </div>
            )}
          </section>

          <aside className="flex min-w-0 flex-col gap-5">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0">
                <CardTitle className="flex items-center gap-2">
                  <span className="live-dot size-1.5" />
                  Pulse
                </CardTitle>
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  {trend.direction === "up" ? (
                    <TrendingUp className="size-3.5 text-foreground" />
                  ) : trend.direction === "down" ? (
                    <TrendingDown className="size-3.5" />
                  ) : null}
                  {trend.level}
                  {trend.deltaPct != null
                    ? ` · ${trend.deltaPct > 0 ? "+" : ""}${trend.deltaPct}% vs last week`
                    : ""}
                </span>
              </CardHeader>
              <CardContent className="grid gap-4">
                <ActivityPulse
                  data={daily.map((day) => day.count)}
                  height={120}
                  ariaLabel="Update volume over the last 30 days"
                  emptyLabel="No updates in the last 30 days."
                />
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="rounded-lg bg-secondary px-3 py-2">
                    <div className="text-xs text-muted-foreground">Updates (30 days)</div>
                    <div className="text-lg font-semibold tabular-nums">{totalInsights30}</div>
                  </div>
                  <div className="rounded-lg bg-secondary px-3 py-2">
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Clock3 className="size-3" />
                      First insight in
                    </div>
                    <div className="text-lg font-semibold tabular-nums">
                      {formatDurationShort(stats?.avg_seconds_to_insight)}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Where it's happening</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3">
                {(stats?.by_company || []).map((row) => (
                  <div key={row.company_id} className="grid gap-1.5">
                    <div className="flex justify-between gap-3 text-sm">
                      <span className="truncate font-medium">{row.company_name}</span>
                      <span className="shrink-0 text-muted-foreground">
                        {row.count} update{row.count === 1 ? "" : "s"}
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-secondary">
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{ width: `${Math.max(4, (row.count / byCompanyMax) * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
                {!statsQuery.isLoading && !(stats?.by_company || []).length ? (
                  <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                    Add monitors to see which companies are changing most.
                  </div>
                ) : null}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Busiest monitors</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3">
                {(stats?.busiest_sources || []).map((row) => (
                  <div key={row.source_id} className="flex items-center justify-between gap-3 text-sm">
                    <span className="truncate text-foreground">{truncate(row.url, 48)}</span>
                    <span className="shrink-0 text-muted-foreground">
                      {row.count} update{row.count === 1 ? "" : "s"}
                    </span>
                  </div>
                ))}
                {!statsQuery.isLoading && !(stats?.busiest_sources || []).length ? (
                  <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                    No monitor activity in the last 30 days yet.
                  </div>
                ) : null}
              </CardContent>
            </Card>

            {quietCount > 0 ? (
              <div className="flex items-center gap-2 rounded-xl border border-dashed px-4 py-3 text-sm text-muted-foreground">
                <Radar className="size-4 shrink-0" />
                {quietCount} monitor{quietCount === 1 ? "" : "s"} had nothing worth flagging this week —
                quiet is good news too.
              </div>
            ) : null}
          </aside>
        </div>
      )}
      </section>

      <section id="monitors" className="grid scroll-mt-24 gap-4 border-t pt-6">
        <SectionHeading
          icon={Radar}
          title="Monitors"
          description="Every website your sentinel is watching, at a glance."
        />
        <MonitorsSection onAdd={() => setAddOpen(true)} />
      </section>

      <section id="alerts" className="grid scroll-mt-24 gap-4 border-t pt-6">
        <SectionHeading
          icon={Bell}
          title="Alerts"
          description="When your sentinel tells you, and who it tells."
        />
        <AlertsSection />
      </section>

      <AddMonitorDialog open={addDialogOpen} onClose={closeAddDialog} />

      {selectedMonitorId != null && Number.isFinite(selectedMonitorId) ? (
        <MonitorDetailDialog sourceId={selectedMonitorId} onClose={() => router.push("/dashboard")} />
      ) : null}
    </div>
  );
}

function SectionHeading({
  icon: Icon,
  title,
  description,
}: {
  icon: React.ElementType;
  title: string;
  description: string;
}) {
  return (
    <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-2">
        <span className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="size-4" />
        </span>
        <h2 className="text-xl font-semibold">{title}</h2>
      </div>
      <p className="text-sm text-muted-foreground sm:text-right">{description}</p>
    </div>
  );
}
