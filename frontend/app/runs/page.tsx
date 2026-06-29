"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, ExternalLink, PlayCircle } from "lucide-react";
import * as React from "react";

import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/status-badge";
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
import { getRun, listRuns, listSources } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { formatDateTime, truncate } from "@/lib/utils";

function RunDetail({ runId }: { runId: number }) {
  const runQuery = useQuery({
    queryKey: queryKeys.run(runId),
    queryFn: () => getRun(runId),
  });

  if (runQuery.isLoading) {
    return <div className="text-sm text-muted-foreground">Loading run details.</div>;
  }

  if (!runQuery.data) {
    return <div className="text-sm text-muted-foreground">No details found.</div>;
  }

  return (
    <div className="grid gap-3">
      <div className="grid gap-2 rounded-lg border bg-background p-3 text-sm sm:grid-cols-3">
        <div>
          <div className="text-muted-foreground">Run ID</div>
          <div className="font-medium">#{runQuery.data.id}</div>
        </div>
        <div>
          <div className="text-muted-foreground">Source ID</div>
          <div className="font-medium">#{runQuery.data.source_id}</div>
        </div>
        <div>
          <div className="text-muted-foreground">Discovered URLs</div>
          <div className="font-medium">{runQuery.data.discovered_urls.length}</div>
        </div>
      </div>
      <div className="grid gap-2">
        {runQuery.data.discovered_urls.map((item) => (
          <a
            key={item.id}
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center justify-between gap-3 rounded-md border bg-background px-3 py-2 text-sm text-primary"
          >
            <span className="truncate">{truncate(item.url, 100)}</span>
            <ExternalLink className="size-4 shrink-0" />
          </a>
        ))}
        {runQuery.data.discovered_urls.length === 0 ? (
          <div className="text-sm text-muted-foreground">No URLs were attached to this run.</div>
        ) : null}
      </div>
    </div>
  );
}

export default function RunsPage() {
  const [expandedId, setExpandedId] = React.useState<number | null>(null);

  const runsQuery = useQuery({
    queryKey: queryKeys.runs,
    queryFn: listRuns,
  });

  const sourcesQuery = useQuery({
    queryKey: queryKeys.sources,
    queryFn: listSources,
  });

  const sourceById = new Map(
    (sourcesQuery.data || []).map((source) => [source.id, source.url]),
  );
  const runs = runsQuery.data || [];

  return (
    <div className="grid gap-6">
      <div>
        <h2 className="text-2xl font-semibold">Runs</h2>
        <p className="text-sm text-muted-foreground">
          Inspect monitor run history and discovered URLs.
        </p>
      </div>

      {runs.length === 0 && !runsQuery.isLoading ? (
        <EmptyState
          icon={PlayCircle}
          title="No runs"
          description="Run a source or baseline to populate monitor history."
        />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Run history</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10"></TableHead>
                  <TableHead>ID</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Finished</TableHead>
                  <TableHead>Error</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((run) => {
                  const expanded = expandedId === run.id;
                  return (
                    <React.Fragment key={run.id}>
                      <TableRow>
                        <TableCell>
                          <Button
                            size="icon"
                            variant="ghost"
                            aria-label="Toggle run details"
                            onClick={() => setExpandedId(expanded ? null : run.id)}
                          >
                            {expanded ? <ChevronDown /> : <ChevronRight />}
                          </Button>
                        </TableCell>
                        <TableCell className="font-medium">#{run.id}</TableCell>
                        <TableCell className="max-w-xs">
                          {sourceById.get(run.source_id)
                            ? truncate(sourceById.get(run.source_id) || "", 48)
                            : `Source #${run.source_id}`}
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={run.status} />
                        </TableCell>
                        <TableCell>{formatDateTime(run.started_at)}</TableCell>
                        <TableCell>{formatDateTime(run.finished_at)}</TableCell>
                        <TableCell className="max-w-xs truncate">
                          {run.error || "-"}
                        </TableCell>
                      </TableRow>
                      {expanded ? (
                        <TableRow>
                          <TableCell colSpan={7} className="bg-secondary/40">
                            <RunDetail runId={run.id} />
                          </TableCell>
                        </TableRow>
                      ) : null}
                    </React.Fragment>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
