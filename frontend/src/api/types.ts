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

export interface AuthConfig {
  id: number;
  name: string;
  ui_test_email: string;
  ui_test_password: string;
  api_test_email: string;
  api_test_password: string;
  open_api_key: string;
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
  pipeline_id: number | null;
  pr_id: number | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  collection_ids: number[] | null;
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

export interface LLMConfig {
  id: number;
  name: string;
  provider: string;
  base_url: string;
  api_key: string;
  model: string;
  is_active: number;
  created_at: string;
}

export interface ZentaoConfig {
  id: number;
  name: string;
  base_url: string;
  username: string;
  password: string;
  product_id: number;
  is_active: number;
  created_at: string;
}

export interface Pipeline {
  id: number;
  pr_id: number | null;  // staging 时为 null
  pr_title: string;
  commit_sha: string;
  branch: string;
  repo_url: string;
  author: string;
  status: string;
  docker_image: string;
  target_url: string;
  rcs_url: string;
  run_id: number | null;
  build_info: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  test_total: number;
  test_passed: number;
  test_failed: number;
  test_skipped: number;
}

export interface CIConfig {
  id: number;
  timeout_minutes: number;
  max_queue_size: number;
  auth_token: string;
  run_api_tests: number;
  run_e2e_p0: number;
  run_e2e_all: number;
  collection_ids: number[] | null;
  staging_collection_ids: number[] | null;
  branch_e2e_collection_ids: number[] | null;
  created_at: string;
  updated_at: string;
}

export interface Collection {
  id: number;
  project_id: number;
  name: string;
  description: string;
  case_ids: number[];
  created_at: string;
  updated_at: string;
}

export interface UnitTestCaseInfo {
  id: number;
  test_name: string;
  full_name: string;
}

export interface UnitTestDescribe {
  name: string;
  tests: UnitTestCaseInfo[];
}

export interface UnitTestFile {
  file_path: string;
  describes: UnitTestDescribe[];
}

export interface UnitTestResult {
  id: number;
  test_case_id: number | null;
  name: string;
  classname: string;
  status: string;
  duration_ms: number;
  failure_message: string | null;
  ran_at: string | null;
}

export interface UnitTestSummary {
  status: string;  // not_run / running / completed / failed
  run_id: number | null;
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  duration_ms: number;
  started_at: string | null;
  results: UnitTestResult[];
}
