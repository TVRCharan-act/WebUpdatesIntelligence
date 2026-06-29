"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DatabaseZap, Eye, Pencil, Play, Plus, RotateCcw, Trash2 } from "lucide-react";
import Link from "next/link";
import * as React from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { SourceFormDialog } from "@/components/source-form-dialog";
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
  createSource,
  deleteSource,
  getApiErrorMessage,
  listCompanies,
  listSources,
  runSource,
  taskHasFailedResult,
  type Source,
  type SourceCreateInput,
  type SourceUpdateInput,
  type TaskStatus,
  updateSource,
} from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { formatDateTime, truncate } from "@/lib/utils";

export default function SourcesPage() {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = React.useState(false);
  const [editingSource, setEditingSource] = React.useState<Source | undefined>();
  const [activeTask, setActiveTask] = React.useState<ActiveTask | null>(null);

  const companiesQuery = useQuery({
    queryKey: queryKeys.companies,
    queryFn: listCompanies,
  });

  const sourcesQuery = useQuery({
    queryKey: queryKeys.sources,
    queryFn: listSources,
  });

  const companyById = new Map(
    (companiesQuery.data || []).map((company) => [company.id, company.name]),
  );

  const createMutation = useMutation({
    mutationFn: createSource,
    onSuccess: (source) => {
      toast.success("Source created.");
      setFormOpen(false);
      setEditingSource(undefined);
      baselineMutation.mutate(source.id);
      queryClient.invalidateQueries({ queryKey: queryKeys.sources });
      queryClient.invalidateQueries({ queryKey: queryKeys.monitorStatus });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, input }: { id: number; input: SourceUpdateInput }) =>
      updateSource(id, input),
    onSuccess: () => {
      toast.success("Source updated.");
      setFormOpen(false);
      setEditingSource(undefined);
      queryClient.invalidateQueries({ queryKey: queryKeys.sources });
      queryClient.invalidateQueries({ queryKey: queryKeys.monitorStatus });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteSource,
    onSuccess: () => {
      toast.success("Source deleted.");
      queryClient.invalidateQueries({ queryKey: queryKeys.sources });
      queryClient.invalidateQueries({ queryKey: queryKeys.monitorStatus });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const runMutation = useMutation({
    mutationFn: runSource,
    onSuccess: (task) => {
      toast.success("Run queued.");
      setActiveTask({ taskId: task.task_id, title: "Run source" });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  const baselineMutation = useMutation({
    mutationFn: baselineSource,
    onSuccess: (task) => {
      toast.success("URL extraction baseline queued.");
      setActiveTask({
        taskId: task.task_id,
        title: "Extract and store source URLs",
        description:
          "Crawling the source URL to store its current URLs without Firecrawl or LLM summarization.",
      });
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  });

  function handleSubmit(input: SourceCreateInput | SourceUpdateInput) {
    if (editingSource) {
      updateMutation.mutate({ id: editingSource.id, input });
      return;
    }

    createMutation.mutate(input as SourceCreateInput);
  }

  function handleTaskFinished(task: TaskStatus) {
    if (!taskHasFailedResult(task)) {
      toast.success("Task completed.");
    } else {
      toast.error("Task failed.");
    }

    queryClient.invalidateQueries({ queryKey: queryKeys.monitorStatus });
    queryClient.invalidateQueries({ queryKey: queryKeys.sources });
    queryClient.invalidateQueries({ queryKey: queryKeys.runs });
  }

  const sources = sourcesQuery.data || [];

  return (
    <div className="grid gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Sources</h2>
          <p className="text-sm text-muted-foreground">
            Create, schedule, baseline, and run monitor targets.
          </p>
        </div>
        <Button
          onClick={() => {
            setEditingSource(undefined);
            setFormOpen(true);
          }}
        >
          <Plus />
          Add source
        </Button>
      </div>

      {sources.length === 0 && !sourcesQuery.isLoading ? (
        <EmptyState
          icon={DatabaseZap}
          title="No sources"
          description="Add a source to start monitoring a website, feed, or API."
        />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Source list</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>URL</TableHead>
                  <TableHead>Company</TableHead>
                  <TableHead>Strategy</TableHead>
                  <TableHead>Schedule</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last checked</TableHead>
                  <TableHead className="w-56">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sources.map((source) => (
                  <TableRow key={source.id}>
                    <TableCell className="max-w-xs">
                      <div className="font-medium">{truncate(source.url, 52)}</div>
                      <div className="text-xs text-muted-foreground">#{source.id}</div>
                    </TableCell>
                    <TableCell>
                      {companyById.get(source.company_id) || `#${source.company_id}`}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{source.strategy}</Badge>
                    </TableCell>
                    <TableCell>{source.schedule_minutes} min</TableCell>
                    <TableCell>
                      <StatusBadge status={source.enabled ? "enabled" : "disabled"} />
                    </TableCell>
                    <TableCell>{formatDateTime(source.last_checked_at)}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-2">
                        <Button asChild size="icon" variant="outline" aria-label="View source">
                          <Link href={`/sources/${source.id}`}>
                            <Eye />
                          </Link>
                        </Button>
                        <Button
                          size="icon"
                          variant="outline"
                          aria-label="Edit source"
                          onClick={() => {
                            setEditingSource(source);
                            setFormOpen(true);
                          }}
                        >
                          <Pencil />
                        </Button>
                        <Button
                          size="icon"
                          variant="outline"
                          aria-label="Run source"
                          onClick={() => runMutation.mutate(source.id)}
                        >
                          <Play />
                        </Button>
                        <Button
                          size="icon"
                          variant="outline"
                          aria-label="Baseline source"
                          onClick={() => baselineMutation.mutate(source.id)}
                        >
                          <RotateCcw />
                        </Button>
                        <Button
                          size="icon"
                          variant="destructive"
                          aria-label="Delete source"
                          onClick={() => {
                            if (confirm(`Delete source #${source.id}?`)) {
                              deleteMutation.mutate(source.id);
                            }
                          }}
                        >
                          <Trash2 />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <SourceFormDialog
        open={formOpen}
        companies={companiesQuery.data || []}
        source={editingSource}
        isSaving={createMutation.isPending || updateMutation.isPending}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) {
            setEditingSource(undefined);
          }
        }}
        onSubmit={handleSubmit}
      />

      <TaskProgressDialog
        task={activeTask}
        onClose={() => setActiveTask(null)}
        onFinished={handleTaskFinished}
      />
    </div>
  );
}
