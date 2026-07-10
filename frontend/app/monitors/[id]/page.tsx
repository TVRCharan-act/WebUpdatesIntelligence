"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Bell, ExternalLink, Loader2, Pause, Play, RefreshCw, Trash2 } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { ActivityPulse } from "@/components/intel/activity-pulse";
import { CompanyFavicon } from "@/components/intel/company-favicon";
import { ConfirmDialog } from "@/components/intel/confirm-dialog";
import { InsightCard } from "@/components/intel/insight-card";
import { WatchTypeBadge } from "@/components/intel/watch-type-badge";
import { Link, useParams, useRouter } from "@/components/router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  deleteCompany,
  getApiErrorMessage,
  getInsightStats,
  getSource,
  listCompanies,
  listSourceSummaries,
  updateInsightReview,
  updateSource,
} from "@/lib/api";
import { hostOf } from "@/lib/attribution";
import { clampMinutes, formatCadence } from "@/lib/cadence";
import { monitoringHealth } from "@/lib/monitor-health";
import { queryKeys } from "@/lib/query-keys";
import { useSourceCheck } from "@/lib/use-source-check";
import { formatDateTime, formatRelativeTime, prettyUrl } from "@/lib/utils";

export default function MonitorDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const sourceId = Number(params.id);
  const queryClient = useQueryClient();
  const [cadenceInput, setCadenceInput] = React.useState("");

  const sourceQuery = useQuery({
    queryKey: queryKeys.source(sourceId),
    queryFn: () => getSource(sourceId),
    enabled: Number.isFinite(sourceId),
  });
  const companiesQuery = useQuery({ queryKey: queryKeys.companies, queryFn: listCompanies });
  const summariesQuery = useQuery({
    queryKey: queryKeys.sourceSummaries(sourceId),
    queryFn: () => listSourceSummaries(sourceId),
    enabled: Number.isFinite(sourceId),
  });
  const statsQuery = useQuery({ queryKey: queryKeys.insightStats(30), queryFn: () => getInsightStats(30) });

  const { check, isChecking } = useSourceCheck(sourceId);
  const pauseMutation = useMutation({
    mutationFn: (enabled: boolean) => updateSource(sourceId, { enabled }),
    onSuccess: () => {
      toast.success("Monitor updated.");
      queryClient.invalidateQueries({ queryKey: queryKeys.source(sourceId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.sources });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
  const reviewMutation = useMutation({
    mutationFn: (id: number) => updateInsightReview(id, true),
    onSuccess: () => {
      toast.success("Insight marked reviewed.");
      queryClient.invalidateQueries({ queryKey: queryKeys.sourceSummaries(sourceId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.insights });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
  const cadenceMutation = useMutation({
    mutationFn: (minutes: number) => updateSource(sourceId, { schedule_minutes: minutes }),
    onSuccess: () => {
      toast.success("Check frequency updated.");
      queryClient.invalidateQueries({ queryKey: queryKeys.source(sourceId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.sources });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
  const deleteMutation = useMutation({
    mutationFn: (companyId: number) => deleteCompany(companyId),
    onSuccess: () => {
      toast.success("Monitor removed.");
      queryClient.invalidateQueries({ queryKey: queryKeys.sources });
      queryClient.invalidateQueries({ queryKey: queryKeys.companies });
      queryClient.invalidateQueries({ queryKey: queryKeys.insights });
      router.replace("/monitors");
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const source = sourceQuery.data;
  React.useEffect(() => {
    if (source) setCadenceInput(String(source.schedule_minutes));
  }, [source?.schedule_minutes]);
  const company = companiesQuery.data?.find((item) => item.id === source?.company_id);
  const companyName = company?.name || "Monitor";
  const summaries = React.useMemo(
    () =>
      (summariesQuery.data || [])
        .slice()
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
    [summariesQuery.data],
  );
  const activity = statsQuery.data?.by_source_daily[sourceId] || [];
  const hasActivity = activity.some((n) => n > 0);
  const health = source ? monitoringHealth(source, hasActivity) : null;
  const newest = summaries[0];

  const glance = [
    { label: "Updates", value: String(summaries.length) },
    { label: "Last update", value: newest ? formatRelativeTime(newest.created_at) : "—" },
    { label: "Checked", value: formatRelativeTime(source?.last_checked_at) },
    { label: "Cadence", value: formatCadence(source?.schedule_minutes) },
  ];

  return (
    <div className="grid gap-6">
      <div>
        <Button asChild variant="ghost" className="mb-3 px-0">
          <Link href="/monitors">
            <ArrowLeft />
            Back to monitors
          </Link>
        </Button>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex min-w-0 flex-1 items-center gap-4">
            {source ? <CompanyFavicon url={source.url} name={companyName} size={44} /> : null}
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="truncate text-3xl font-semibold">{companyName}</h2>
                {source ? (
                  <Badge variant={source.enabled ? "success" : "secondary"}>
                    {source.enabled ? "Active" : "Paused"}
                  </Badge>
                ) : null}
                {company ? <WatchTypeBadge type={company.watch_type} /> : null}
              </div>
              {source ? (
                <a
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 flex max-w-full items-center gap-1 text-sm text-primary"
                >
                  <span className="truncate">{prettyUrl(source.url)}</span>
                  <ExternalLink className="size-3 shrink-0" />
                </a>
              ) : null}
              {health ? (
                <div
                  className={
                    health.tone === "warn"
                      ? "mt-1 text-sm text-amber-700 dark:text-amber-500"
                      : "mt-1 text-sm text-muted-foreground"
                  }
                >
                  {health.label}
                </div>
              ) : null}
            </div>
          </div>
          {source ? (
            <div className="flex flex-wrap gap-2">
              <Button onClick={check} disabled={isChecking}>
                {isChecking ? <Loader2 className="animate-spin" /> : <RefreshCw />}
                {isChecking ? "Checking" : "Check now"}
              </Button>
              <Button variant="outline" onClick={() => pauseMutation.mutate(!source.enabled)}>
                {source.enabled ? <Pause /> : <Play />}
                {source.enabled ? "Pause" : "Resume"}
              </Button>
              <ConfirmDialog
                trigger={
                  <Button variant="outline" className="text-muted-foreground hover:text-destructive">
                    <Trash2 />
                    Delete
                  </Button>
                }
                title={`Stop tracking ${companyName}?`}
                description="This permanently removes this monitor and every update collected for it. This can't be undone."
                confirmLabel="Delete monitor"
                destructive
                pending={deleteMutation.isPending}
                onConfirm={() => deleteMutation.mutate(source.company_id)}
              />
            </div>
          ) : null}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {glance.map((item) => (
          <Card key={item.label}>
            <CardContent className="p-4">
              <div className="text-xs font-medium text-muted-foreground">{item.label}</div>
              <div className="mt-1 text-lg font-semibold">{item.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Activity over time</CardTitle>
        </CardHeader>
        <CardContent>
          <ActivityPulse
            data={activity}
            height={120}
            ariaLabel={`30-day activity for ${companyName}`}
            emptyLabel="No activity in the last 30 days"
          />
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
        <Card>
          <CardHeader>
            <CardTitle>Intelligence timeline</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            {summaries.map((summary) => (
              <InsightCard
                key={summary.id}
                insight={summary}
                companyName={companyName}
                sourceLabel={hostOf(summary.discovered_url) || undefined}
                onReview={summary.reviewed_at ? undefined : (id) => reviewMutation.mutate(id)}
                isReviewing={reviewMutation.isPending}
              />
            ))}
            {!summariesQuery.isLoading && summaries.length === 0 ? (
              <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
                No updates yet. Run a check now, or wait for the next scheduled scan.
              </div>
            ) : null}
          </CardContent>
        </Card>

        <aside className="grid content-start gap-6">
          <Card>
            <CardHeader>
              <CardTitle>About this monitor</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm">
              <div className="flex justify-between gap-3">
                <span className="text-muted-foreground">Created</span>
                <span>{formatDateTime(source?.created_at)}</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-muted-foreground">Checked</span>
                <span>{formatRelativeTime(source?.last_checked_at)}</span>
              </div>
              <div className="grid gap-2">
                <span className="text-muted-foreground">Check frequency</span>
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    min={1}
                    step={1}
                    value={cadenceInput}
                    onChange={(event) => setCadenceInput(event.target.value)}
                    className="h-8 w-24"
                    aria-label="Check every N minutes"
                  />
                  <span className="text-xs text-muted-foreground">min</span>
                  <Button
                    size="sm"
                    variant="outline"
                    className="ml-auto"
                    disabled={
                      cadenceMutation.isPending ||
                      clampMinutes(cadenceInput) === source?.schedule_minutes
                    }
                    onClick={() => cadenceMutation.mutate(clampMinutes(cadenceInput))}
                  >
                    Update
                  </Button>
                </div>
                <span className="text-xs text-muted-foreground">
                  Currently {formatCadence(source?.schedule_minutes)}.
                </span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bell className="size-4" />
                Alerts
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Who gets notified is managed on the Notifications page.
              <Button asChild variant="outline" className="mt-4 w-full">
                <Link href="/notifications">Open notifications</Link>
              </Button>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}
