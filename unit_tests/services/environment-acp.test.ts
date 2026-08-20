// environment-acp.test.ts — ACP 环境生命周期管理测试
// 测试目标：registerEnvironment、handleAcpConnect、handleAcpRegister、handleAcpIdentify、handleAcpDisconnect 等

import { describe, expect, test, beforeEach, mock } from "bun:test";

// ── 复制核心逻辑（隔离 DB/transport 依赖）──

class NotFoundError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NotFoundError";
  }
}

class AppError extends Error {
  readonly code: string;
  readonly statusCode: number;
  constructor(message: string, code: string, statusCode: number) {
    super(message);
    this.name = "AppError";
    this.code = code;
    this.statusCode = statusCode;
  }
}

interface EnvironmentRecord {
  id: string;
  userId: string | null;
  agentConfigId: string | null;
  organizationId: string | null;
  secret: string;
  machineName: string;
  workerType: string;
  status: string;
  capabilities: Record<string, unknown> | null;
  maxSessions: number;
  lastPollAt: Date | null;
}

// 依赖注入
const _deps = {
  repo: {
    getBySecret: async (_secret: string): Promise<EnvironmentRecord | null> => null,
    getById: async (_id: string): Promise<EnvironmentRecord | null> => null,
    create: async (_params: Record<string, unknown>): Promise<EnvironmentRecord> => ({
      id: "new-env-id",
      userId: "system",
      agentConfigId: null,
      organizationId: null,
      secret: "generated-secret",
      machineName: "",
      workerType: "acp",
      status: "idle",
      capabilities: null,
      maxSessions: 1,
      lastPollAt: null,
    }),
    update: async (_id: string, _patch: Record<string, unknown>) => {},
    listActive: async (): Promise<EnvironmentRecord[]> => [],
    listActiveByUsername: async (_username: string): Promise<EnvironmentRecord[]> => [],
    delete: async (_id: string): Promise<boolean> => true,
  },
};

// ── 复制服务函数 ──

async function getEnvironmentBySecret(secret: string) {
  const env = await _deps.repo.getBySecret(secret);
  if (!env) return null;
  return {
    id: env.id,
    userId: env.userId,
    agentConfigId: env.agentConfigId,
    organizationId: env.organizationId,
    secret: env.secret,
  };
}

async function registerEnvironment(req: {
  machine_name?: string;
  directory?: string;
  branch?: string;
  max_sessions?: number;
  capabilities?: Record<string, unknown>;
  userId?: string;
  organizationId?: string;
  username?: string;
  metadata?: { worker_type?: string };
}) {
  const record = await _deps.repo.create({
    userId: req.userId ?? "system",
    organizationId: req.organizationId,
    machineName: req.machine_name,
    directory: req.directory,
    branch: req.branch,
    maxSessions: req.max_sessions,
    workerType: req.metadata?.worker_type,
    username: req.username,
    capabilities: req.capabilities,
  });
  return {
    environment_id: record.id,
    environment_secret: record.secret,
    status: record.status,
    session_id: undefined,
  };
}

async function markEnvironmentActive(envId: string): Promise<void> {
  await _deps.repo.update(envId, { status: "active", lastPollAt: new Date() });
}

async function markEnvironmentIdle(envId: string): Promise<void> {
  await _deps.repo.update(envId, { status: "idle" });
}

async function handleAcpConnect(boundEnvId: string | null): Promise<void> {
  if (boundEnvId) {
    await markEnvironmentActive(boundEnvId);
  }
}

async function handleAcpRegister(params: {
  wsId: string;
  userId: string;
  agentName: string;
  capabilities?: Record<string, unknown>;
  maxSessions?: number;
  directory?: string;
  boundEnvId: string | null;
}): Promise<{ envId: string; isNew: boolean }> {
  if (params.boundEnvId) {
    await _deps.repo.update(params.boundEnvId, {
      status: "active",
      lastPollAt: new Date(),
      capabilities: params.capabilities ?? undefined,
      maxSessions: params.maxSessions,
    });
    return { envId: params.boundEnvId, isNew: false };
  }
  const record = await _deps.repo.create({
    secret: `ws_${params.wsId}`,
    userId: params.userId,
    machineName: params.agentName,
    workerType: "acp",
    directory: params.directory,
    maxSessions: params.maxSessions,
    capabilities: params.capabilities,
  });
  return { envId: record.id, isNew: true };
}

async function handleAcpIdentify(params: {
  agentId: string;
  userId: string;
  boundEnvId: string | null;
}): Promise<{ envId: string; capabilities: Record<string, unknown> | null }> {
  if (params.boundEnvId) {
    await markEnvironmentActive(params.boundEnvId);
    const env = await _deps.repo.getById(params.boundEnvId);
    return { envId: params.boundEnvId, capabilities: env?.capabilities ?? null };
  }

  const record = await _deps.repo.getById(params.agentId);
  if (record?.workerType !== "acp") {
    throw new NotFoundError("Agent not found");
  }
  if (record.userId && record.userId !== params.userId) {
    throw new AppError("Agent not owned by you", "FORBIDDEN", 403);
  }

  await markEnvironmentActive(params.agentId);
  return { envId: record.id, capabilities: record.capabilities ?? null };
}

async function handleAcpDisconnect(agentId: string, isBound: boolean): Promise<void> {
  if (isBound) {
    await markEnvironmentIdle(agentId);
  } else {
    await _deps.repo.delete(agentId);
  }
}

// ── Tests ──

describe("environment-acp", () => {
  let updateCalls: Array<{ id: string; patch: Record<string, unknown> }>;
  let deleteCalls: string[];

  beforeEach(() => {
    mock.restore();
    updateCalls = [];
    deleteCalls = [];
    _deps.repo.update = async (id: string, patch: Record<string, unknown>) => {
      updateCalls.push({ id, patch });
    };
    _deps.repo.delete = async (id: string) => {
      deleteCalls.push(id);
      return true;
    };
    _deps.repo.getById = async (_id: string) => null;
    _deps.repo.getBySecret = async (_secret: string) => null;
  });

  // ── getEnvironmentBySecret ──

  describe("getEnvironmentBySecret", () => {
    test("找到环境时返回认证字段", async () => {
      _deps.repo.getBySecret = async () => ({
        id: "env-1",
        userId: "user-1",
        agentConfigId: "ac-1",
        organizationId: "org-1",
        secret: "sec-123",
        machineName: "m1",
        workerType: "acp",
        status: "active",
        capabilities: null,
        maxSessions: 1,
        lastPollAt: null,
      });
      const result = await getEnvironmentBySecret("sec-123");
      expect(result).toEqual({
        id: "env-1",
        userId: "user-1",
        agentConfigId: "ac-1",
        organizationId: "org-1",
        secret: "sec-123",
      });
    });

    test("未找到时返回 null", async () => {
      const result = await getEnvironmentBySecret("nonexistent");
      expect(result).toBeNull();
    });
  });

  // ── registerEnvironment ──

  describe("registerEnvironment", () => {
    test("默认 userId 为 system", async () => {
      let capturedParams: Record<string, unknown> = {};
      _deps.repo.create = async (params: Record<string, unknown>) => {
        capturedParams = params;
        return { id: "new-id", secret: "new-secret", status: "idle" } as EnvironmentRecord;
      };
      await registerEnvironment({});
      expect(capturedParams.userId).toBe("system");
    });

    test("返回 environment_id 和 environment_secret", async () => {
      _deps.repo.create = async () => ({
        id: "env-42",
        secret: "sec-42",
        status: "idle",
      } as EnvironmentRecord);
      const result = await registerEnvironment({});
      expect(result.environment_id).toBe("env-42");
      expect(result.environment_secret).toBe("sec-42");
      expect(result.status).toBe("idle");
      expect(result.session_id).toBeUndefined();
    });
  });

  // ── handleAcpConnect ──

  describe("handleAcpConnect", () => {
    test("boundEnvId 存在时标记为 active", async () => {
      await handleAcpConnect("env-1");
      expect(updateCalls.length).toBe(1);
      expect(updateCalls[0].id).toBe("env-1");
      expect(updateCalls[0].patch.status).toBe("active");
    });

    test("boundEnvId 为 null 时不做任何操作", async () => {
      await handleAcpConnect(null);
      expect(updateCalls.length).toBe(0);
    });
  });

  // ── handleAcpRegister ──

  describe("handleAcpRegister", () => {
    test("bound 环境 → 更新状态并返回 isNew=false", async () => {
      const result = await handleAcpRegister({
        wsId: "ws-1",
        userId: "user-1",
        agentName: "agent-1",
        boundEnvId: "env-bound",
        capabilities: { shell: true },
        maxSessions: 3,
      });
      expect(result.envId).toBe("env-bound");
      expect(result.isNew).toBe(false);
      expect(updateCalls[0].patch.status).toBe("active");
      expect(updateCalls[0].patch.capabilities).toEqual({ shell: true });
      expect(updateCalls[0].patch.maxSessions).toBe(3);
    });

    test("unbound 环境 → 创建临时环境并返回 isNew=true", async () => {
      _deps.repo.create = async (params: Record<string, unknown>) => ({
        id: "temp-env-id",
        secret: params.secret,
        status: "idle",
        machineName: params.machineName,
      } as EnvironmentRecord);

      const result = await handleAcpRegister({
        wsId: "ws-42",
        userId: "user-1",
        agentName: "agent-x",
        boundEnvId: null,
      });
      expect(result.envId).toBe("temp-env-id");
      expect(result.isNew).toBe(true);
    });
  });

  // ── handleAcpIdentify ──

  describe("handleAcpIdentify", () => {
    test("bound 环境 → 标记 active 并返回 capabilities", async () => {
      _deps.repo.getById = async () => ({
        id: "env-bound",
        capabilities: { code: true },
        userId: "u1",
        workerType: "acp",
      } as unknown as EnvironmentRecord);

      const result = await handleAcpIdentify({ agentId: "env-bound", userId: "u1", boundEnvId: "env-bound" });
      expect(result.envId).toBe("env-bound");
      expect(result.capabilities).toEqual({ code: true });
      expect(updateCalls[0].patch.status).toBe("active");
    });

    test("bound 环境 capabilities 为 null 时返回 null", async () => {
      _deps.repo.getById = async () => ({
        id: "env-bound",
        capabilities: null,
        userId: "u1",
        workerType: "acp",
      } as unknown as EnvironmentRecord);

      const result = await handleAcpIdentify({ agentId: "env-bound", userId: "u1", boundEnvId: "env-bound" });
      expect(result.capabilities).toBeNull();
    });

    test("unbound + workerType 非 acp → 抛出 NotFoundError", async () => {
      _deps.repo.getById = async () => ({
        id: "agent-1",
        workerType: "legacy",
        userId: "u1",
      } as unknown as EnvironmentRecord);

      await expect(
        handleAcpIdentify({ agentId: "agent-1", userId: "u1", boundEnvId: null }),
      ).rejects.toThrow("Agent not found");
    });

    test("unbound + 非本人环境 → 抛出 FORBIDDEN 403", async () => {
      _deps.repo.getById = async () => ({
        id: "agent-1",
        workerType: "acp",
        userId: "owner-1",
        capabilities: null,
      } as unknown as EnvironmentRecord);

      try {
        await handleAcpIdentify({ agentId: "agent-1", userId: "other-user", boundEnvId: null });
        expect.unreachable("should have thrown");
      } catch (err) {
        expect(err).toBeInstanceOf(AppError);
        expect((err as AppError).code).toBe("FORBIDDEN");
        expect((err as AppError).statusCode).toBe(403);
      }
    });

    test("unbound + userId 为 null 时不做归属检查", async () => {
      _deps.repo.getById = async () => ({
        id: "agent-1",
        workerType: "acp",
        userId: null,
        capabilities: { shell: true },
      } as unknown as EnvironmentRecord);

      const result = await handleAcpIdentify({ agentId: "agent-1", userId: "anyone", boundEnvId: null });
      expect(result.envId).toBe("agent-1");
      expect(result.capabilities).toEqual({ shell: true });
    });

    test("unbound + 记录不存在 → 抛出 NotFoundError", async () => {
      _deps.repo.getById = async () => null;
      await expect(
        handleAcpIdentify({ agentId: "missing", userId: "u1", boundEnvId: null }),
      ).rejects.toThrow("Agent not found");
    });
  });

  // ── handleAcpDisconnect ──

  describe("handleAcpDisconnect", () => {
    test("bound → 标记 idle", async () => {
      await handleAcpDisconnect("env-1", true);
      expect(updateCalls.length).toBe(1);
      expect(updateCalls[0].patch.status).toBe("idle");
      expect(deleteCalls.length).toBe(0);
    });

    test("unbound → 删除环境", async () => {
      await handleAcpDisconnect("env-1", false);
      expect(deleteCalls).toEqual(["env-1"]);
      expect(updateCalls.length).toBe(0);
    });
  });
});
