"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink, Play, RotateCcw, Search, Trash2 } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { Link, useParams, useRouter } from "@/components/router";
import { StatusBadge } from "@/components/status-badge";
import {
  type ActiveTask,
  TaskProgressDialog,
} from "@/components/task-progress-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  baselineSource,
  deleteSource,
  getApiErrorMessage,
  getSource,
  getSourceDiscoveryPreview,
  listCompanies,
  listSourceDiscoveredUrls,
  listSourceRuns,
  listSourceSummaries,
  runSource,
  taskHasFailedResult,
  type TaskStatus,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { formatDateTime, truncate } from "@/lib/utils";

export default function SourceDetailsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const sourceId = Number(params.id);
  const [activeTask, setActiveTask] = React.useState<ActiveTask | null>(null);

  const sourceQuery = useQuery({
    queryKey: queryKeys.source(sourceId),
    queryFn: () => getSource(sourceId),
    enabled: Number.isFinite(sourceId),
  });

  const companiesQuery = useQuery({
    queryKey: queryKeys.companies,
    queryFn: listCompanies,
  });

  const runsQuery = useQuery({
    queryKey: queryKeys.sourceRuns(sourceId),
    queryFn: () => listSourceRuns(sourceId),
    enabled: Number.isFinite(sourceId),
  });

  const discoveredQuery = useQuery({
    queryKey: queryKeys.sourceDiscoveredUrls(sourceId),
    queryFn: () => listSourceDiscoveredUrls(sourceId),
    enabled: Number.isFinite(sourceId),
  });

  const summariesQuery = useQuery({
    queryKey: queryKeys.sourceSummaries(sourceId),
    queryFn: () => listSourceSummaries(sourceId),
    enabled: Number.isFinite(sourceId),
  });

  const previewQuery = useQuery({
    queryKey: queryKeys.sourceDiscoveryPreview(sourceId),
    queryFn: () => getSourceDiscoveryPreview(sourceId),
    enabled: false,
    retry: false,
  });

  const runMutation = useMutation({
    mutationFn: runSource,
    onSuccess: (task) => setActiveTask({ taskId: task.task_id, title: "Run source" }),
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const baselineMutation = useMutation({
    mutationFn: baselineSource,
    onSuccess: (task) => setActiveTask({ taskId: task.task_id, title: "Baseline source" }),
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteSource,
    onSuccess: () => {
      toast.success("Source deleted.");
      queryClient.invalidateQueries({ queryKey: queryKeys.sources });
      router.push("/sources");
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  function handleTaskFinished(task: TaskStatus) {
    if (!taskHasFailedResult(task)) {
      toast.success("Task completed.");
    } else {
      toast.error("Task failed.");
    }

    queryClient.invalidateQueries({ queryKey: queryKeys.source(sourceId) });
    queryClient.invalidateQueries({ queryKey: queryKeys.sourceRuns(sourceId) });
    queryClient.invalidateQueries({
      queryKey: queryKeys.sourceDiscoveredUrls(sourceId),
    });
    queryClient.invalidateQueries({ queryKey: queryKeys.sourceSummaries(sourceId) });
    queryClient.invalidateQueries({ queryKey: queryKeys.runs });
    queryClient.invalidateQueries({ queryKey: queryKeys.monitorStatus });
  }

  const source = sourceQuery.data;
  const company = companiesQuery.data?.find(
    (item) => item.id === source?.company_id,
  );

  return (
    <div className="grid gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <Button asChild variant="ghost" className="mb-2 px-0">
            <Link href="/sources">
              <ArrowLeft />
              Back to sources
            </Link>
          </Button>
          <h2 className="truncate text-2xl font-semibold">
            {source ? source.url : "Source details"}
          </h2>
          <p className="text-sm text-muted-foreground">
            {company?.name || (source ? `Company #${source.company_id}` : "Loading")}
          </p>
        </div>
        {source ? (
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => runMutation.mutate(source.id)}>
              <Play />
              Run
            </Button>
            <Button variant="outline" onClick={() => baselineMutation.mutate(source.id)}>
              <RotateCcw />
              Baseline
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (confirm(`Delete source #${source.id}?`)) {
                  deleteMutation.mutate(source.id);
                }
              }}
            >
              <Trash2 />
              Delete
            </Button>
          </div>
        ) : null}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Metadata</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm">
            {source ? (
              <>
                <div className="flex justify-between gap-3">
                  <span className="text-muted-foreground">Strategy</span>
                  <Badge variant="outline">{source.strategy}</Badge>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-muted-foreground">Enabled</span>
                  <StatusBadge status={source.enabled ? "enabled" : "disabled"} />
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-muted-foreground">Trace JS</span>
                  <span>{source.trace_js ? "Yes" : "No"}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-muted-foreground">Schedule</span>
                  <span>{source.schedule_minutes} min</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-muted-foreground">Last checked</span>
                  <span>{formatDateTime(source.last_checked_at)}</span>
                </div>
              </>
            ) : (
              <div className="text-muted-foreground">Loading source metadata.</div>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>JS bundle sources</CardTitle>
          </CardHeader>
          <CardContent>
            {source?.js_bundle_sources.length ? (
              <div className="grid gap-2">
                {source.js_bundle_sources.map((bundle) => (
                  <code key={bundle} className="rounded-md bg-secondary px-3 py-2 text-sm">
                    {bundle}
                  </code>
                ))}
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">No bundle sources.</div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle>Discovery check</CardTitle>
            <Button
              variant="outline"
              onClick={() => previewQuery.refetch()}
              disabled={!source || previewQuery.isFetching}
            >
              <Search />
              {previewQuery.isFetching ? "Checking" : "Run check"}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4">
          {!previewQuery.data && !previewQuery.isFetching ? (
            <div className="text-sm text-muted-foreground">
              Run this check to see whether the source is being crawled and how many URLs survive filtering before storage.
            </div>
          ) : null}

          {previewQuery.data ? (
            <>
              {previewQuery.data.message ? (
                <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
                  {previewQuery.data.message}
                </div>
              ) : null}

              <div className="grid gap-3 sm:grid-cols-4">
                <div className="rounded-lg border p-3">
                  <div className="text-xs text-muted-foreground">Raw URLs</div>
                  <div className="text-2xl font-semibold">
                    {previewQuery.data.raw_url_count}
                  </div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-xs text-muted-foreground">Content URLs</div>
                  <div className="text-2xl font-semibold">
                    {previewQuery.data.content_url_count}
                  </div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-xs text-muted-foreground">Already Seen</div>
                  <div className="text-2xl font-semibold">
                    {previewQuery.data.already_seen_count}
                  </div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-xs text-muted-foreground">New Candidates</div>
                  <div className="text-2xl font-semibold">
                    {previewQuery.data.new_candidate_count}
                  </div>
                </div>
              </div>

              {previewQuery.data.urls.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>URL</TableHead>
                      <TableHead>Seen</TableHead>
                      <TableHead>Source</TableHead>
                      <TableHead>Region</TableHead>
                      <TableHead className="w-16"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {previewQuery.data.urls.map((item) => (
                      <TableRow key={item.url}>
                        <TableCell className="max-w-xl">
                          <div className="font-medium">{truncate(item.url, 100)}</div>
                          {item.label ? (
                            <div className="text-xs text-muted-foreground">
                              {truncate(item.label, 80)}
                            </div>
                          ) : null}
                        </TableCell>
                        <TableCell>
                          <Badge variant={item.already_seen ? "secondary" : "success"}>
                            {item.already_seen ? "yes" : "new"}
                          </Badge>
                        </TableCell>
                        <TableCell>{item.source || "-"}</TableCell>
                        <TableCell>{item.region || "-"}</TableCell>
                        <TableCell>
                          <Button asChild size="icon" variant="ghost">
                            <a
                              href={item.url}
                              target="_blank"
                              rel="noreferrer"
                              aria-label="Open preview URL"
                            >
                              <ExternalLink />
                            </a>
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : null}
            </>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent runs</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Started</TableHead>
                <TableHead>Finished</TableHead>
                <TableHead>Error</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(runsQuery.data || []).map((run) => (
                <TableRow key={run.id}>
                  <TableCell>#{run.id}</TableCell>
                  <TableCell>
                    <StatusBadge status={run.status} />
                  </TableCell>
                  <TableCell>{formatDateTime(run.started_at)}</TableCell>
                  <TableCell>{formatDateTime(run.finished_at)}</TableCell>
                  <TableCell className="max-w-sm truncate">{run.error || "-"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent discovered URLs</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            {(discoveredQuery.data || []).map((item) => (
              <div key={item.id} className="rounded-lg border p-3">
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 font-medium text-primary"
                >
                  {truncate(item.url, 80)}
                  <ExternalLink className="size-3" />
                </a>
                <div className="mt-1 text-xs text-muted-foreground">
                  {formatDateTime(item.discovered_at)}
                </div>
              </div>
            ))}
            {!discoveredQuery.isLoading && (discoveredQuery.data || []).length === 0 ? (
              <div className="text-sm text-muted-foreground">No discovered URLs.</div>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent summaries</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            {(summariesQuery.data || []).map((summary) => (
              <div key={summary.id} className="rounded-lg border p-3">
                <div className="font-medium">{summary.title || "Untitled"}</div>
                <a
                  href={summary.discovered_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 block truncate text-xs text-primary"
                >
                  {summary.discovered_url}
                </a>
                <p className="mt-2 text-sm text-muted-foreground">
                  {summary.summary}
                </p>
              </div>
            ))}
            {!summariesQuery.isLoading && (summariesQuery.data || []).length === 0 ? (
              <div className="text-sm text-muted-foreground">No summaries.</div>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <TaskProgressDialog
        task={activeTask}
        onClose={() => setActiveTask(null)}
        onFinished={handleTaskFinished}
      />
    </div>
  );
}
