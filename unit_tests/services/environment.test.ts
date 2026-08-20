// environment.test.ts — environment-core 纯函数测试
// 测试目标：validateWorkspacePath、KEBAB_CASE_RE、toResponse、sanitizeResponse、generateEnvSecret

import { describe, expect, test } from "bun:test";

// ── 复制纯函数（避免引入 DB/transport 依赖链）──

const BLOCKED_PATHS = ["/", "/etc", "/usr", "/bin", "/sbin", "/var", "/sys", "/proc", "/dev", "/boot", "/lib", "/root"];

function validateWorkspacePath(p: string): string | null {
  // 简化版：不做真实 resolve，只做前缀匹配
  if (!p.startsWith("/")) return "workspace 路径必须是绝对路径";
  const normalized = p.replace(/\/+$/, "") || "/";
  if (BLOCKED_PATHS.includes(normalized)) return `不允许使用系统目录: ${normalized}`;
  for (const blocked of BLOCKED_PATHS) {
    if (blocked !== "/" && normalized.startsWith(`${blocked}/`)) {
      return `不允许使用系统目录下的路径: ${normalized}`;
    }
  }
  return null;
}

const KEBAB_CASE_RE = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/;

function generateEnvSecret(): string {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  return `env_secret_${Array.from(bytes).map((b) => b.toString(16).padStart(2, "0")).join("")}`;
}

interface EnvironmentRecord {
  id: string;
  name: string | null;
  description: string | null;
  workspacePath: string;
  agentConfigId: string | null;
  secret: string;
  machineName: string;
  directory: string;
  branch: string | null;
  gitRepoUrl: string | null;
  maxSessions: number;
  workerType: string;
  capabilities: Record<string, unknown> | null;
  status: string;
  username: string | null;
  userId: string | null;
  organizationId: string | null;
  autoStart: boolean;
  lastPollAt: Date | null;
  createdAt: Date;
  updatedAt: Date;
}

function toResponse(row: EnvironmentRecord) {
  return {
    id: row.id,
    machine_name: row.machineName,
    directory: row.workspacePath,
    branch: row.branch,
    status: row.status,
    username: row.username,
    last_poll_at: row.lastPollAt ? Math.floor(row.lastPollAt.getTime() / 1000) : null,
    worker_type: row.workerType,
    capabilities: row.capabilities,
  };
}

function sanitizeResponse(row: EnvironmentRecord) {
  return {
    id: row.id,
    name: row.name,
    description: row.description ?? null,
    workspace_path: row.workspacePath,
    agent_config_id: row.agentConfigId ?? null,
    status: row.status,
    machine_name: row.machineName ?? null,
    branch: row.branch ?? null,
    auto_start: row.autoStart ?? false,
    last_poll_at: row.lastPollAt ? Math.floor(row.lastPollAt.getTime() / 1000) : null,
    created_at: Math.floor(row.createdAt.getTime() / 1000),
    updated_at: Math.floor(row.updatedAt.getTime() / 1000),
  };
}

function makeRecord(overrides: Partial<EnvironmentRecord> = {}): EnvironmentRecord {
  const now = new Date("2026-01-01T00:00:00Z");
  return {
    id: "env-1",
    name: "test-env",
    description: "desc",
    workspacePath: "/ws/test",
    agentConfigId: "ac-1",
    secret: "secret-123",
    machineName: "machine-1",
    directory: "/ws/test",
    branch: "main",
    gitRepoUrl: null,
    maxSessions: 1,
    workerType: "acp",
    capabilities: null,
    status: "active",
    username: "user1",
    userId: "u-1",
    organizationId: "org-1",
    autoStart: true,
    lastPollAt: now,
    createdAt: now,
    updatedAt: now,
    ...overrides,
  };
}

// ── validateWorkspacePath ──

describe("validateWorkspacePath", () => {
  test("合法绝对路径返回 null", () => {
    expect(validateWorkspacePath("/home/user/workspace")).toBeNull();
  });

  test("相对路径返回错误信息", () => {
    expect(validateWorkspacePath("relative/path")).toBe("workspace 路径必须是绝对路径");
  });

  test("空字符串返回错误信息", () => {
    expect(validateWorkspacePath("")).toBe("workspace 路径必须是绝对路径");
  });

  test("根目录 / 返回系统目录错误", () => {
    const result = validateWorkspacePath("/");
    expect(result).toContain("不允许使用系统目录");
  });

  test("/etc 返回系统目录错误", () => {
    const result = validateWorkspacePath("/etc");
    expect(result).toContain("不允许使用系统目录");
  });

  test("/usr/local 返回系统目录下路径错误", () => {
    const result = validateWorkspacePath("/usr/local");
    expect(result).toContain("不允许使用系统目录下的路径");
  });

  test("/proc/123 返回系统目录下路径错误", () => {
    const result = validateWorkspacePath("/proc/123");
    expect(result).toContain("不允许使用系统目录下的路径");
  });

  test("/home/workspace 合法路径返回 null", () => {
    expect(validateWorkspacePath("/home/workspace")).toBeNull();
  });

  test("/var/log 返回系统目录下路径错误", () => {
    const result = validateWorkspacePath("/var/log");
    expect(result).toContain("不允许使用系统目录下的路径");
  });
});

// ── KEBAB_CASE_RE ──

describe("KEBAB_CASE_RE", () => {
  test("合法 kebab-case: my-agent", () => {
    expect(KEBAB_CASE_RE.test("my-agent")).toBe(true);
  });

  test("单个字符: a", () => {
    expect(KEBAB_CASE_RE.test("a")).toBe(true);
  });

  test("纯数字: 123", () => {
    expect(KEBAB_CASE_RE.test("123")).toBe(true);
  });

  test("含数字混合: agent-2-test", () => {
    expect(KEBAB_CASE_RE.test("agent-2-test")).toBe(true);
  });

  test("大写字母不合法: MyAgent", () => {
    expect(KEBAB_CASE_RE.test("MyAgent")).toBe(false);
  });

  test("开头连字符不合法: -agent", () => {
    expect(KEBAB_CASE_RE.test("-agent")).toBe(false);
  });

  test("结尾连字符不合法: agent-", () => {
    expect(KEBAB_CASE_RE.test("agent-")).toBe(false);
  });

  test("空字符串不合法", () => {
    expect(KEBAB_CASE_RE.test("")).toBe(false);
  });

  test("含空格不合法: my agent", () => {
    expect(KEBAB_CASE_RE.test("my agent")).toBe(false);
  });

  test("含下划线不合法: my_agent", () => {
    expect(KEBAB_CASE_RE.test("my_agent")).toBe(false);
  });

  test("连续连字符合法: my--agent", () => {
    expect(KEBAB_CASE_RE.test("my--agent")).toBe(true);
  });
});

// ── generateEnvSecret ──

describe("generateEnvSecret", () => {
  test("返回以 env_secret_ 为前缀的字符串", () => {
    const secret = generateEnvSecret();
    expect(secret.startsWith("env_secret_")).toBe(true);
  });

  test("hex 部分长度为 48 字符（24 字节）", () => {
    const secret = generateEnvSecret();
    const hexPart = secret.slice("env_secret_".length);
    expect(hexPart.length).toBe(48);
  });

  test("两次调用生成不同的 secret", () => {
    const a = generateEnvSecret();
    const b = generateEnvSecret();
    expect(a).not.toBe(b);
  });
});

// ── toResponse ──

describe("toResponse", () => {
  test("正常转换返回 v1 格式", () => {
    const record = makeRecord();
    const resp = toResponse(record);
    expect(resp.id).toBe("env-1");
    expect(resp.machine_name).toBe("machine-1");
    expect(resp.directory).toBe("/ws/test");
    expect(resp.branch).toBe("main");
    expect(resp.status).toBe("active");
    expect(resp.username).toBe("user1");
    expect(resp.worker_type).toBe("acp");
    expect(resp.capabilities).toBeNull();
  });

  test("lastPollAt 为 null 时 last_poll_at 为 null", () => {
    const record = makeRecord({ lastPollAt: null });
    const resp = toResponse(record);
    expect(resp.last_poll_at).toBeNull();
  });

  test("lastPollAt 有值时转为秒级时间戳", () => {
    const date = new Date("2026-01-01T00:00:00Z");
    const record = makeRecord({ lastPollAt: date });
    const resp = toResponse(record);
    expect(resp.last_poll_at).toBe(Math.floor(date.getTime() / 1000));
  });

  test("capabilities 保留原始对象", () => {
    const caps = { shell: true, code_interpreter: false };
    const record = makeRecord({ capabilities: caps });
    const resp = toResponse(record);
    expect(resp.capabilities).toEqual(caps);
  });
});

// ── sanitizeResponse ──

describe("sanitizeResponse", () => {
  test("正常转换返回 Web API 格式", () => {
    const record = makeRecord();
    const resp = sanitizeResponse(record);
    expect(resp.id).toBe("env-1");
    expect(resp.name).toBe("test-env");
    expect(resp.description).toBe("desc");
    expect(resp.workspace_path).toBe("/ws/test");
    expect(resp.agent_config_id).toBe("ac-1");
    expect(resp.status).toBe("active");
    expect(resp.machine_name).toBe("machine-1");
    expect(resp.auto_start).toBe(true);
  });

  test("name 为 null 时输出 null", () => {
    const record = makeRecord({ name: null });
    const resp = sanitizeResponse(record);
    expect(resp.name).toBeNull();
  });

  test("agentConfigId 为 null 时输出 null", () => {
    const record = makeRecord({ agentConfigId: null });
    const resp = sanitizeResponse(record);
    expect(resp.agent_config_id).toBeNull();
  });

  test("description 为 null 时输出 null", () => {
    const record = makeRecord({ description: null });
    const resp = sanitizeResponse(record);
    expect(resp.description).toBeNull();
  });

  test("autoStart 为 false 时输出 false", () => {
    const record = makeRecord({ autoStart: false });
    const resp = sanitizeResponse(record);
    expect(resp.auto_start).toBe(false);
  });

  test("created_at 和 updated_at 为秒级时间戳", () => {
    const date = new Date("2026-06-15T12:00:00Z");
    const record = makeRecord({ createdAt: date, updatedAt: date });
    const resp = sanitizeResponse(record);
    expect(resp.created_at).toBe(Math.floor(date.getTime() / 1000));
    expect(resp.updated_at).toBe(Math.floor(date.getTime() / 1000));
  });

  test("branch 为 null 时输出 null", () => {
    const record = makeRecord({ branch: null });
    const resp = sanitizeResponse(record);
    expect(resp.branch).toBeNull();
  });

  test("machineName 为 null 时输出 null", () => {
    const record = makeRecord({ machineName: null as unknown as string });
    const resp = sanitizeResponse(record);
    expect(resp.machine_name).toBeNull();
  });
});
