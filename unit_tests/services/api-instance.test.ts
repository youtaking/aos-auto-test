// api-instance.test.ts — API 实例解析与运行时服务测试
// 测试目标：getApiOwnedInstance / resolveApiAgentInstance / ensureApiInstanceRuntime
// 业务意图：确保外部 API 只复用凭证归属的实例与环境，环境缺失时在锁内确定性创建，且运行时就绪与请求生命周期解耦
// 源：packages/agent-runtime/src/server/services/api-instance-resolution.ts（main a7f477a9e）

import { beforeEach, describe, expect, mock, test } from "bun:test";
import { createHash } from "node:crypto";

// ── 复制纯函数（依赖通过 deps 注入，避免 @fenix/* 依赖链） ──

class AppError extends Error {
  code: string;
  statusCode: number;
  constructor(message: string, code: string, statusCode: number) {
    super(message);
    this.name = "AppError";
    this.code = code;
    this.statusCode = statusCode;
  }
}

type InstanceCreationSource = "user" | "api" | "workflow";

interface AgentInstanceRecord {
  id: string;
  environmentId: string;
  ownerUserId: string;
  creationSource: InstanceCreationSource;
  name: string;
  isDefault: boolean;
  createdByUserId: string | null;
  createdAt: Date;
  updatedAt: Date;
}

interface EnvironmentLike {
  id: string;
  organizationId: string | null;
  userId: string | null;
  agentConfigId: string | null;
  description: string | null;
  createdAt?: Date;
}

interface AgentConfigLike {
  id: string;
  description?: string | null;
}

interface InstanceOwner {
  readonly organizationId: string;
  readonly userId: string;
}

interface ResolvedApiAgentInstance {
  agentConfigId: string;
  environmentId: string;
  instance: AgentInstanceRecord;
}

interface ResolutionDeps {
  findVisibleAgentConfig(input: {
    agentConfigId: string;
    organizationId: string;
    userId: string;
    action?: "read" | "use";
  }): Promise<AgentConfigLike | null>;
  getOwnedInstance(instanceId: string, ownerUserId: string): Promise<AgentInstanceRecord | undefined>;
  getEnvironmentById(id: string): Promise<EnvironmentLike | undefined>;
  listEnvironmentsByOrganizationId(organizationId: string): Promise<EnvironmentLike[]>;
  createWebEnvironment(input: {
    name: string;
    description?: string;
    agentConfigId: string;
    autoStart: boolean;
    userId: string;
    organizationId: string;
  }): Promise<EnvironmentLike>;
  withEnvironmentLock<T>(owner: InstanceOwner, agentConfigId: string, fn: () => Promise<T>): Promise<T>;
  resolveInstance(input: {
    environmentId: string;
    ownerUserId: string;
    automaticSelection: "api";
  }): Promise<AgentInstanceRecord>;
  ensureInstanceRuntime(instance: AgentInstanceRecord, signal?: AbortSignal): Promise<void>;
}

const unavailable = () => new AppError("Instance not found", "NOT_FOUND", 404);

let deps: ResolutionDeps;

/** Reauthorize an existing instance and its Environment without creating or starting anything. */
async function getApiOwnedInstance(
  owner: InstanceOwner,
  instanceId: string,
  agentConfigId?: string,
): Promise<ResolvedApiAgentInstance> {
  const instance = await deps.getOwnedInstance(instanceId, owner.userId);
  if (!instance || instance.ownerUserId !== owner.userId || instance.creationSource === "workflow")
    throw unavailable();
  const environment = await deps.getEnvironmentById(instance.environmentId);
  if (
    !environment ||
    environment.organizationId !== owner.organizationId ||
    environment.userId !== owner.userId ||
    !environment.agentConfigId ||
    (agentConfigId !== undefined && environment.agentConfigId !== agentConfigId)
  )
    throw unavailable();
  const agent = await deps.findVisibleAgentConfig({
    ...owner,
    agentConfigId: environment.agentConfigId,
    action: "use",
  });
  if (!agent) throw unavailable();
  return { agentConfigId: agent.id, environmentId: environment.id, instance };
}

/** Shared HTTP connect/Chat policy; runtime starts only after the environment transaction commits. */
async function resolveApiAgentInstance(
  owner: InstanceOwner,
  agentConfigId: string,
  options: { instanceId?: string; signal?: AbortSignal } = {},
): Promise<ResolvedApiAgentInstance> {
  options.signal?.throwIfAborted();
  if (options.instanceId) return getApiOwnedInstance(owner, options.instanceId, agentConfigId);
  const agent = await deps.findVisibleAgentConfig({ ...owner, agentConfigId, action: "use" });
  if (!agent) throw new AppError("Agent not found", "NOT_FOUND", 404);
  const environment = await deps.withEnvironmentLock(owner, agentConfigId, async () => {
    options.signal?.throwIfAborted();
    const candidates = (await deps.listEnvironmentsByOrganizationId(owner.organizationId))
      .filter(
        (env) =>
          env.organizationId === owner.organizationId && env.userId === owner.userId && env.agentConfigId === agent.id,
      )
      .sort((a, b) => (a.createdAt?.getTime() ?? 0) - (b.createdAt?.getTime() ?? 0) || a.id.localeCompare(b.id));
    if (candidates[0]) return candidates[0];
    const suffix = createHash("sha256")
      .update(JSON.stringify([owner.userId, agent.id]))
      .digest("hex")
      .slice(0, 20);
    return deps.createWebEnvironment({
      name: `api-${suffix}`,
      description: agent.description ?? undefined,
      agentConfigId: agent.id,
      autoStart: true,
      userId: owner.userId,
      organizationId: owner.organizationId,
    });
  });
  options.signal?.throwIfAborted();
  const instance = await deps.resolveInstance({
    environmentId: environment.id,
    ownerUserId: owner.userId,
    automaticSelection: "api",
  });
  return { agentConfigId: agent.id, environmentId: environment.id, instance };
}

/** Ensure the selected shared runtime without transferring lifetime ownership to the request. */
function ensureApiInstanceRuntime(instance: AgentInstanceRecord, signal?: AbortSignal): Promise<void> {
  return deps.ensureInstanceRuntime(instance, signal);
}

// ── 测试辅助 ──

function instanceRecord(overrides: Partial<AgentInstanceRecord> = {}): AgentInstanceRecord {
  return {
    id: "inst-1",
    environmentId: "env-1",
    ownerUserId: "user-1",
    creationSource: "api",
    name: "api-instance",
    isDefault: false,
    createdByUserId: "user-1",
    createdAt: new Date("2026-01-01T00:00:00Z"),
    updatedAt: new Date("2026-01-01T00:00:00Z"),
    ...overrides,
  };
}

function environmentRecord(overrides: Partial<EnvironmentLike> = {}): EnvironmentLike {
  return {
    id: "env-1",
    organizationId: "org-1",
    userId: "user-1",
    agentConfigId: "agent-1",
    description: null,
    createdAt: new Date("2026-01-01T00:00:00Z"),
    ...overrides,
  };
}

const owner: InstanceOwner = { organizationId: "org-1", userId: "user-1" };

function baseDeps(overrides: Partial<ResolutionDeps> = {}): ResolutionDeps {
  return {
    findVisibleAgentConfig: mock(async (input) => ({ id: input.agentConfigId })),
    getOwnedInstance: mock(async () => instanceRecord()),
    getEnvironmentById: mock(async () => environmentRecord()),
    listEnvironmentsByOrganizationId: mock(async () => [environmentRecord()]),
    createWebEnvironment: mock(async (input) =>
      environmentRecord({
        id: "env-created",
        agentConfigId: input.agentConfigId,
        description: input.description ?? null,
      }),
    ),
    withEnvironmentLock: mock(async (_owner, _agentConfigId, fn) => fn()),
    resolveInstance: mock(async (input) =>
      instanceRecord({ environmentId: input.environmentId, ownerUserId: input.ownerUserId }),
    ),
    ensureInstanceRuntime: mock(async () => {}),
    ...overrides,
  };
}

// ── tests ──

describe("api-instance-resolution 实例解析", () => {
  beforeEach(() => {
    mock.restore();
    deps = baseDeps();
  });

  describe("getApiOwnedInstance 已有实例再授权", () => {
    test("成功时返回 agent/环境/实例三元组", async () => {
      const resolved = await getApiOwnedInstance(owner, "inst-1");
      expect(resolved).toEqual({
        agentConfigId: "agent-1",
        environmentId: "env-1",
        instance: instanceRecord(),
      });
    });

    test("用 use 动作校验 Agent 可见性，并带上凭证身份", async () => {
      await getApiOwnedInstance(owner, "inst-1");
      expect(deps.findVisibleAgentConfig).toHaveBeenCalledWith({
        organizationId: "org-1",
        userId: "user-1",
        agentConfigId: "agent-1",
        action: "use",
      });
    });

    test("不创建环境、不启动运行时", async () => {
      await getApiOwnedInstance(owner, "inst-1");
      expect(deps.createWebEnvironment).toHaveBeenCalledTimes(0);
      expect(deps.resolveInstance).toHaveBeenCalledTimes(0);
      expect(deps.ensureInstanceRuntime).toHaveBeenCalledTimes(0);
      expect(deps.withEnvironmentLock).toHaveBeenCalledTimes(0);
    });

    test("实例不存在时抛 NOT_FOUND，且不再查环境", async () => {
      deps.getOwnedInstance = mock(async () => undefined);
      await expect(getApiOwnedInstance(owner, "missing")).rejects.toMatchObject({
        code: "NOT_FOUND",
        statusCode: 404,
      });
      expect(deps.getEnvironmentById).toHaveBeenCalledTimes(0);
    });

    test("实例所有者与凭证用户不一致时拒绝", async () => {
      deps.getOwnedInstance = mock(async () => instanceRecord({ ownerUserId: "user-other" }));
      await expect(getApiOwnedInstance(owner, "inst-1")).rejects.toThrow("Instance not found");
    });

    test("workflow 创建的实例不可通过 API 使用", async () => {
      deps.getOwnedInstance = mock(async () => instanceRecord({ creationSource: "workflow" }));
      await expect(getApiOwnedInstance(owner, "inst-1")).rejects.toMatchObject({ code: "NOT_FOUND" });
    });

    test("环境不存在时拒绝", async () => {
      deps.getEnvironmentById = mock(async () => undefined);
      await expect(getApiOwnedInstance(owner, "inst-1")).rejects.toThrow("Instance not found");
    });

    test("环境属于其他组织时拒绝（跨组织）", async () => {
      deps.getEnvironmentById = mock(async () => environmentRecord({ organizationId: "org-other" }));
      await expect(getApiOwnedInstance(owner, "inst-1")).rejects.toThrow("Instance not found");
    });

    test("环境属于其他用户时拒绝（越权）", async () => {
      deps.getEnvironmentById = mock(async () => environmentRecord({ userId: "user-other" }));
      await expect(getApiOwnedInstance(owner, "inst-1")).rejects.toThrow("Instance not found");
    });

    test("环境未绑定 Agent 时拒绝", async () => {
      deps.getEnvironmentById = mock(async () => environmentRecord({ agentConfigId: null }));
      await expect(getApiOwnedInstance(owner, "inst-1")).rejects.toThrow("Instance not found");
      expect(deps.findVisibleAgentConfig).toHaveBeenCalledTimes(0);
    });

    test("传入的 agentConfigId 与环境不一致时拒绝", async () => {
      await expect(getApiOwnedInstance(owner, "inst-1", "agent-other")).rejects.toThrow("Instance not found");
      expect(deps.findVisibleAgentConfig).toHaveBeenCalledTimes(0);
    });

    test("传入的 agentConfigId 与环境一致时通过", async () => {
      const resolved = await getApiOwnedInstance(owner, "inst-1", "agent-1");
      expect(resolved.agentConfigId).toBe("agent-1");
    });

    test("Agent 不可见时拒绝", async () => {
      deps.findVisibleAgentConfig = mock(async () => null);
      await expect(getApiOwnedInstance(owner, "inst-1")).rejects.toMatchObject({ code: "NOT_FOUND" });
    });
  });

  describe("resolveApiAgentInstance 共享 HTTP 连接策略", () => {
    test("已中止的 signal 立即抛错，不查 Agent", async () => {
      const controller = new AbortController();
      controller.abort(new Error("aborted by caller"));
      await expect(resolveApiAgentInstance(owner, "agent-1", { signal: controller.signal })).rejects.toThrow(
        "aborted by caller",
      );
      expect(deps.findVisibleAgentConfig).toHaveBeenCalledTimes(0);
    });

    test("传入 instanceId 时走已有实例再授权", async () => {
      const resolved = await resolveApiAgentInstance(owner, "agent-1", { instanceId: "inst-1" });
      expect(deps.getOwnedInstance).toHaveBeenCalledWith("inst-1", "user-1");
      expect(resolved.environmentId).toBe("env-1");
      expect(deps.withEnvironmentLock).toHaveBeenCalledTimes(0);
      expect(deps.resolveInstance).toHaveBeenCalledTimes(0);
    });

    test("传入 instanceId 且与环境 Agent 不一致时拒绝", async () => {
      await expect(resolveApiAgentInstance(owner, "agent-other", { instanceId: "inst-1" })).rejects.toThrow(
        "Instance not found",
      );
    });

    test("Agent 不可见时抛 Agent not found", async () => {
      deps.findVisibleAgentConfig = mock(async () => null);
      await expect(resolveApiAgentInstance(owner, "agent-1")).rejects.toMatchObject({
        message: "Agent not found",
        code: "NOT_FOUND",
        statusCode: 404,
      });
      expect(deps.withEnvironmentLock).toHaveBeenCalledTimes(0);
    });

    test("在环境锁内筛选同组织同用户同 Agent 的候选", async () => {
      const environments = [
        environmentRecord({ id: "env-other-org", organizationId: "org-other" }),
        environmentRecord({ id: "env-other-user", userId: "user-other" }),
        environmentRecord({ id: "env-other-agent", agentConfigId: "agent-other" }),
        environmentRecord({ id: "env-match" }),
      ];
      deps.listEnvironmentsByOrganizationId = mock(async () => environments);
      const resolved = await resolveApiAgentInstance(owner, "agent-1");
      expect(resolved.environmentId).toBe("env-match");
      expect(deps.withEnvironmentLock).toHaveBeenCalledWith(owner, "agent-1", expect.any(Function));
      expect(deps.listEnvironmentsByOrganizationId).toHaveBeenCalledWith("org-1");
    });

    test("多个候选按 createdAt 升序取最早，不创建新环境", async () => {
      deps.listEnvironmentsByOrganizationId = mock(async () => [
        environmentRecord({ id: "env-late", createdAt: new Date("2026-02-01T00:00:00Z") }),
        environmentRecord({ id: "env-early", createdAt: new Date("2026-01-01T00:00:00Z") }),
      ]);
      const resolved = await resolveApiAgentInstance(owner, "agent-1");
      expect(resolved.environmentId).toBe("env-early");
      expect(deps.createWebEnvironment).toHaveBeenCalledTimes(0);
    });

    test("createdAt 相同时按 id 字典序取最小，保证确定性", async () => {
      const sameTime = new Date("2026-01-01T00:00:00Z");
      deps.listEnvironmentsByOrganizationId = mock(async () => [
        environmentRecord({ id: "env-b", createdAt: sameTime }),
        environmentRecord({ id: "env-a", createdAt: sameTime }),
      ]);
      const resolved = await resolveApiAgentInstance(owner, "agent-1");
      expect(resolved.environmentId).toBe("env-a");
    });

    test("缺少 createdAt 视为最早", async () => {
      deps.listEnvironmentsByOrganizationId = mock(async () => [
        environmentRecord({ id: "env-dated", createdAt: new Date("2026-01-01T00:00:00Z") }),
        environmentRecord({ id: "env-undated", createdAt: undefined }),
      ]);
      const resolved = await resolveApiAgentInstance(owner, "agent-1");
      expect(resolved.environmentId).toBe("env-undated");
    });

    test("无候选时在锁内创建 api- 前缀环境并自动启动", async () => {
      deps.listEnvironmentsByOrganizationId = mock(async () => []);
      const resolved = await resolveApiAgentInstance(owner, "agent-1");
      const suffix = createHash("sha256").update(JSON.stringify(["user-1", "agent-1"])).digest("hex").slice(0, 20);
      expect(deps.createWebEnvironment).toHaveBeenCalledWith({
        name: `api-${suffix}`,
        description: undefined,
        agentConfigId: "agent-1",
        autoStart: true,
        userId: "user-1",
        organizationId: "org-1",
      });
      expect(resolved.environmentId).toBe("env-created");
    });

    test("创建环境时继承 Agent 描述", async () => {
      deps.listEnvironmentsByOrganizationId = mock(async () => []);
      deps.findVisibleAgentConfig = mock(async () => ({ id: "agent-1", description: "desc from agent" }));
      await resolveApiAgentInstance(owner, "agent-1");
      expect(deps.createWebEnvironment).toHaveBeenCalledWith(
        expect.objectContaining({ description: "desc from agent" }),
      );
    });

    test("锁释放后再检查 signal，已中止则不解析实例", async () => {
      const controller = new AbortController();
      deps.withEnvironmentLock = mock(async (_owner, _agentConfigId, fn) => {
        const environment = await fn();
        controller.abort(new Error("aborted after lock"));
        return environment;
      });
      await expect(resolveApiAgentInstance(owner, "agent-1", { signal: controller.signal })).rejects.toThrow(
        "aborted after lock",
      );
      expect(deps.resolveInstance).toHaveBeenCalledTimes(0);
    });

    test("锁内中止则不创建环境", async () => {
      const controller = new AbortController();
      deps.withEnvironmentLock = mock(async (_owner, _agentConfigId, fn) => {
        controller.abort(new Error("aborted in lock"));
        return fn();
      });
      deps.listEnvironmentsByOrganizationId = mock(async () => []);
      await expect(resolveApiAgentInstance(owner, "agent-1", { signal: controller.signal })).rejects.toThrow(
        "aborted in lock",
      );
      expect(deps.createWebEnvironment).toHaveBeenCalledTimes(0);
    });

    test("用 automaticSelection=api 解析实例并透传环境与用户", async () => {
      await resolveApiAgentInstance(owner, "agent-1");
      expect(deps.resolveInstance).toHaveBeenCalledWith({
        environmentId: "env-1",
        ownerUserId: "user-1",
        automaticSelection: "api",
      });
    });

    test("成功返回 Agent、环境与实例", async () => {
      const resolved = await resolveApiAgentInstance(owner, "agent-1");
      expect(resolved.agentConfigId).toBe("agent-1");
      expect(resolved.environmentId).toBe("env-1");
      expect(resolved.instance.ownerUserId).toBe("user-1");
    });
  });

  describe("ensureApiInstanceRuntime 运行时就绪", () => {
    test("透传实例与 signal 给运行时服务", async () => {
      const controller = new AbortController();
      const instance = instanceRecord();
      await ensureApiInstanceRuntime(instance, controller.signal);
      expect(deps.ensureInstanceRuntime).toHaveBeenCalledWith(instance, controller.signal);
    });

    test("运行时失败向上抛出", async () => {
      deps.ensureInstanceRuntime = mock(async () => {
        throw new Error("runtime failed");
      });
      await expect(ensureApiInstanceRuntime(instanceRecord())).rejects.toThrow("runtime failed");
    });
  });
});
