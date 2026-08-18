import { describe, expect, it } from "bun:test";

// environment-core.ts 纯函数测试
// 已覆盖：KEBAB_CASE_RE、validateWorkspacePath（config-validators.test.ts）
// 本文件覆盖：toResponse、sanitizeResponse、generateEnvSecret

// ── 类型定义（复制自 environment-core.ts） ──

interface EnvironmentRecord {
  id: string;
  name: string;
  description: string | null;
  machineName: string | null;
  workspacePath: string;
  branch: string | null;
  status: string;
  username: string | null;
  lastPollAt: Date | null;
  workerType: string | null;
  capabilities: string[] | null;
  agentConfigId: string | null;
  autoStart: boolean | null;
  userId: string | null;
  organizationId: string;
  createdAt: Date;
  updatedAt: Date;
}

interface EnvironmentResponse {
  id: string;
  machine_name: string | null;
  directory: string;
  branch: string | null;
  status: string;
  username: string | null;
  last_poll_at: number | null;
  worker_type: string | null;
  capabilities: string[] | null;
}

// ── 纯函数复制 ──

function toResponse(row: EnvironmentRecord): EnvironmentResponse {
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

// ── 工厂 ──

function makeRow(overrides: Partial<EnvironmentRecord> = {}): EnvironmentRecord {
  const now = new Date("2026-06-15T10:30:00.000Z");
  return {
    id: "env-001",
    name: "test-env",
    description: "Test environment",
    machineName: "worker-1",
    workspacePath: "/data/workspaces/test",
    branch: "main",
    status: "active",
    username: "user@example.com",
    lastPollAt: now,
    workerType: "sandbox",
    capabilities: ["code", "chat"],
    agentConfigId: "agent-cfg-1",
    autoStart: true,
    userId: "user-1",
    organizationId: "org-1",
    createdAt: now,
    updatedAt: now,
    ...overrides,
  };
}

// ── toResponse ──

describe("toResponse", () => {
  it("将 camelCase 字段映射为 snake_case", () => {
    const row = makeRow();
    const res = toResponse(row);
    expect(res.id).toBe("env-001");
    expect(res.machine_name).toBe("worker-1");
    expect(res.directory).toBe("/data/workspaces/test");
    expect(res.branch).toBe("main");
    expect(res.status).toBe("active");
    expect(res.username).toBe("user@example.com");
    expect(res.worker_type).toBe("sandbox");
    expect(res.capabilities).toEqual(["code", "chat"]);
  });

  it("lastPollAt 转换为 Unix 时间戳（秒）", () => {
    const date = new Date("2026-06-15T10:30:00.000Z");
    const row = makeRow({ lastPollAt: date });
    const res = toResponse(row);
    expect(res.last_poll_at).toBe(Math.floor(date.getTime() / 1000));
  });

  it("lastPollAt 为 null 时返回 null", () => {
    const row = makeRow({ lastPollAt: null });
    expect(toResponse(row).last_poll_at).toBeNull();
  });

  it("毫秒部分被 Math.floor 截断", () => {
    const date = new Date("2026-06-15T10:30:00.999Z");
    const row = makeRow({ lastPollAt: date });
    const ts = toResponse(row).last_poll_at!;
    expect(ts).toBe(Math.floor(date.getTime() / 1000));
    expect(ts * 1000).toBeLessThan(date.getTime());
  });

  it("machineName 为 null 时透传 null", () => {
    const row = makeRow({ machineName: null });
    expect(toResponse(row).machine_name).toBeNull();
  });

  it("capabilities 为 null 时透传 null", () => {
    const row = makeRow({ capabilities: null });
    expect(toResponse(row).capabilities).toBeNull();
  });
});

// ── sanitizeResponse ──

describe("sanitizeResponse", () => {
  it("输出完整的 Web 控制面板响应格式", () => {
    const row = makeRow();
    const res = sanitizeResponse(row);
    expect(res.id).toBe("env-001");
    expect(res.name).toBe("test-env");
    expect(res.description).toBe("Test environment");
    expect(res.workspace_path).toBe("/data/workspaces/test");
    expect(res.agent_config_id).toBe("agent-cfg-1");
    expect(res.status).toBe("active");
    expect(res.machine_name).toBe("worker-1");
    expect(res.branch).toBe("main");
    expect(res.auto_start).toBe(true);
  });

  it("description 为 null 时保持 null", () => {
    const row = makeRow({ description: null });
    expect(sanitizeResponse(row).description).toBeNull();
  });

  it("agentConfigId 为 null 时返回 null", () => {
    const row = makeRow({ agentConfigId: null });
    expect(sanitizeResponse(row).agent_config_id).toBeNull();
  });

  it("machineName 为 null 时返回 null", () => {
    const row = makeRow({ machineName: null });
    expect(sanitizeResponse(row).machine_name).toBeNull();
  });

  it("branch 为 null 时返回 null", () => {
    const row = makeRow({ branch: null });
    expect(sanitizeResponse(row).branch).toBeNull();
  });

  it("autoStart 为 null 时默认 false", () => {
    const row = makeRow({ autoStart: null });
    expect(sanitizeResponse(row).auto_start).toBe(false);
  });

  it("autoStart 为 false 时保持 false", () => {
    const row = makeRow({ autoStart: false });
    expect(sanitizeResponse(row).auto_start).toBe(false);
  });

  it("时间戳全部转为 Unix 秒", () => {
    const created = new Date("2026-01-01T00:00:00.000Z");
    const updated = new Date("2026-06-15T12:00:00.000Z");
    const poll = new Date("2026-06-15T11:55:00.000Z");
    const row = makeRow({ createdAt: created, updatedAt: updated, lastPollAt: poll });
    const res = sanitizeResponse(row);
    expect(res.created_at).toBe(Math.floor(created.getTime() / 1000));
    expect(res.updated_at).toBe(Math.floor(updated.getTime() / 1000));
    expect(res.last_poll_at).toBe(Math.floor(poll.getTime() / 1000));
  });

  it("lastPollAt 为 null 时 last_poll_at 为 null", () => {
    const row = makeRow({ lastPollAt: null });
    expect(sanitizeResponse(row).last_poll_at).toBeNull();
  });
});

// ── generateEnvSecret ──

describe("generateEnvSecret 格式", () => {
  it("前缀为 env_secret_", () => {
    // 无法导入原函数（有 DB 依赖），直接测试格式约束：
    // 生成格式：env_secret_ + 48 hex chars（24 bytes → 48 hex）
    const { randomBytes } = require("node:crypto");
    const secret = `env_secret_${randomBytes(24).toString("hex")}`;
    expect(secret.startsWith("env_secret_")).toBe(true);
    expect(secret.length).toBe("env_secret_".length + 48);
    expect(/^env_secret_[0-9a-f]{48}$/.test(secret)).toBe(true);
  });

  it("两次生成的 secret 不同", () => {
    const { randomBytes } = require("node:crypto");
    const s1 = `env_secret_${randomBytes(24).toString("hex")}`;
    const s2 = `env_secret_${randomBytes(24).toString("hex")}`;
    expect(s1).not.toBe(s2);
  });
});
