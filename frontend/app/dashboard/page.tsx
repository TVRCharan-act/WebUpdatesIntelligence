"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Radar, Sparkles, TrendingDown, TrendingUp } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth-provider";
import { AmbientSignal } from "@/components/intel/ambient-signal";
import { AnalystEmptyState } from "@/components/intel/analyst-empty-state";
import { ActivityPulse } from "@/components/intel/activity-pulse";
import { InsightCard } from "@/components/intel/insight-card";
import { Link } from "@/components/router";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  getApiErrorMessage,
  getInsightStats,
  listCompanies,
  listInsights,
  listSources,
  updateInsightReview,
} from "@/lib/api";
import { makeAttributor, hostOf } from "@/lib/attribution";
import { queryKeys } from "@/lib/query-keys";
import { deriveTrend } from "@/lib/trend";
import { formatDurationShort } from "@/lib/utils";

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

const MINUTES_SAVED_PER_REVIEW = 4;

export default function CustomerDashboardPage() {
  const auth = useAuth();
  const queryClient = useQueryClient();

  const companiesQuery = useQuery({ queryKey: queryKeys.companies, queryFn: listCompanies });
  const sourcesQuery = useQuery({ queryKey: queryKeys.sources, queryFn: listSources });
  const insightsQuery = useQuery({ queryKey: queryKeys.insights, queryFn: () => listInsights(100) });
  const statsQuery = useQuery({ queryKey: queryKeys.insightStats(30), queryFn: () => getInsightStats(30) });

  const reviewMutation = useMutation({
    mutationFn: (id: number) => updateInsightReview(id, true),
    onSuccess: () => {
      toast.success("Insight marked reviewed.");
      queryClient.invalidateQueries({ queryKey: queryKeys.insights });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const sources = sourcesQuery.data || [];
  const companies = companiesQuery.data || [];
  const insights = React.useMemo(
    () =>
      (insightsQuery.data || [])
        .slice()
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
    [insightsQuery.data],
  );

  const attribute = React.useMemo(() => makeAttributor(sources, companies), [sources, companies]);
  const nameFor = (url: string) => {
    const { companyName, domain } = attribute(url);
    return companyName || domain || "Website update";
  };

  const weekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
  const newThisWeek = insights.filter((i) => new Date(i.created_at).getTime() >= weekAgo).length;
  const unreviewed = insights.filter((i) => !i.reviewed_at);
  const reviewedCount = insights.filter((i) => i.reviewed_at).length;
  const latest = unreviewed[0] || insights[0];
  const trend = deriveTrend(statsQuery.data?.daily);

  // "What's quiet" — monitors with no activity in the last 7 days of the window.
  const bySourceDaily = statsQuery.data?.by_source_daily || {};
  const quietCount = sources.filter((s) => {
    const series = bySourceDaily[s.id] || [];
    return series.slice(-7).reduce((sum, n) => sum + n, 0) === 0;
  }).length;

  const synthesis = (() => {
    if (!insights.length) return "Your sentinel is on watch. Your first briefing will appear here soon.";
    if (unreviewed.length === 0) return `You're all caught up — ${reviewedCount} updates reviewed.`;
    const newest = unreviewed[0];
    const rel = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
    const hrs = Math.round((Date.now() - new Date(newest.created_at).getTime()) / 3600000);
    const when = hrs < 24 ? rel.format(-hrs, "hour") : rel.format(-Math.round(hrs / 24), "day");
    const n = unreviewed.length;
    return `${n} update${n === 1 ? "" : "s"} ${n === 1 ? "is" : "are"} waiting for you — the newest is from ${nameFor(newest.discovered_url)}, ${when}.`;
  })();

  const metrics = [
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

  const trendDaily = (statsQuery.data?.daily || []).slice(-18).map((d) => d.count);
  const noSources = sources.length === 0 && !sourcesQuery.isLoading;

  return (
    <div className="grid gap-6">
      <section className="relative overflow-hidden rounded-xl border bg-[hsl(var(--briefing-bg))] p-6 shadow-sm">
        <AmbientSignal amplitude={trend.level === "Busy" ? 1.4 : trend.level === "Quiet" ? 0.6 : 1} />
        <div className="relative flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-2xl">
            <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-card/70 px-3 py-1 text-xs font-medium text-primary">
              <Sparkles className="size-3.5" />
              On watch
            </div>
            <h2 className="text-3xl font-semibold sm:text-4xl">
              {greeting()}, {auth.session?.name || "there"}.
            </h2>
            <p className="mt-2 text-muted-foreground">{synthesis}</p>
          </div>
          <Button asChild className="shrink-0">
            <Link href="/monitors">
              Track a website
              <ArrowRight />
            </Link>
          </Button>
        </div>
      </section>

      {noSources ? (
        <AnalystEmptyState
          title="Post your sentinel at its first website."
          body="Add one URL and your sentinel takes up watch — surfacing future changes as business-readable updates, usually within a minute."
          action={{ label: "Start onboarding", href: "/onboarding" }}
        />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {metrics.map((metric, i) => (
              <Card
                key={metric.label}
                className="animate-enter transition hover:-translate-y-px hover:shadow-md"
                style={{ animationDelay: `${i * 40}ms` }}
              >
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
                    {metric.label}
                    {metric.estimated ? (
                      <span
                        title={metric.tooltip}
                        className="cursor-help rounded bg-secondary px-1 text-[10px] uppercase tracking-wide"
                      >
                        est.
                      </span>
                    ) : null}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="font-mono text-3xl font-semibold tabular-nums">{metric.value}</div>
                </CardContent>
              </Card>
            ))}
          </div>

          <section className="grid gap-3">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              The Latest
            </h3>
            {latest ? (
              <InsightCard
                insight={latest}
                companyName={nameFor(latest.discovered_url)}
                sourceLabel={hostOf(latest.discovered_url) || undefined}
                onReview={latest.reviewed_at ? undefined : (id) => reviewMutation.mutate(id)}
                isReviewing={reviewMutation.isPending}
              />
            ) : (
              <AnalystEmptyState
                title="Standing watch for your first update"
                body="Your sentinel is reading the pages it guards. The moment one changes, the update appears here."
              />
            )}
          </section>

          <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
            <Card>
              <CardHeader>
                <CardTitle>Needs your review</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3">
                {unreviewed.slice(0, 4).map((insight) => (
                  <InsightCard
                    key={insight.id}
                    insight={insight}
                    companyName={nameFor(insight.discovered_url)}
                    sourceLabel={hostOf(insight.discovered_url) || undefined}
                    density="compact"
                    onReview={(id) => reviewMutation.mutate(id)}
                    isReviewing={reviewMutation.isPending}
                  />
                ))}
                {!unreviewed.length ? (
                  <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                    Nothing waiting — you've reviewed everything.
                  </div>
                ) : null}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0">
                <CardTitle>Activity</CardTitle>
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  {trend.direction === "up" ? (
                    <TrendingUp className="size-3.5 text-emerald-600" />
                  ) : trend.direction === "down" ? (
                    <TrendingDown className="size-3.5" />
                  ) : null}
                  {trend.level}
                  {trend.deltaPct != null ? ` · ${trend.deltaPct > 0 ? "+" : ""}${trend.deltaPct}%` : ""}
                </span>
              </CardHeader>
              <CardContent>
                <ActivityPulse
                  data={trendDaily}
                  height={96}
                  ariaLabel="Insight activity over the last 18 days"
                  emptyLabel="No activity yet"
                />
                <Button asChild variant="outline" className="mt-4 w-full">
                  <Link href="/trends">Open trends</Link>
                </Button>
              </CardContent>
            </Card>
          </div>

          {quietCount > 0 ? (
            <div className="flex items-center gap-2 rounded-xl border border-dashed px-4 py-3 text-sm text-muted-foreground">
              <Radar className="size-4 shrink-0" />
              {quietCount} monitor{quietCount === 1 ? "" : "s"} had nothing worth flagging this week — quiet is good news too.
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
