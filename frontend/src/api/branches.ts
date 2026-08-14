import { get, post, del } from "./client";

export interface BranchInfo {
  branch_name: string;
  last_commit_sha: string;
  pr_number: number | null;
  dev_status: string;
  case_status: string;
  discovered_at: string | null;
  updated_at: string | null;
  has_dir: boolean;
}

export interface CanGenerateResponse {
  can_generate: boolean;
  autotest_dir: string | null;
}

export interface PromoteReport {
  branch_name: string;
  new_api_files: string[];
  new_unit_files: string[];
}

export async function listBranches(): Promise<BranchInfo[]> {
  return get<BranchInfo[]>("/branches");
}

export async function createBranch(branchName: string) {
  return post<{ branch_name: string }>("/branches", { branch_name: branchName });
}

export async function deleteBranch(branchName: string) {
  return del<{ branch_name: string; dir_deleted: boolean }>(`/branches/delete?branch_name=${encodeURIComponent(branchName)}`);
}

export async function resetBranch(branchName: string) {
  return post<{ branch_name: string; api_suites_copied: boolean; unit_tests_copied: boolean }>(
    "/branches/reset", { branch_name: branchName }
  );
}

export async function promoteBranch(branchName: string) {
  return post<PromoteReport>("/branches/promote", { branch_name: branchName });
}

export async function pollNow() {
  return post<Record<string, unknown>>("/branches/poll-now");
}

export async function getTrackers() {
  return get<Record<string, unknown>[]>("/branches/trackers");
}

export interface BranchCaseFile {
  name: string;
  path: string;
  size: number;
  modified: number;
}

export interface BranchCases {
  branch_name: string;
  api_suites: BranchCaseFile[];
  unit_tests: BranchCaseFile[];
}

export async function listBranchCases(branchName: string) {
  return get<BranchCases>(`/branches/cases?branch_name=${encodeURIComponent(branchName)}`);
}

export async function canGenerate() {
  return get<CanGenerateResponse>("/branches/can-generate");
}

export async function launchGenerate(branchName: string, testType: string = "api") {
  return post<{ launched: boolean }>("/branches/generate", { branch_name: branchName, test_type: testType });
}
