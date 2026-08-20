// orchestration-bootstrap.test.ts — 执行节点解析器工厂测试
// 测试目标：createExecutionNodeResolver 全分支覆盖

import { describe, expect, test, beforeEach, mock } from "bun:test";

// ── 复制核心逻辑（隔离 DB/config/sandbox 依赖）──

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

interface AgentNodeInfo {
  kind: "machine" | "sandbox";
  machineId?: string;
  sandboxPoolId?: string;
}

function resolveAgentNode(input: { agentNode: unknown; machineId: string | null }): AgentNodeInfo | null {
  const an = input.agentNode as Record<string, unknown> | null;
  if (an && typeof an === "object") {
    if (an.kind === "sandbox" && typeof an.sandboxPoolId === "string") {
      return { kind: "sandbox", sandboxPoolId: an.sandboxPoolId };
    }
    if (an.kind === "machine" && typeof an.machineId === "string") {
      return { kind: "machine", machineId: an.machineId };
    }
  }
  if (input.machineId) {
    return { kind: "machine", machineId: input.machineId };
  }
  return null;
}

interface ResolverInput {
  envId: string;
  organizationId: string | null;
  userId?: string;
  agentNode: unknown;
  configMachineId: string | null;
}

interface ResolverDeps {
  prepareSandbox?: (sandboxPoolId: string, userId: string, organizationId: string | null) => Promise<string>;
  sandboxEnabled?: boolean;
  defaultSandboxPoolId?: string | null;
}

function createExecutionNodeResolver(deps: ResolverDeps = {}) {
  const prepareSandbox = deps.prepareSandbox ?? (async () => "default-sandbox-node");

  return async function resolveExecutionNode(input: ResolverInput): Promise<string | null> {
    const sandboxEnabled = deps.sandboxEnabled ?? false;
    const defaultSandboxPoolId = deps.defaultSandboxPoolId ?? null;
    const agentNode = resolveAgentNode({ agentNode: input.agentNode, machineId: input.configMachineId });
    const explicitSandboxPoolId = agentNode?.kind === "sandbox" ? agentNode.sandboxPoolId : null;
    const explicitMachineId = agentNode?.kind === "machine" ? agentNode.machineId : null;

    if (explicitSandboxPoolId) {
      return prepareSandbox(explicitSandboxPoolId, input.userId ?? "", input.organizationId);
    }
    if (explicitMachineId) {
      return Promise.resolve(explicitMachineId);
    }
    if (sandboxEnabled) {
      if (!defaultSandboxPoolId) {
        throw new AppError("沙盒已开启但未配置默认资源池", "SANDBOX_DEFAULT_POOL_MISSING", 503);
      }
      return prepareSandbox(defaultSandboxPoolId, input.userId ?? "", input.organizationId);
    }
    return Promise.resolve(null);
  };
}

// ── Tests ──

describe("createExecutionNodeResolver", () => {
  let sandboxCalls: Array<{ poolId: string; userId: string; orgId: string | null }>;
  let mockPrepareSandbox: (poolId: string, userId: string, orgId: string | null) => Promise<string>;

  beforeEach(() => {
    mock.restore();
    sandboxCalls = [];
    mockPrepareSandbox = async (poolId: string, userId: string, orgId: string | null) => {
      sandboxCalls.push({ poolId, userId, orgId });
      return `sandbox-node-${poolId}`;
    };
  });

  // ── 显式 sandbox ──

  describe("显式 sandbox 分支", () => {
    test("agentNode.kind=sandbox → 调用 prepareSandbox 并返回节点", async () => {
      const resolver = createExecutionNodeResolver({ prepareSandbox: mockPrepareSandbox });
      const result = await resolver({
        envId: "env-1",
        organizationId: "org-1",
        userId: "user-1",
        agentNode: { kind: "sandbox", sandboxPoolId: "pool-abc" },
        configMachineId: null,
      });
      expect(result).toBe("sandbox-node-pool-abc");
      expect(sandboxCalls.length).toBe(1);
      expect(sandboxCalls[0].poolId).toBe("pool-abc");
      expect(sandboxCalls[0].userId).toBe("user-1");
      expect(sandboxCalls[0].orgId).toBe("org-1");
    });

    test("userId 未提供时传空字符串", async () => {
      const resolver = createExecutionNodeResolver({ prepareSandbox: mockPrepareSandbox });
      await resolver({
        envId: "env-1",
        organizationId: null,
        agentNode: { kind: "sandbox", sandboxPoolId: "pool-1" },
        configMachineId: null,
      });
      expect(sandboxCalls[0].userId).toBe("");
    });
  });

  // ── 显式 machine ──

  describe("显式 machine 分支", () => {
    test("agentNode.kind=machine → 返回 machineId", async () => {
      const resolver = createExecutionNodeResolver({ prepareSandbox: mockPrepareSandbox });
      const result = await resolver({
        envId: "env-1",
        organizationId: "org-1",
        agentNode: { kind: "machine", machineId: "machine-42" },
        configMachineId: null,
      });
      expect(result).toBe("machine-42");
      expect(sandboxCalls.length).toBe(0);
    });

    test("configMachineId 回退 → 返回 configMachineId", async () => {
      const resolver = createExecutionNodeResolver({ prepareSandbox: mockPrepareSandbox });
      const result = await resolver({
        envId: "env-1",
        organizationId: null,
        agentNode: null,
        configMachineId: "fallback-machine",
      });
      expect(result).toBe("fallback-machine");
    });
  });

  // ── 默认 sandbox ──

  describe("默认 sandbox 分支", () => {
    test("sandboxEnabled + defaultSandboxPoolId → 调用 prepareSandbox", async () => {
      const resolver = createExecutionNodeResolver({
        prepareSandbox: mockPrepareSandbox,
        sandboxEnabled: true,
        defaultSandboxPoolId: "default-pool",
      });
      const result = await resolver({
        envId: "env-1",
        organizationId: "org-1",
        userId: "user-1",
        agentNode: null,
        configMachineId: null,
      });
      expect(result).toBe("sandbox-node-default-pool");
      expect(sandboxCalls[0].poolId).toBe("default-pool");
    });

    test("sandboxEnabled 但无 defaultSandboxPoolId → 抛出 503", async () => {
      const resolver = createExecutionNodeResolver({
        sandboxEnabled: true,
        defaultSandboxPoolId: null,
      });
      try {
        await resolver({
          envId: "env-1",
          organizationId: null,
          agentNode: null,
          configMachineId: null,
        });
        expect.unreachable("should have thrown");
      } catch (err) {
        expect(err).toBeInstanceOf(AppError);
        expect((err as AppError).code).toBe("SANDBOX_DEFAULT_POOL_MISSING");
        expect((err as AppError).statusCode).toBe(503);
      }
    });

    test("sandboxEnabled 但 defaultSandboxPoolId 为空字符串 → 抛出 503", async () => {
      const resolver = createExecutionNodeResolver({
        sandboxEnabled: true,
        defaultSandboxPoolId: "",
      });
      try {
        await resolver({
          envId: "env-1",
          organizationId: null,
          agentNode: null,
          configMachineId: null,
        });
        expect.unreachable("should have thrown");
      } catch (err) {
        expect((err as AppError).code).toBe("SANDBOX_DEFAULT_POOL_MISSING");
      }
    });
  });

  // ── 默认链（无解析）──

  describe("默认链（返回 null）", () => {
    test("无 agentNode + sandbox 未启用 → 返回 null", async () => {
      const resolver = createExecutionNodeResolver();
      const result = await resolver({
        envId: "env-1",
        organizationId: null,
        agentNode: null,
        configMachineId: null,
      });
      expect(result).toBeNull();
    });

    test("空 agentNode 对象 + sandbox 未启用 → 返回 null", async () => {
      const resolver = createExecutionNodeResolver();
      const result = await resolver({
        envId: "env-1",
        organizationId: null,
        agentNode: {},
        configMachineId: null,
      });
      expect(result).toBeNull();
    });
  });

  // ── 优先级验证 ──

  describe("优先级", () => {
    test("显式 sandbox 优先于显式 machine", async () => {
      const resolver = createExecutionNodeResolver({
        prepareSandbox: mockPrepareSandbox,
        sandboxEnabled: true,
        defaultSandboxPoolId: "default-pool",
      });
      const result = await resolver({
        envId: "env-1",
        organizationId: null,
        userId: "u1",
        agentNode: { kind: "sandbox", sandboxPoolId: "explicit-pool" },
        configMachineId: "should-be-ignored",
      });
      expect(result).toBe("sandbox-node-explicit-pool");
    });

    test("显式 machine 优先于默认 sandbox", async () => {
      const resolver = createExecutionNodeResolver({
        prepareSandbox: mockPrepareSandbox,
        sandboxEnabled: true,
        defaultSandboxPoolId: "default-pool",
      });
      const result = await resolver({
        envId: "env-1",
        organizationId: null,
        agentNode: { kind: "machine", machineId: "explicit-machine" },
        configMachineId: null,
      });
      expect(result).toBe("explicit-machine");
      expect(sandboxCalls.length).toBe(0);
    });
  });
});
