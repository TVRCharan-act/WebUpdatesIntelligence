"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  ClipboardCheck,
  ExternalLink,
  Loader2,
  Mail,
  MailWarning,
  Pause,
  Play,
  Plus,
  Radar,
  RefreshCw,
  Search,
  Trash2,
  Zap,
} from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { ActivityPulse } from "@/components/intel/activity-pulse";
import { CadenceField } from "@/components/intel/cadence-field";
import { CompanyFavicon } from "@/components/intel/company-favicon";
import { ConfirmDialog } from "@/components/intel/confirm-dialog";
import { InsightCard } from "@/components/intel/insight-card";
import { PRIORITY_OPTIONS, PriorityBadge } from "@/components/intel/priority-badge";
import { ThinkingState } from "@/components/intel/thinking-state";
import { EmptyState } from "@/components/empty-state";
import { Link } from "@/components/router";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  baselineSource,
  createCompany,
  createCompanyRecipient,
  createSource,
  deleteCompany,
  deleteNotificationRecipient,
  getApiErrorMessage,
  getEmailNotificationSettings,
  getInsightStats,
  getSesStatus,
  getSource,
  getTaskStatus,
  listCompanies,
  listCompanyRecipients,
  listInsights,
  listSources,
  listSourceSummaries,
  sendEmailSummary,
  taskHasFailedResult,
  updateEmailNotificationSettings,
  updateInsightReview,
  updateSource,
  type Priority,
  type Source,
  type Summary,
} from "@/lib/api";
import { domainOf, hostOf } from "@/lib/attribution";
import { formatCadence, minutesToParts, toMinutes, type CadenceUnit } from "@/lib/cadence";
import { monitoringHealth } from "@/lib/monitor-health";
import { parseInsight } from "@/lib/parse-insight";
import { queryKeys } from "@/lib/query-keys";
import { useSourceCheck } from "@/lib/use-source-check";
import {
  cn,
  formatDateTime,
  formatRelativeTime,
  prettyUrl,
  truncate,
} from "@/lib/utils";

// This module holds every building block for what your sentinel watches and
// how it alerts you: the Monitors grid (with an add dialog that doubles as
// onboarding), a per-monitor dossier dialog, and an Alerts section. They're
// composed together on the single unified dashboard page
// (app/dashboard/page.tsx) as stacked, anchored sections instead of separate
// routed tabs.

// ---------------------------------------------------------------------------
// Monitors section — the grid of watched sites.
// ---------------------------------------------------------------------------

export function MonitorsSection({ onAdd }: { onAdd: () => void }) {
  const [query, setQuery] = React.useState("");

  const companiesQuery = useQuery({ queryKey: queryKeys.companies, queryFn: listCompanies });
  const sourcesQuery = useQuery({ queryKey: queryKeys.sources, queryFn: listSources });
  const statsQuery = useQuery({ queryKey: queryKeys.insightStats(14), queryFn: () => getInsightStats(14) });
  const insightsQuery = useQuery({ queryKey: queryKeys.insights, queryFn: () => listInsights(100) });

  const companyById = new Map(
    (companiesQuery.data || []).map((company) => [company.id, company.name]),
  );
  const priorityById = new Map(
    (companiesQuery.data || []).map((company) => [company.id, company.priority]),
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

  const sources = (sourcesQuery.data || []).filter((source) => {
    const company = companyById.get(source.company_id) || "";
    const haystack = `${source.url} ${company}`.toLowerCase();
    return haystack.includes(query.trim().toLowerCase());
  });

  return (
    <div className="grid gap-4">
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted-foreground" />
          <Input
            className="pl-9"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search monitors"
          />
        </div>
        <Button onClick={onAdd}>
          <Plus />
          Track a website
        </Button>
      </div>

      {sources.length === 0 && !sourcesQuery.isLoading ? (
        query ? (
          <EmptyState
            icon={Search}
            title="No monitors match"
            description="Try a different search, or track a new website."
          />
        ) : (
          <Card>
            <CardContent className="flex flex-col items-center justify-center gap-3 py-14 text-center">
              <Radar className="size-8 text-signal" />
              <div className="text-lg font-semibold">Nothing under watch yet</div>
              <p className="max-w-md text-sm text-muted-foreground">
                Post your sentinel at its first website — it takes up watch and reports future
                changes as business-readable updates.
              </p>
              <Button className="mt-2" onClick={onAdd}>
                <Plus />
                Track your first website
              </Button>
            </CardContent>
          </Card>
        )
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {sources.map((source, i) => (
            <MonitorCard
              key={source.id}
              source={source}
              companyName={companyById.get(source.company_id) || "Tracked company"}
              priority={priorityById.get(source.company_id) || "medium"}
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
  priority,
  activity,
  lastUpdate,
  index = 0,
}: {
  source: Source;
  companyName: string;
  priority: Priority;
  activity: number[] | undefined;
  lastUpdate: Summary | undefined;
  index?: number;
}) {
  const queryClient = useQueryClient();
  const { check, isChecking, progress } = useSourceCheck(source.id);
  const monitoringMutation = useMutation({
    mutationFn: (enabled: boolean) => updateSource(source.id, { enabled }),
    onSuccess: (updatedSource) => {
      toast.success(updatedSource.enabled ? "Monitoring resumed." : "Monitoring paused.");
      queryClient.invalidateQueries({ queryKey: queryKeys.sources });
      queryClient.invalidateQueries({ queryKey: queryKeys.monitorStatus });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
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
      className="animate-enter"
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
          <Badge className="shrink-0 gap-1.5" variant={source.enabled ? "success" : "secondary"}>
            {source.enabled ? <span className="live-dot size-1.5" /> : null}
            {source.enabled ? "Active" : "Paused"}
          </Badge>
        </div>

        <div
          className={
            health.tone === "warn"
              ? "text-sm font-medium text-foreground"
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
            emptyLabel="No relevant updates in the last 14 days"
          />
        </div>

        {lastHeadline ? (
          <div className="text-sm">
            <span className="text-muted-foreground">Last update: </span>
            <span className="font-medium">“{truncate(lastHeadline, 60)}”</span>
            <span className="text-muted-foreground"> · {formatRelativeTime(lastUpdate!.created_at)}</span>
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">No relevant business updates yet.</div>
        )}

        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <PriorityBadge priority={priority} />
          <span>Checks {formatCadence(source.schedule_minutes).toLowerCase()}</span>
        </div>

        <div className="flex gap-2">
          <Button
            className="flex-1"
            variant="outline"
            onClick={check}
            disabled={!source.enabled || isChecking}
            title={source.enabled ? "Check now" : "Resume monitoring to run a check"}
          >
            {isChecking ? <Loader2 className="animate-spin" /> : <Play />}
            {isChecking ? progress?.message || "Checking" : "Check now"}
          </Button>
          <Button
            size="icon"
            variant={source.enabled ? "outline" : "secondary"}
            aria-label={source.enabled ? `Pause ${companyName}` : `Resume ${companyName}`}
            title={source.enabled ? "Pause monitoring" : "Resume monitoring"}
            disabled={monitoringMutation.isPending}
            onClick={() => monitoringMutation.mutate(!source.enabled)}
          >
            {source.enabled ? <Pause /> : <Play />}
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
        {isChecking && progress ? (
          <div className="text-xs text-muted-foreground">
            {progress.current !== null && progress.total !== null
              ? `${progress.current}/${progress.total} · `
              : null}
            {progress.message}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Add-monitor dialog — also serves as onboarding (/onboarding opens it).
// ---------------------------------------------------------------------------

export function AddMonitorDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [companyName, setCompanyName] = React.useState("");
  const [url, setUrl] = React.useState("");
  const [priority, setPriority] = React.useState<Priority>("medium");
  const [cadenceValue, setCadenceValue] = React.useState("1");
  const [cadenceUnit, setCadenceUnit] = React.useState<CadenceUnit>("hour");
  const [showAdvanced, setShowAdvanced] = React.useState(false);
  const [baselineTaskId, setBaselineTaskId] = React.useState<string | null>(null);

  const baselineTaskQuery = useQuery({
    queryKey: baselineTaskId ? queryKeys.task(baselineTaskId) : queryKeys.task("idle"),
    queryFn: () => getTaskStatus(baselineTaskId as string),
    enabled: Boolean(baselineTaskId),
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      return state && ["succeeded", "partially_succeeded", "failed", "cancelled"].includes(state)
        ? false
        : 1000;
    },
  });

  const addMutation = useMutation({
    mutationFn: async () => {
      const company = await createCompany({ name: companyName.trim(), priority });
      const source = await createSource({
        company_id: company.id,
        url: url.trim(),
        strategy: "parent",
        trace_js: false,
        js_bundle_sources: [],
        enabled: true,
        schedule_minutes: toMinutes(cadenceValue, cadenceUnit),
      });
      const task = await baselineSource(source.id);
      return { source, task };
    },
    onSuccess: ({ task }) => {
      setBaselineTaskId(task.task_id);
      setCompanyName("");
      setPriority("medium");
      setCadenceValue("1");
      setCadenceUnit("hour");
      setShowAdvanced(false);
      queryClient.invalidateQueries({ queryKey: queryKeys.companies });
      queryClient.invalidateQueries({ queryKey: queryKeys.sources });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  React.useEffect(() => {
    const task = baselineTaskQuery.data;
    const state = task?.state;
    if (!baselineTaskId || !task || !state || !["succeeded", "partially_succeeded", "failed", "cancelled"].includes(state)) {
      return;
    }

    const failed = taskHasFailedResult(task);
    toast[failed ? "error" : "success"](
      failed ? "Your first check failed. You can try again from the monitor card." : "Your monitor is live and on watch.",
    );
    setBaselineTaskId(null);
    setUrl("");
    queryClient.invalidateQueries({ queryKey: queryKeys.companies });
    queryClient.invalidateQueries({ queryKey: queryKeys.sources });
    queryClient.invalidateQueries({ queryKey: queryKeys.insights });
    onClose();
  }, [baselineTaskId, baselineTaskQuery.data, onClose, queryClient]);

  const domain = hostOf(url) || "the page";
  const isSettingUp = addMutation.isPending || Boolean(baselineTaskId);
  const scanLines = [
    `Taking up watch over ${domain}…`,
    "Learning what to look out for…",
    "Your sentinel is reporting for duty…",
  ];

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !isSettingUp) onClose();
      }}
    >
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Track a website</DialogTitle>
          <DialogDescription>
            Name what you're tracking, add one URL, and set how important it is. Your sentinel
            takes up watch and alerts you the moment anything changes.
          </DialogDescription>
        </DialogHeader>
        {isSettingUp ? (
          <div className="grid gap-2">
            <ThinkingState lines={scanLines} ariaLabel="Setting up your monitor" />
            <p className="text-center text-xs text-muted-foreground">
              {baselineTaskQuery.data?.progress?.message || "Starting your first check…"}
            </p>
          </div>
        ) : (
          <form
            className="grid gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              addMutation.mutate();
            }}
          >
            <div className="grid gap-2">
              <Label htmlFor="add-company">What should we call this?</Label>
              <Input
                id="add-company"
                value={companyName}
                onChange={(event) => setCompanyName(event.target.value)}
                placeholder="Acme"
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="add-url">Website URL</Label>
              <Input
                id="add-url"
                type="url"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://example.com/pricing"
                required
              />
            </div>
            {showAdvanced ? (
              <>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="grid gap-2">
                    <Label htmlFor="add-priority">Priority</Label>
                    <Select value={priority} onValueChange={(v) => setPriority(v as Priority)}>
                      <SelectTrigger id="add-priority">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {PRIORITY_OPTIONS.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="add-cadence">Check every</Label>
                    <CadenceField
                      id="add-cadence"
                      value={cadenceValue}
                      unit={cadenceUnit}
                      onValueChange={setCadenceValue}
                      onUnitChange={setCadenceUnit}
                    />
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  Priority helps you sort what matters most in your feed. You can change both later.
                </p>
              </>
            ) : (
              <button
                type="button"
                onClick={() => setShowAdvanced(true)}
                className="justify-self-start text-xs font-medium text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
              >
                Advanced options (priority, check frequency)
              </button>
            )}
            <Button>
              <Plus />
              Start monitoring
            </Button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Monitor dossier dialog — the old /monitors/[id] page, plus that company's
// alert recipients inline.
// ---------------------------------------------------------------------------

export function MonitorDetailDialog({ sourceId, onClose }: { sourceId: number; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [cadenceValue, setCadenceValue] = React.useState("1");
  const [cadenceUnit, setCadenceUnit] = React.useState<CadenceUnit>("hour");

  const sourceQuery = useQuery({
    queryKey: queryKeys.source(sourceId),
    queryFn: () => getSource(sourceId),
  });
  const companiesQuery = useQuery({ queryKey: queryKeys.companies, queryFn: listCompanies });
  const summariesQuery = useQuery({
    queryKey: queryKeys.sourceSummaries(sourceId),
    queryFn: () => listSourceSummaries(sourceId),
  });
  const statsQuery = useQuery({ queryKey: queryKeys.insightStats(30), queryFn: () => getInsightStats(30) });

  const { check, isChecking, progress } = useSourceCheck(sourceId);
  const pauseMutation = useMutation({
    mutationFn: (enabled: boolean) => updateSource(sourceId, { enabled }),
    onSuccess: (updatedSource) => {
      toast.success(updatedSource.enabled ? "Monitoring resumed." : "Monitoring paused.");
      queryClient.invalidateQueries({ queryKey: queryKeys.source(sourceId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.sources });
      queryClient.invalidateQueries({ queryKey: queryKeys.monitorStatus });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
  const reviewMutation = useMutation({
    mutationFn: (id: string) => updateInsightReview(id, true),
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
      onClose();
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const source = sourceQuery.data;
  React.useEffect(() => {
    if (source) {
      const parts = minutesToParts(source.schedule_minutes);
      setCadenceValue(String(parts.value));
      setCadenceUnit(parts.unit);
    }
  }, [source?.schedule_minutes]);
  const editedMinutes = toMinutes(cadenceValue, cadenceUnit);
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
    <Dialog open onOpenChange={(next) => (!next ? onClose() : undefined)}>
      <DialogContent className="max-h-[88vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <div className="flex min-w-0 items-center gap-4 pr-6">
            {source ? <CompanyFavicon url={source.url} name={companyName} size={44} /> : null}
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <DialogTitle className="truncate text-2xl">{companyName}</DialogTitle>
                {source ? (
                  <Badge variant={source.enabled ? "success" : "secondary"}>
                    {source.enabled ? "Active" : "Paused"}
                  </Badge>
                ) : null}
                {company ? <PriorityBadge priority={company.priority} /> : null}
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
                <DialogDescription
                  className={cn(
                    "mt-1",
                    health.tone === "warn" && "font-medium text-foreground",
                  )}
                >
                  {health.label}
                </DialogDescription>
              ) : null}
            </div>
          </div>
        </DialogHeader>

        {source ? (
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={check}
              disabled={!source.enabled || isChecking}
              title={source.enabled ? "Check now" : "Resume monitoring to run a check"}
            >
              {isChecking ? <Loader2 className="animate-spin" /> : <RefreshCw />}
              {isChecking ? progress?.message || "Checking" : "Check now"}
            </Button>
            <Button
              variant="outline"
              onClick={() => pauseMutation.mutate(!source.enabled)}
              disabled={pauseMutation.isPending}
            >
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

        {isChecking && progress ? (
          <div className="rounded-lg border bg-secondary/40 p-3 text-sm text-muted-foreground">
            <span className="font-medium text-foreground capitalize">{progress.stage}: </span>
            {progress.current !== null && progress.total !== null
              ? `${progress.current}/${progress.total} · `
              : null}
            {progress.message}
          </div>
        ) : null}

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {glance.map((item) => (
            <div key={item.label} className="rounded-xl border bg-secondary/50 px-3 py-2.5">
              <div className="text-xs font-medium text-muted-foreground">{item.label}</div>
              <div className="mt-0.5 text-sm font-semibold sm:text-base">{item.value}</div>
            </div>
          ))}
        </div>

        <div className="rounded-xl border p-4">
          <div className="mb-2 text-sm font-semibold">Activity over time</div>
          <ActivityPulse
            data={activity}
            height={96}
            ariaLabel={`30-day activity for ${companyName}`}
            emptyLabel="No relevant updates in the last 30 days"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-xl border p-4">
            <div className="mb-3 text-sm font-semibold">Check frequency</div>
            <div className="flex items-center gap-2">
              <CadenceField
                value={cadenceValue}
                unit={cadenceUnit}
                onValueChange={setCadenceValue}
                onUnitChange={setCadenceUnit}
                compact
                className="flex-1"
              />
              <Button
                size="sm"
                variant="outline"
                disabled={cadenceMutation.isPending || editedMinutes === source?.schedule_minutes}
                onClick={() => cadenceMutation.mutate(editedMinutes)}
              >
                Update
              </Button>
            </div>
            <div className="mt-3 grid gap-1 text-xs text-muted-foreground">
              <span>Currently {formatCadence(source?.schedule_minutes)}.</span>
              <span>Created {formatDateTime(source?.created_at)}.</span>
            </div>
          </div>

          {company ? <CompanyRecipients companyId={company.id} /> : null}
        </div>

        <section className="grid gap-3">
          <h3 className="text-sm font-semibold">Intelligence timeline</h3>
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
              No relevant business updates yet. Newly discovered article URLs are
              processed separately in batches.
            </div>
          ) : null}
        </section>
      </DialogContent>
    </Dialog>
  );
}

/** Alert recipients for one company, editable inline in the dossier. */
function CompanyRecipients({ companyId }: { companyId: number }) {
  const queryClient = useQueryClient();
  const [email, setEmail] = React.useState("");
  const recipientsQuery = useQuery({
    queryKey: queryKeys.companyRecipients,
    queryFn: listCompanyRecipients,
  });

  const addMutation = useMutation({
    mutationFn: () => createCompanyRecipient(companyId, { email, enabled: true }),
    onSuccess: () => {
      toast.success("Recipient added.");
      setEmail("");
      queryClient.invalidateQueries({ queryKey: queryKeys.companyRecipients });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
  const deleteMutation = useMutation({
    mutationFn: deleteNotificationRecipient,
    onSuccess: () => {
      toast.success("Recipient removed.");
      queryClient.invalidateQueries({ queryKey: queryKeys.companyRecipients });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const recipients =
    recipientsQuery.data?.find((company) => company.id === companyId)?.recipients || [];

  return (
    <div className="rounded-xl border p-4">
      <div className="mb-3 flex items-center gap-1.5 text-sm font-semibold">
        <Bell className="size-3.5" />
        Alert recipients
      </div>
      <div className="flex flex-wrap gap-2">
        {recipients.map((recipient) => (
          <span
            key={recipient.id}
            className="inline-flex items-center gap-2 rounded-full border bg-secondary px-3 py-1 text-sm"
          >
            {recipient.email}
            <button
              aria-label={`Remove ${recipient.email}`}
              onClick={() => deleteMutation.mutate(recipient.id)}
            >
              <Trash2 className="size-3.5" />
            </button>
          </span>
        ))}
        {!recipients.length ? (
          <span className="text-xs text-muted-foreground">No recipients yet.</span>
        ) : null}
      </div>
      <form
        className="mt-3 flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          addMutation.mutate();
        }}
      >
        <Input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="person@example.com"
          required
          className="h-8 flex-1"
        />
        <Button size="sm" disabled={addMutation.isPending}>
          <Plus />
          Add
        </Button>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Alerts section — notification cadence, delivery health, recipients.
// ---------------------------------------------------------------------------

export function AlertsSection() {
  const queryClient = useQueryClient();
  const [emailByCompany, setEmailByCompany] = React.useState<Record<number, string>>({});
  const recipientsQuery = useQuery({
    queryKey: queryKeys.companyRecipients,
    queryFn: listCompanyRecipients,
  });
  const settingsQuery = useQuery({
    queryKey: queryKeys.emailSettings,
    queryFn: getEmailNotificationSettings,
  });
  const sesQuery = useQuery({ queryKey: queryKeys.sesStatus, queryFn: getSesStatus });
  const insightsQuery = useQuery({ queryKey: queryKeys.insights, queryFn: () => listInsights(200) });

  const settingsMutation = useMutation({
    mutationFn: updateEmailNotificationSettings,
    onSuccess: () => {
      toast.success("Notification cadence updated.");
      queryClient.invalidateQueries({ queryKey: queryKeys.emailSettings });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
  const retryMutation = useMutation({
    mutationFn: sendEmailSummary,
    onSuccess: (result) => {
      if (result.status === "sent") toast.success("Alert sent.");
      else toast.message(result.message);
      queryClient.invalidateQueries({ queryKey: queryKeys.insights });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
  const addMutation = useMutation({
    mutationFn: ({ companyId, email }: { companyId: number; email: string }) =>
      createCompanyRecipient(companyId, { email, enabled: true }),
    onSuccess: () => {
      toast.success("Recipient added.");
      setEmailByCompany({});
      queryClient.invalidateQueries({ queryKey: queryKeys.companyRecipients });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });
  const deleteMutation = useMutation({
    mutationFn: deleteNotificationRecipient,
    onSuccess: () => {
      toast.success("Recipient removed.");
      queryClient.invalidateQueries({ queryKey: queryKeys.companyRecipients });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const mode = settingsQuery.data?.mode || "manual";
  const insights = insightsQuery.data || [];
  const unreviewedCount = insights.filter((i) => !i.reviewed_at).length;
  const failedInsights = insights
    .filter((i) => i.email_status === "failed")
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  const sesConfigured = sesQuery.data?.configured ?? true; // avoid a false alarm before the first load resolves

  const MODE_OPTIONS = [
    {
      label: "Automatic",
      value: "automatic" as const,
      icon: Zap,
      detail: "Send each update the moment your sentinel spots it.",
      context: "Delivers instantly — no one reviews it first.",
    },
    {
      label: "Manual review",
      value: "manual" as const,
      icon: ClipboardCheck,
      detail: "Send only the updates your team approves first.",
      context:
        unreviewedCount > 0
          ? `${unreviewedCount} update${unreviewedCount === 1 ? "" : "s"} waiting for review right now.`
          : "Nothing waiting for review right now.",
    },
  ];

  return (
    <div className="grid gap-6">
      {sesQuery.data && !sesConfigured ? (
        <div className="flex items-start gap-3 rounded-xl border border-border bg-secondary p-4 text-sm text-foreground">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <div>
            <div className="font-medium">Email alerts aren't connected yet.</div>
            <p className="mt-0.5 text-muted-foreground">
              {sesQuery.data.missing.includes("SES_FROM_EMAIL")
                ? "No sender address is configured, so neither automatic nor manually-approved alerts can be delivered."
                : "Alert delivery isn't fully configured."}{" "}
              Contact your Sentinel Actalyst admin to finish setup.
            </p>
          </div>
        </div>
      ) : null}

      {failedInsights.length > 0 ? (
        <Card className="border-destructive/40">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <MailWarning className="size-4" />
              {failedInsights.length} alert{failedInsights.length === 1 ? "" : "s"} failed to send
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2">
            {failedInsights.slice(0, 5).map((insight) => (
              <div
                key={insight.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">
                    {insight.title || hostOf(insight.discovered_url) || "Website update"}
                  </div>
                  <div className="truncate text-xs text-muted-foreground">
                    {insight.email_error || "Delivery failed."} · {formatRelativeTime(insight.created_at)}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={retryMutation.isPending}
                  onClick={() => retryMutation.mutate(insight.id)}
                >
                  <RefreshCw className={retryMutation.isPending ? "animate-spin" : undefined} />
                  Retry
                </Button>
              </div>
            ))}
            {failedInsights.length > 5 ? (
              <p className="text-xs text-muted-foreground">
                +{failedInsights.length - 5} more failed alert{failedInsights.length - 5 === 1 ? "" : "s"}.
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="size-4" />
            When to send alerts
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          {MODE_OPTIONS.map((option) => {
            const Icon = option.icon;
            const selected = mode === option.value;
            return (
              <button
                key={option.value}
                className={`relative rounded-xl border p-4 text-left transition-colors hover:bg-accent ${
                  selected ? "border-foreground bg-accent" : "bg-card"
                }`}
                onClick={() => settingsMutation.mutate({ mode: option.value })}
              >
                {selected ? (
                  <CheckCircle2 className="absolute right-3 top-3 size-4 text-primary" aria-label="Selected" />
                ) : null}
                <div className="flex items-center gap-2 font-semibold">
                  <Icon className="size-4" />
                  {option.label}
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{option.detail}</p>
                <p className="mt-2 text-xs font-medium text-muted-foreground/80">{option.context}</p>
              </button>
            );
          })}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="size-4" />
            Alert recipients
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-5">
          {(recipientsQuery.data || []).map((company) => (
            <section key={company.id} className="rounded-xl border p-4">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <h3 className="font-semibold">{company.name}</h3>
                <Badge variant="secondary">{company.recipients.length} recipients</Badge>
              </div>
              <div className="flex flex-wrap gap-2">
                {company.recipients.map((recipient) => (
                  <span
                    key={recipient.id}
                    className="inline-flex items-center gap-2 rounded-full border bg-secondary px-3 py-1 text-sm"
                  >
                    {recipient.email}
                    <button
                      aria-label={`Remove ${recipient.email}`}
                      onClick={() => deleteMutation.mutate(recipient.id)}
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </span>
                ))}
              </div>
              <form
                className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-end"
                onSubmit={(event) => {
                  event.preventDefault();
                  addMutation.mutate({
                    companyId: company.id,
                    email: emailByCompany[company.id] || "",
                  });
                }}
              >
                <div className="grid flex-1 gap-2">
                  <Label htmlFor={`recipient-${company.id}`}>Add recipient</Label>
                  <Input
                    id={`recipient-${company.id}`}
                    type="email"
                    value={emailByCompany[company.id] || ""}
                    onChange={(event) =>
                      setEmailByCompany((current) => ({
                        ...current,
                        [company.id]: event.target.value,
                      }))
                    }
                    placeholder="person@example.com"
                    required
                  />
                </div>
                <Button>
                  <Plus />
                  Add
                </Button>
              </form>
            </section>
          ))}
          {!recipientsQuery.isLoading && !(recipientsQuery.data || []).length ? (
            <div className="rounded-xl border border-dashed p-6 text-sm text-muted-foreground">
              Add a monitor before configuring recipients.
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
