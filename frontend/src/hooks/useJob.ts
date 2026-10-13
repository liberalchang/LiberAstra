import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ApiError, api, TERMINAL_STATUSES, type JobOut } from "@/api/client";

const JOB_KEY_PREFIX = "liberastra-job:";

function readStoredJobId(scope: string): string | null {
  try {
    return sessionStorage.getItem(JOB_KEY_PREFIX + scope);
  } catch {
    return null;
  }
}

function writeStoredJobId(scope: string, id: string | null) {
  try {
    const key = JOB_KEY_PREFIX + scope;
    if (id) sessionStorage.setItem(key, id);
    else sessionStorage.removeItem(key);
  } catch {
    /* 隐私模式可能禁用 sessionStorage */
  }
}

/** 轮询 Job 直到终态。jobId 为 null 时禁用。 */
export function useJob(jobId: string | null) {
  return useQuery<JobOut>({
    queryKey: ["job", jobId],
    queryFn: () => api.getJob(jobId!),
    enabled: jobId != null,
    refetchInterval: (query) =>
      query.state.data && TERMINAL_STATUSES.includes(query.state.data.status) ? false : 800,
  });
}

/** 把当前页的任务编号记在 sessionStorage，离开页面再回来仍能接着显示进度和结果。 */
export function useTrackedJob(scope: string) {
  const [activeScope, setActiveScope] = useState(scope);
  const [jobId, setJobIdState] = useState<string | null>(() => readStoredJobId(scope));
  if (scope !== activeScope) {
    setActiveScope(scope);
    setJobIdState(readStoredJobId(scope));
  }

  const setJobId = (id: string | null) => {
    setJobIdState(id);
    writeStoredJobId(scope, id);
  };

  const query = useJob(jobId);
  useEffect(() => {
    if (!(query.error instanceof ApiError) || query.error.status !== 404) return;
    setJobIdState(null);
    writeStoredJobId(scope, null);
  }, [query.error, scope]);

  return { job: query.data, setJobId };
}
