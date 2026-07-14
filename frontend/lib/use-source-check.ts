import { useQueryClient, useQuery } from "@tanstack/react-query";
import * as React from "react";
import { toast } from "sonner";

import { getApiErrorMessage, getTaskStatus, runSource, taskHasFailedResult } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

const TERMINAL_STATES = new Set(["succeeded", "partially_succeeded", "failed", "cancelled"]);

function checkCompletionMessage(task: { result: unknown }): string {
  const result = task.result;
  if (!result || typeof result !== "object" || Array.isArray(result)) {
    return "Check complete.";
  }

  const payload = result as Record<string, unknown>;
  const newUrls = Array.isArray(payload.new_urls) ? payload.new_urls.length : null;
  const processedUrls = Array.isArray(payload.processed_urls)
    ? payload.processed_urls.length
    : null;
  const deferredUrls = Array.isArray(payload.deferred_urls)
    ? payload.deferred_urls.length
    : null;

  if (newUrls === null) {
    return "Check complete.";
  }

  const parts = [`${newUrls} new URL${newUrls === 1 ? "" : "s"} found`];
  if (processedUrls !== null) {
    parts.push(`${processedUrls} processed`);
  }
  if (deferredUrls) {
    parts.push(`${deferredUrls} deferred to the next check`);
  }

  return `Check complete: ${parts.join("; ")}.`;
}

export function useSourceCheck(sourceId: number) {
  const queryClient = useQueryClient();
  const [taskId, setTaskId] = React.useState<string | null>(null);
  const [isStarting, setIsStarting] = React.useState(false);

  const taskQuery = useQuery({
    queryKey: taskId ? queryKeys.task(taskId) : queryKeys.task("idle"),
    queryFn: () => getTaskStatus(taskId as string),
    enabled: Boolean(taskId),
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      return state && TERMINAL_STATES.has(state) ? false : 2000;
    },
  });

  React.useEffect(() => {
    const data = taskQuery.data;
    const state = data?.state;
    if (!taskId || !data || !state || !TERMINAL_STATES.has(state)) {
      return;
    }

    const failed = state === "failed" || state === "cancelled" || taskHasFailedResult(data);
    toast[failed ? "error" : "success"](
      failed ? "Check failed." : checkCompletionMessage(data),
    );
    setTaskId(null);
    queryClient.invalidateQueries({ queryKey: queryKeys.sources });
    queryClient.invalidateQueries({ queryKey: queryKeys.source(sourceId) });
    queryClient.invalidateQueries({ queryKey: ["insights"] });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId, taskQuery.data]);

  async function check() {
    setIsStarting(true);
    try {
      const task = await runSource(sourceId);
      setTaskId(task.task_id);
    } catch (error) {
      toast.error(getApiErrorMessage(error));
    } finally {
      setIsStarting(false);
    }
  }

  const isChecking =
    isStarting || (Boolean(taskId) && !TERMINAL_STATES.has(taskQuery.data?.state || ""));

  return { check, isChecking, progress: taskQuery.data?.progress || null };
}
