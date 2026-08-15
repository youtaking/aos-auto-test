import { get, post, del } from "./client";
import type { TestRun, TestResult } from "./types";

export const listRuns = (params?: { project_id?: number; status?: string; trigger_type?: string; page?: number }) =>
  get<TestRun[]>("/runs", params);
export const getRun = (id: number) => get<TestRun>(`/runs/${id}`);
export const getRunResults = (runId: number) => get<TestResult[]>(`/runs/${runId}/results`);
export const getRunLogs = (runId: number) => get<string[]>(`/runs/${runId}/logs`);
export const cancelRun = (id: number) => post<{ cancelled: boolean; killed_process: boolean }>(`/runs/${id}/cancel`);
export const deleteRun = (id: number) => del<{ deleted: number }>(`/runs/${id}`);
export const batchDeleteRuns = (runIds: number[]) =>
  post<{ deleted: number[]; count: number }>("/runs/batch-delete", { run_ids: runIds });

export interface SingleTestResult {
  status: string;
  duration_ms: number;
  error_message: string | null;
  output: string;
}

export const runSingleTest = (caseId?: number, caseName?: string, headed = true) => {
  const params = new URLSearchParams({ headed: String(headed) });
  if (caseId) params.set("case_id", String(caseId));
  if (caseName) params.set("case_name", caseName);
  return post<SingleTestResult>(`/tests/run-single?${params}`);
};

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
  collectionIds?: number[],
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
  if (collectionIds && collectionIds.length > 0) {
    params.set("collection_ids", collectionIds.join(","));
  }
  return post<TestRun>(`/runs?${params}`);
};
