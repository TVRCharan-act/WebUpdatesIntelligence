"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, CheckCircle2, Clock3, Play, Radar, XCircle } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { Link } from "@/components/router";
import { StatusBadge } from "@/components/status-badge";
import {
  type ActiveTask,
  TaskProgressDialog,
} from "@/components/task-progress-dialog";
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
  getApiErrorMessage,
  getDiscoveryHealth,
  getMonitorStatus,
  listRuns,
  runAllSources,
  taskHasFailedResult,
  type TaskStatus,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { formatDateTime } from "@/lib/utils";

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const [activeTask, setActiveTask] = React.useState<ActiveTask | null>(null);

  const statusQuery = useQuery({
    queryKey: queryKeys.monitorStatus,
    queryFn: getMonitorStatus,
  });

  const runsQuery = useQuery({
    queryKey: queryKeys.runs,
    queryFn: listRuns,
  });

  const discoveryHealthQuery = useQuery({
    queryKey: queryKeys.discoveryHealth,
    queryFn: getDiscoveryHealth,
  });

  const runAllMutation = useMutation({
    mutationFn: runAllSources,
    onSuccess: (task) => {
      setActiveTask({
        taskId: task.task_id,
        title: "Run all sources",
      });
      toast.success("Run all queued.");
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  function handleTaskFinished(task: TaskStatus) {
    if (!taskHasFailedResult(task)) {
      toast.success("Task completed.");
    } else {
      toast.error("Task failed.");
    }

    queryClient.invalidateQueries({ queryKey: queryKeys.monitorStatus });
    queryClient.invalidateQueries({ queryKey: queryKeys.runs });
    queryClient.invalidateQueries({ queryKey: queryKeys.sources });
  }

  const status = statusQuery.data;
  const metrics = [
    {
      label: "Enabled Sources",
      value: status?.enabled_sources ?? 0,
      icon: Activity,
    },
    { label: "Queued Jobs", value: status?.queued ?? 0, icon: Clock3 },
    { label: "Running Jobs", value: status?.running ?? 0, icon: Play },
    {
      label: "Completed Today",
      value: status?.completed_today ?? 0,
      icon: CheckCircle2,
    },
    {
      label: "Failed Today",
      value: status?.failed_today ?? 0,
      icon: XCircle,
    },
  ];

  return (
    <div className="grid gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Dashboard</h2>
          <p className="text-sm text-muted-foreground">
            Monitor queue health and recent backend activity.
          </p>
        </div>
        <Button onClick={() => runAllMutation.mutate()} disabled={runAllMutation.isPending}>
          <Play />
          Run all
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <Card key={metric.label}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {metric.label}
                </CardTitle>
                <Icon className="size-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-semibold">{metric.value}</div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Radar className="size-4" />
            Discovery health
          </CardTitle>
        </CardHeader>
        <CardContent>
          {discoveryHealthQuery.data ? (
            <div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-6">
              <div>
                <div className="text-xs text-muted-foreground">OpenAI planner</div>
                <StatusBadge
                  status={discoveryHealthQuery.data.openai_configured ? "configured" : "missing key"}
                />
                <div className="mt-1 text-xs text-muted-foreground">
                  {discoveryHealthQuery.data.openai_model}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Browser tracing</div>
                <StatusBadge
                  status={
                    discoveryHealthQuery.data.browser_tracing_available
                      ? "available"
                      : "unavailable"
                  }
                />
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Cached adapters</div>
                <div className="text-2xl font-semibold">
                  {discoveryHealthQuery.data.cached_adapter_count}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Recent discovery errors</div>
                <div className="text-2xl font-semibold">
                  {discoveryHealthQuery.data.recent_discovery_error_count}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Heavy trace lock</div>
                <StatusBadge
                  status={
                    discoveryHealthQuery.data.heavy_discovery_lock.locked ? "locked" : "idle"
                  }
                />
                <div className="mt-1 text-xs text-muted-foreground">
                  TTL {String(discoveryHealthQuery.data.limits.heavy_lock_ttl_seconds ?? "-")}s
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Scrape budget</div>
                <div className="text-2xl font-semibold">
                  {String(discoveryHealthQuery.data.limits.max_discovered_urls ?? "-")}
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {String(discoveryHealthQuery.data.limits.max_browser_responses ?? "-")} responses
                </div>
              </div>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">Loading discovery health.</div>
          )}
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
                <TableHead>Source</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Started</TableHead>
                <TableHead>Finished</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(runsQuery.data || []).slice(0, 10).map((run) => (
                <TableRow key={run.id}>
                  <TableCell>
                    <Link className="font-medium text-primary" href="/runs">
                      #{run.id}
                    </Link>
                  </TableCell>
                  <TableCell>Source #{run.source_id}</TableCell>
                  <TableCell>
                    <StatusBadge status={run.status} />
                  </TableCell>
                  <TableCell>{formatDateTime(run.started_at)}</TableCell>
                  <TableCell>{formatDateTime(run.finished_at)}</TableCell>
                </TableRow>
              ))}
              {!runsQuery.isLoading && (runsQuery.data || []).length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                    No runs yet.
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <TaskProgressDialog
        task={activeTask}
        onClose={() => setActiveTask(null)}
        onFinished={handleTaskFinished}
      />
    </div>
  );
}
