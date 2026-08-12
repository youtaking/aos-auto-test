import { get, post } from "./client";
import type { UnitTestFile, UnitTestSummary } from "./types";

export interface UnitTestRunResult {
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  duration_ms: number;
  exit_code: number;
  tests: {
    name: string;
    classname: string;
    status: "passed" | "failed" | "skipped";
    duration_ms: number;
    failure_message: string | null;
  }[];
}

export async function listUnitTests(branch: string = "main"): Promise<UnitTestFile[]> {
  return get<UnitTestFile[]>("/unit-tests", { branch });
}

export async function discoverUnitTests(): Promise<{ discovered: number }> {
  return post<{ discovered: number }>("/unit-tests/discover");
}

export async function runUnitTests(testIds?: number[]): Promise<UnitTestRunResult> {
  return post<UnitTestRunResult>("/unit-tests/run", { test_ids: testIds ?? [] });
}

export async function getPipelineUnitResults(pipelineId: number): Promise<UnitTestSummary> {
  return get<UnitTestSummary>(`/pipelines/${pipelineId}/unit-results`);
}
