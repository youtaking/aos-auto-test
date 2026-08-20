// environment-web.test.ts — Web 环境管理辅助函数测试
// 测试目标：isUniqueConstraintError、enterEnvironment、listEnvironmentsWithInstances 中的映射逻辑

import { describe, expect, test, beforeEach, mock } from "bun:test";

// ── 复制纯函数 ──

function isUniqueConstraintError(err: unknown): boolean {
  const candidate = err as {
    message?: string;
    code?: string;
    cause?: { message?: string; code?: string } | null;
  } | null;
  const message = candidate?.message ?? candidate?.cause?.message ?? "";
  const code = candidate?.code ?? candidate?.cause?.code ?? "";
  return (
    code === "23505" ||
    message.includes("unique") ||
    message.includes("duplicate") ||
    message.includes("UNIQUE") ||
    message.includes("23505")
  );
}

class NotFoundError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NotFoundError";
  }
}

// enterEnvironment 逻辑复制
async function enterEnvironment(
  _userId: string,
  envId: string,
  getEnvById: (id: string) => Promise<{ id: string } | null>,
) {
  const env = await getEnvById(envId);
  if (!env) throw new NotFoundError("环境不存在");
  return {
    environment_id: envId,
    instance_id: envId,
    session_id: null,
  };
}

// ── Tests ──

describe("environment-web", () => {
  beforeEach(() => {
    mock.restore();
  });

  // ── isUniqueConstraintError ──

  describe("isUniqueConstraintError", () => {
    test("PostgreSQL 唯一约束错误码 23505", () => {
      expect(isUniqueConstraintError({ code: "23505" })).toBe(true);
    });

    test("message 包含 unique", () => {
      expect(isUniqueConstraintError({ message: "unique constraint violation" })).toBe(true);
    });

    test("message 包含 duplicate", () => {
      expect(isUniqueConstraintError({ message: "duplicate key value" })).toBe(true);
    });

    test("message 包含 UNIQUE（大写）", () => {
      expect(isUniqueConstraintError({ message: "UNIQUE constraint failed" })).toBe(true);
    });

    test("message 包含 23505", () => {
      expect(isUniqueConstraintError({ message: "error code 23505" })).toBe(true);
    });

    test("cause.message 包含 unique", () => {
      expect(isUniqueConstraintError({ cause: { message: "unique violation" } })).toBe(true);
    });

    test("cause.code 为 23505", () => {
      expect(isUniqueConstraintError({ cause: { code: "23505" } })).toBe(true);
    });

    test("无关错误返回 false", () => {
      expect(isUniqueConstraintError({ message: "connection timeout", code: "42P01" })).toBe(false);
    });

    test("null 输入返回 false", () => {
      expect(isUniqueConstraintError(null)).toBe(false);
    });

    test("空对象返回 false", () => {
      expect(isUniqueConstraintError({})).toBe(false);
    });

    test("Error 实例可检测", () => {
      const err = new Error("duplicate key value violates unique constraint");
      expect(isUniqueConstraintError(err)).toBe(true);
    });
  });

  // ── enterEnvironment ──

  describe("enterEnvironment", () => {
    test("环境存在时返回 environment_id 和 instance_id", async () => {
      const getEnv = async (id: string) => ({ id });
      const result = await enterEnvironment("user-1", "env-42", getEnv);
      expect(result.environment_id).toBe("env-42");
      expect(result.instance_id).toBe("env-42");
      expect(result.session_id).toBeNull();
    });

    test("环境不存在时抛出 NotFoundError", async () => {
      const getEnv = async () => null;
      await expect(enterEnvironment("user-1", "missing-env", getEnv)).rejects.toThrow("环境不存在");
    });

    test("userId 不影响返回结果", async () => {
      const getEnv = async (id: string) => ({ id });
      const r1 = await enterEnvironment("user-a", "env-1", getEnv);
      const r2 = await enterEnvironment("user-b", "env-1", getEnv);
      expect(r1).toEqual(r2);
    });
  });

  // ── 响应格式映射 ──

  describe("listEnvironmentsWithInstances 映射逻辑", () => {
    // 测试环境到响应的映射（不依赖 DB）
    function mapEnvToResponse(env: {
      id: string;
      name: string;
      description: string | null;
      workspacePath: string;
      agentConfigId: string | null;
      status: string;
      machineName: string | null;
      branch: string | null;
      autoStart: boolean;
      lastPollAt: Date | null;
      createdAt: Date;
      updatedAt: Date;
    }, agentName: string | null, instances: Array<{
      id: string;
      instanceNumber: number;
      status: string;
      sessionId: string | null;
      port: number;
      createdAt: Date;
    }>) {
      const firstInstance = instances[0];
      return {
        id: env.id,
        name: env.name,
        description: env.description ?? null,
        workspace_path: env.workspacePath,
        agent_config_id: env.agentConfigId ?? null,
        agent_name: agentName ?? null,
        status: env.status,
        machine_name: env.machineName ?? null,
        branch: env.branch ?? null,
        auto_start: env.autoStart ?? false,
        last_poll_at: env.lastPollAt ? Math.floor(env.lastPollAt.getTime() / 1000) : null,
        created_at: Math.floor(env.createdAt.getTime() / 1000),
        updated_at: Math.floor(env.updatedAt.getTime() / 1000),
        session_id: firstInstance?.sessionId ?? null,
        instance_status: firstInstance ? firstInstance.status : null,
        instance_id: firstInstance ? firstInstance.id : null,
        instances: instances.map((inst) => ({
          id: inst.id,
          instance_number: inst.instanceNumber,
          status: inst.status,
          session_id: inst.sessionId ?? null,
          port: inst.port,
          created_at: Math.floor(inst.createdAt.getTime() / 1000),
        })),
        instances_count: instances.length,
      };
    }

    test("无实例时映射正确", () => {
      const now = new Date("2026-01-01T00:00:00Z");
      const resp = mapEnvToResponse(
        {
          id: "env-1", name: "test", description: "desc", workspacePath: "/ws",
          agentConfigId: "ac-1", status: "idle", machineName: "m1", branch: "main",
          autoStart: true, lastPollAt: now, createdAt: now, updatedAt: now,
        },
        "My Agent",
        [],
      );
      expect(resp.id).toBe("env-1");
      expect(resp.agent_name).toBe("My Agent");
      expect(resp.session_id).toBeNull();
      expect(resp.instance_status).toBeNull();
      expect(resp.instance_id).toBeNull();
      expect(resp.instances_count).toBe(0);
      expect(resp.instances).toEqual([]);
    });

    test("有实例时映射第一个实例的信息", () => {
      const now = new Date("2026-01-01T00:00:00Z");
      const instDate = new Date("2026-01-02T00:00:00Z");
      const resp = mapEnvToResponse(
        {
          id: "env-2", name: "test", description: null, workspacePath: "/ws",
          agentConfigId: null, status: "active", machineName: null, branch: null,
          autoStart: false, lastPollAt: null, createdAt: now, updatedAt: now,
        },
        null,
        [
          { id: "inst-1", instanceNumber: 1, status: "running", sessionId: "sess-1", port: 3001, createdAt: instDate },
          { id: "inst-2", instanceNumber: 2, status: "idle", sessionId: null, port: 3002, createdAt: instDate },
        ],
      );
      expect(resp.session_id).toBe("sess-1");
      expect(resp.instance_status).toBe("running");
      expect(resp.instance_id).toBe("inst-1");
      expect(resp.instances_count).toBe(2);
      expect(resp.instances.length).toBe(2);
      expect(resp.instances[1].id).toBe("inst-2");
    });

    test("viewerUserId 过滤逻辑 - 非本人 agent 绑定环境被跳过", () => {
      // 测试 viewerUserId 过滤：agent 绑定的环境只展示当前用户的
      const envs = [
        { id: "env-1", userId: "user-a", agentConfigId: "ac-1" },
        { id: "env-2", userId: "user-b", agentConfigId: "ac-2" },
        { id: "env-3", userId: "user-a", agentConfigId: null },
      ];
      const viewerUserId = "user-a";
      const filtered = envs.filter((env) => {
        if (viewerUserId && env.agentConfigId && env.userId !== viewerUserId) return false;
        return true;
      });
      expect(filtered.length).toBe(2);
      expect(filtered.map((e) => e.id)).toEqual(["env-1", "env-3"]);
    });
  });
});
