import { useQueryClient, useQuery } from "@tanstack/react-query";
import * as React from "react";
import { toast } from "sonner";

import { getApiErrorMessage, getTaskStatus, runSource, taskHasFailedResult } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

const TERMINAL_STATES = new Set(["SUCCESS", "FAILURE", "REVOKED"]);

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

    const failed = state !== "SUCCESS" || taskHasFailedResult(data);
    toast[failed ? "error" : "success"](failed ? "Check failed." : "Check complete.");
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

  return { check, isChecking };
}
