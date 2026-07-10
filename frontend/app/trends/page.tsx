"use client";

import { useQuery } from "@tanstack/react-query";
import { BarChart3, Clock3, Radar, TrendingDown, TrendingUp } from "lucide-react";

import { ActivityPulse } from "@/components/intel/activity-pulse";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getInsightStats, listCompanies } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { deriveTrend } from "@/lib/trend";
import { formatDurationShort, truncate } from "@/lib/utils";

export default function TrendsPage() {
  const companiesQuery = useQuery({ queryKey: queryKeys.companies, queryFn: listCompanies });
  const statsQuery = useQuery({ queryKey: queryKeys.insightStats(30), queryFn: () => getInsightStats(30) });

  const companies = companiesQuery.data || [];
  const stats = statsQuery.data;
  const daily = stats?.daily || [];
  const totalInsights = daily.reduce((sum, day) => sum + day.count, 0);
  const byCompanyMax = Math.max(1, ...(stats?.by_company || []).map((row) => row.count));
  const trend = deriveTrend(daily);

  const metrics = [
    { label: "Updates (30 days)", value: String(totalInsights), icon: TrendingUp },
    { label: "Companies watched", value: String(companies.length), icon: BarChart3 },
    { label: "Busiest monitor", value: String(stats?.busiest_sources[0]?.count ?? 0), icon: Radar },
    {
      label: "Typical time to first insight",
      value: formatDurationShort(stats?.avg_seconds_to_insight),
      icon: Clock3,
    },
  ];

  return (
    <div className="grid gap-6">
      <div>
        <h2 className="text-2xl font-semibold">Trends</h2>
        <p className="text-sm text-muted-foreground">
          How much is changing across everything you watch, and where.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <Card key={metric.label}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">{metric.label}</CardTitle>
                <Icon className="size-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="font-mono text-3xl font-semibold tabular-nums">{metric.value}</div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle>Update volume over time</CardTitle>
          <span className="flex items-center gap-1 text-sm text-muted-foreground">
            {trend.direction === "up" ? (
              <TrendingUp className="size-4 text-emerald-600" />
            ) : trend.direction === "down" ? (
              <TrendingDown className="size-4" />
            ) : null}
            {trend.level}
            {trend.deltaPct != null ? ` · ${trend.deltaPct > 0 ? "+" : ""}${trend.deltaPct}% vs last week` : ""}
          </span>
        </CardHeader>
        <CardContent>
          <ActivityPulse
            data={daily.map((day) => day.count)}
            height={272}
            ariaLabel="Update volume over the last 30 days"
            emptyLabel="No updates in the last 30 days."
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Breakdown by company</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3">
          {(stats?.by_company || []).map((row) => (
            <div key={row.company_id} className="grid gap-2">
              <div className="flex justify-between text-sm">
                <span className="font-medium">{row.company_name}</span>
                <span className="text-muted-foreground">
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
            <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
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
              <span className="truncate text-foreground">{truncate(row.url, 60)}</span>
              <span className="shrink-0 text-muted-foreground">
                {row.count} update{row.count === 1 ? "" : "s"}
              </span>
            </div>
          ))}
          {!statsQuery.isLoading && !(stats?.busiest_sources || []).length ? (
            <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
              No monitor activity in the last 30 days yet.
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
