import { get, post } from "./client";
import type { TestRun, TestResult } from "./types";

export const listRuns = (params?: { project_id?: number; status?: string; page?: number }) =>
  get<TestRun[]>("/runs", params);
export const getRun = (id: number) => get<TestRun>(`/runs/${id}`);
export const getRunResults = (runId: number) => get<TestResult[]>(`/runs/${runId}/results`);
export const getRunLogs = (runId: number) => get<string[]>(`/runs/${runId}/logs`);
export const cancelRun = (id: number) => post<{ cancelled: boolean; killed_process: boolean }>(`/runs/${id}/cancel`);
export const getRunMdReport = (runId: number) =>
  fetch(`/api/runs/${runId}/md-report`).then((r) => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.text();
  });
export const triggerRun = (
  projectId: number,
  triggerType = "manual",
  headed = false,
  stepDelay = 0,
  caseIds?: number[],
) => {
  const params = new URLSearchParams({
    project_id: String(projectId),
    trigger_type: triggerType,
    headed: String(headed),
    step_delay: String(stepDelay),
  });
  if (caseIds && caseIds.length > 0) {
    params.set("case_ids", caseIds.join(","));
  }
  return post<TestRun>(`/runs?${params}`);
};
