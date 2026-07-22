import { get, post } from "./client";
import type { TestRun, TestResult } from "./types";

export const listRuns = (params?: { project_id?: number; status?: string; page?: number }) =>
  get<TestRun[]>("/runs", params);
export const getRun = (id: number) => get<TestRun>(`/runs/${id}`);
export const getRunResults = (runId: number) => get<TestResult[]>(`/runs/${runId}/results`);
export const triggerRun = (projectId: number, triggerType = "manual") =>
  post<TestRun>(`/runs?project_id=${projectId}&trigger_type=${triggerType}`);
