"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Loader2, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getTaskStatus, taskHasFailedResult, type TaskStatus } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

const terminalStates = new Set(["SUCCESS", "FAILURE", "REVOKED"]);

function taskLogMessages(result: unknown) {
  const items = Array.isArray(result) ? result : result ? [result] : [];
  const messages: string[] = [];

  for (const item of items) {
    if (!item || typeof item !== "object") {
      continue;
    }

    const sourceId = "source_id" in item ? item.source_id : undefined;
    const prefix =
      typeof sourceId === "number" ? `Source ${sourceId}: ` : "";
    const logMessages =
      "log_messages" in item && Array.isArray(item.log_messages)
        ? item.log_messages
        : [];

    for (const message of logMessages) {
      if (typeof message === "string") {
        messages.push(`${prefix}${message}`);
      }
    }
  }

  return messages;
}

export interface ActiveTask {
  taskId: string;
  title: string;
  description?: string;
}

export function TaskProgressDialog({
  task,
  onClose,
  onFinished,
}: {
  task: ActiveTask | null;
  onClose: () => void;
  onFinished: (task: TaskStatus) => void;
}) {
  const [reportedTaskId, setReportedTaskId] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (task?.taskId !== reportedTaskId) {
      setReportedTaskId(null);
    }
  }, [reportedTaskId, task?.taskId]);

  const query = useQuery({
    queryKey: task ? queryKeys.task(task.taskId) : ["tasks", "idle"],
    queryFn: () => getTaskStatus(task?.taskId || ""),
    enabled: Boolean(task),
    refetchInterval: (queryResult) => {
      const state = queryResult.state.data?.state;
      return state && terminalStates.has(state) ? false : 2000;
    },
  });

  React.useEffect(() => {
    const data = query.data;
    if (!data || !terminalStates.has(data.state) || reportedTaskId === data.task_id) {
      return;
    }

    setReportedTaskId(data.task_id);
    onFinished(data);
  }, [onFinished, query.data, reportedTaskId]);

  const state = query.data?.state || "PENDING";
  const isDone = terminalStates.has(state);
  const isFailure = query.data ? taskHasFailedResult(query.data) : false;
  const logMessages = taskLogMessages(query.data?.result);

  return (
    <Dialog open={Boolean(task)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{task?.title || "Task progress"}</DialogTitle>
          <DialogDescription>
            {task?.description || "Waiting for the backend worker to finish."}
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-4 rounded-lg border bg-secondary/40 p-4">
          <div className="flex size-10 items-center justify-center rounded-md bg-card">
            {!isDone ? (
              <Loader2 className="size-5 animate-spin text-primary" />
            ) : isFailure ? (
              <XCircle className="size-5 text-destructive" />
            ) : (
              <CheckCircle2 className="size-5 text-emerald-600" />
            )}
          </div>
          <div className="min-w-0">
            <div className="text-sm font-medium">State: {state}</div>
            <div className="truncate text-xs text-muted-foreground">
              {task?.taskId}
            </div>
          </div>
        </div>

        {logMessages.length > 0 ? (
          <div className="rounded-lg border bg-card p-4">
            <div className="mb-2 text-sm font-medium">Output log</div>
            <div className="grid gap-2">
              {logMessages.map((message, index) => (
                <div
                  key={`${message}-${index}`}
                  className="flex gap-2 text-sm text-muted-foreground"
                >
                  {/(failed|rejected|error)/i.test(message) ? (
                    <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600" />
                  ) : (
                    <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" />
                  )}
                  <span>{message}</span>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {query.data?.result ? (
          <pre className="max-h-56 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-50">
            {JSON.stringify(query.data.result, null, 2)}
          </pre>
        ) : null}

        <DialogFooter>
          <Button onClick={onClose} disabled={!isDone}>
            {isDone ? "Close" : "Working"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
