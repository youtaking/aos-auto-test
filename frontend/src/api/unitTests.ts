import { get, post } from "./client";
import type { UnitTestFile, UnitTestSummary } from "./types";

export async function listUnitTests(): Promise<UnitTestFile[]> {
  return get<UnitTestFile[]>("/unit-tests");
}

export async function discoverUnitTests(): Promise<{ discovered: number }> {
  return post<{ discovered: number }>("/unit-tests/discover");
}

export async function getPipelineUnitResults(pipelineId: number): Promise<UnitTestSummary> {
  return get<UnitTestSummary>(`/pipelines/${pipelineId}/unit-results`);
}
