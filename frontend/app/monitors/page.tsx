"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Loader2, Play, Plus, Radar, Search, Trash2 } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { ActivityPulse } from "@/components/intel/activity-pulse";
import { CompanyFavicon } from "@/components/intel/company-favicon";
import { ConfirmDialog } from "@/components/intel/confirm-dialog";
import { EmptyState } from "@/components/empty-state";
import { Link } from "@/components/router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  baselineSource,
  createCompany,
  createSource,
  deleteCompany,
  getApiErrorMessage,
  getInsightStats,
  listCompanies,
  listInsights,
  listSources,
  type Source,
  type Summary,
} from "@/lib/api";
import { domainOf } from "@/lib/attribution";
import { clampMinutes, formatCadence } from "@/lib/cadence";
import { monitoringHealth } from "@/lib/monitor-health";
import { parseInsight } from "@/lib/parse-insight";
import { queryKeys } from "@/lib/query-keys";
import { useSourceCheck } from "@/lib/use-source-check";
import { formatRelativeTime, prettyUrl, truncate } from "@/lib/utils";

export default function MonitorsPage() {
  const queryClient = useQueryClient();
  const [query, setQuery] = React.useState("");
  const [companyName, setCompanyName] = React.useState("");
  const [url, setUrl] = React.useState("");
  const [scheduleMinutes, setScheduleMinutes] = React.useState("60");

  const companiesQuery = useQuery({ queryKey: queryKeys.companies, queryFn: listCompanies });
  const sourcesQuery = useQuery({ queryKey: queryKeys.sources, queryFn: listSources });
  const statsQuery = useQuery({ queryKey: queryKeys.insightStats(14), queryFn: () => getInsightStats(14) });
  const insightsQuery = useQuery({ queryKey: queryKeys.insights, queryFn: () => listInsights(100) });

  const companyById = new Map(
    (companiesQuery.data || []).map((company) => [company.id, company.name]),
  );

  // Newest insight per domain → surfaces each monitor's last important event.
  const latestByDomain = React.useMemo(() => {
    const map = new Map<string, Summary>();
    const sorted = (insightsQuery.data || [])
      .slice()
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    for (const insight of sorted) {
      const domain = domainOf(insight.discovered_url);
      if (domain && !map.has(domain)) map.set(domain, insight);
    }
    return map;
  }, [insightsQuery.data]);

  const addMutation = useMutation({
    mutationFn: async () => {
      const company = await createCompany({ name: companyName.trim() });
      const source = await createSource({
        company_id: company.id,
        url: url.trim(),
        strategy: "parent",
        trace_js: false,
        js_bundle_sources: [],
        enabled: true,
        schedule_minutes: clampMinutes(scheduleMinutes),
      });
      await baselineSource(source.id);
      return source;
    },
    onSuccess: () => {
      toast.success("Monitor added. First look queued.");
      setCompanyName("");
      setUrl("");
      setScheduleMinutes("60");
      queryClient.invalidateQueries({ queryKey: queryKeys.companies });
      queryClient.invalidateQueries({ queryKey: queryKeys.sources });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const sources = (sourcesQuery.data || []).filter((source) => {
    const company = companyById.get(source.company_id) || "";
    const haystack = `${source.url} ${company}`.toLowerCase();
    return haystack.includes(query.trim().toLowerCase());
  });

  function handleAdd(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    addMutation.mutate();
  }

  return (
    <div className="grid gap-6">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Monitors</h2>
          <p className="text-sm text-muted-foreground">
            Every site your sentinel is keeping watch over.
          </p>
        </div>
        <div className="relative w-full xl:w-80">
          <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted-foreground" />
          <Input
            className="pl-9"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search monitors"
          />
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="size-4" />
            Add monitor
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4 lg:grid-cols-[1fr_1.4fr_180px_auto] lg:items-end" onSubmit={handleAdd}>
            <div className="grid gap-2">
              <Label htmlFor="company-name">Tracked company</Label>
              <Input
                id="company-name"
                value={companyName}
                onChange={(event) => setCompanyName(event.target.value)}
                placeholder="Acme"
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="monitor-url">Website URL</Label>
              <Input
                id="monitor-url"
                type="url"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://example.com/news"
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="monitor-cadence">Check every (min)</Label>
              <Input
                id="monitor-cadence"
                type="number"
                min={1}
                step={1}
                value={scheduleMinutes}
                onChange={(event) => setScheduleMinutes(event.target.value)}
                placeholder="60"
              />
            </div>
            <Button disabled={addMutation.isPending}>
              <Plus />
              {addMutation.isPending ? "Adding" : "Add"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {sources.length === 0 && !sourcesQuery.isLoading ? (
        <EmptyState
          icon={Radar}
          title="Nothing under watch yet"
          description="Post your sentinel at its first website to start collecting updates."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {sources.map((source, i) => (
            <MonitorCard
              key={source.id}
              source={source}
              companyName={companyById.get(source.company_id) || "Tracked company"}
              activity={statsQuery.data?.by_source_daily[source.id]}
              lastUpdate={latestByDomain.get(domainOf(source.url) || "")}
              index={i}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function MonitorCard({
  source,
  companyName,
  activity,
  lastUpdate,
  index = 0,
}: {
  source: Source;
  companyName: string;
  activity: number[] | undefined;
  lastUpdate: Summary | undefined;
  index?: number;
}) {
  const queryClient = useQueryClient();
  const { check, isChecking } = useSourceCheck(source.id);
  const deleteMutation = useMutation({
    mutationFn: () => deleteCompany(source.company_id),
    onSuccess: () => {
      toast.success(`${companyName} removed.`);
      queryClient.invalidateQueries({ queryKey: queryKeys.companies });
      queryClient.invalidateQueries({ queryKey: queryKeys.sources });
      queryClient.invalidateQueries({ queryKey: queryKeys.insights });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
  const series = activity && activity.length ? activity : [];
  const hasActivity = series.some((count) => count > 0);
  const health = monitoringHealth(source, hasActivity);
  const lastHeadline = lastUpdate
    ? parseInsight(lastUpdate.summary).headline || lastUpdate.title || "Update detected"
    : null;

  return (
    <Card
      className="animate-enter transition hover:-translate-y-px hover:shadow-md"
      style={{ animationDelay: `${Math.min(index, 7) * 40}ms` }}
    >
      <CardContent className="grid gap-4 p-5 [&>*]:min-w-0">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <CompanyFavicon url={source.url} name={companyName} size={44} />
            <div className="min-w-0 flex-1">
              <Link
                href={`/monitors/${source.id}`}
                className="block truncate font-semibold text-foreground hover:text-primary"
              >
                {companyName}
              </Link>
              <div className="truncate text-sm text-muted-foreground">{prettyUrl(source.url)}</div>
            </div>
          </div>
          <Badge className="shrink-0" variant={source.enabled ? "success" : "secondary"}>
            {source.enabled ? "Active" : "Paused"}
          </Badge>
        </div>

        <div
          className={
            health.tone === "warn"
              ? "text-sm text-amber-700 dark:text-amber-500"
              : "text-sm text-muted-foreground"
          }
        >
          {health.label}
        </div>

        <div className="rounded-lg bg-secondary px-2 py-1">
          <ActivityPulse
            data={series}
            height={40}
            ariaLabel={`14-day activity for ${companyName}`}
            emptyLabel="No activity in the last 14 days"
          />
        </div>

        {lastHeadline ? (
          <div className="text-sm">
            <span className="text-muted-foreground">Last update: </span>
            <span className="font-medium">“{truncate(lastHeadline, 60)}”</span>
            <span className="text-muted-foreground"> · {formatRelativeTime(lastUpdate!.created_at)}</span>
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">No updates yet.</div>
        )}

        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Checks {formatCadence(source.schedule_minutes).toLowerCase()}</span>
        </div>

        <div className="flex gap-2">
          <Button className="flex-1" variant="outline" onClick={check} disabled={isChecking}>
            {isChecking ? <Loader2 className="animate-spin" /> : <Play />}
            {isChecking ? "Checking" : "Check now"}
          </Button>
          <Button asChild size="icon" variant="ghost">
            <a href={source.url} target="_blank" rel="noreferrer" aria-label="Open website">
              <ExternalLink />
            </a>
          </Button>
          <ConfirmDialog
            trigger={
              <Button
                size="icon"
                variant="ghost"
                aria-label={`Delete ${companyName}`}
                className="text-muted-foreground hover:text-destructive"
              >
                <Trash2 />
              </Button>
            }
            title={`Stop tracking ${companyName}?`}
            description="This removes the monitor and every update collected for it. This can't be undone."
            confirmLabel="Delete"
            destructive
            pending={deleteMutation.isPending}
            onConfirm={() => deleteMutation.mutate()}
          />
        </div>
      </CardContent>
    </Card>
  );
}
