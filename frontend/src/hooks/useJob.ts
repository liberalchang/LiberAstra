import { useQuery } from "@tanstack/react-query";

import { api, TERMINAL_STATUSES, type JobOut } from "@/api/client";

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
