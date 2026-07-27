import { get, post } from "./client";
import type { TestRun, TestResult } from "./types";

export interface ApiTestCase {
  id: number;
  suite_id: number;
  name: string;
  file_path: string;
  function_name: string;
  tags: string;
  priority: string;
  timeout: number;
}

export interface ApiRunDetail {
  run: TestRun;
  results: TestResult[];
}

export const listApiCases = (params?: { module?: string; priority?: string }) =>
  get<ApiTestCase[]>("/api-tests/cases", params);

export const triggerApiRun = (projectId: number, caseIds?: number[]) => {
  const params = new URLSearchParams({ project_id: String(projectId) });
  if (caseIds && caseIds.length > 0) {
    params.set("case_ids", caseIds.join(","));
  }
  return post<TestRun>(`/api-tests/run?${params}`);
};

export const listApiRuns = (page = 1, pageSize = 20) =>
  get<TestRun[]>("/api-tests/runs", { page, page_size: pageSize });

export const getApiRun = (id: number) =>
  get<ApiRunDetail>(`/api-tests/runs/${id}`);
