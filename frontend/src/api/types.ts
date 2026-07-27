export interface ApiResponse<T = unknown> {
  success: boolean;
  data: T;
  error?: string;
}

export interface Project {
  id: number;
  name: string;
  url: string;
  description: string;
  is_active: number;
  created_at: string;
}

export interface TestSuite {
  id: number;
  project_id: number;
  name: string;
  description: string;
  tags: string;
  test_type: string;
  created_at: string;
}

export interface TestCase {
  id: number;
  suite_id: number;
  name: string;
  file_path: string;
  function_name: string;
  tags: string;
  priority: string;
  timeout: number;
  created_at: string;
  updated_at: string;
}

export interface TestRun {
  id: number;
  project_id: number;
  trigger_type: string;
  trigger_user: string;
  git_commit: string;
  git_branch: string;
  status: string;
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  duration_ms: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface TestResult {
  id: number;
  run_id: number;
  case_id: number | null;
  case_name: string;
  suite_name: string;
  status: string;
  duration_ms: number;
  error_message: string | null;
  stack_trace: string | null;
  screenshot_path: string | null;
  retry_count: number;
  started_at: string | null;
  finished_at: string | null;
}

export interface DashboardSummary {
  total_cases: number;
  latest_run_status: string | null;
  pass_rate: number;
  total_runs: number;
}

export interface TrendItem {
  id: number;
  created_at: string;
  status: string;
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  pass_rate: number;
}
