// instance-manager.test.ts — ACP 实例管理器类型和状态测试
// 测试目标：AgentType 枚举、InstanceState 结构、EngineHandler 接口
// 业务意图：确保实例管理器的类型约束正确

import { describe, test, expect } from "bun:test";

// ── 复制类型和纯函数（来自 packages/acp-link/src/client/instance-manager.ts）──

type AgentType = "opencode" | "ccb" | "claude-code";

interface AcpSessionState {
  connection: unknown | null;
  sessionId: string | null;
  pendingPermissions: Map<string, unknown>;
  agentCapabilities: unknown | null;
  promptCapabilities: unknown | null;
  modelState: unknown | null;
  modeState: unknown | null;
  titleOverrides: Map<string, string | null>;
}

interface InstanceState {
  instanceId: string;
  workspace: string;
  process: unknown | null;
  connection: unknown | null;
  capabilities: Record<string, unknown> | null;
  sessionState: AcpSessionState;
  agentType: AgentType;
  sessionId: string | null;
}

function createInstanceState(instanceId: string, agentType: AgentType, workspace: string): InstanceState {
  return {
    instanceId,
    workspace,
    process: null,
    connection: null,
    capabilities: null,
    sessionState: {
      connection: null,
      sessionId: null,
      pendingPermissions: new Map(),
      agentCapabilities: null,
      promptCapabilities: null,
      modelState: null,
      modeState: null,
      titleOverrides: new Map(),
    },
    agentType,
    sessionId: null,
  };
}

// 模拟 getHandler 逻辑
function getHandler(
  handlers: Record<string, string>,
  engineType: string | undefined,
  defaultEngine: string,
): string {
  const type = engineType ?? defaultEngine;
  const handler = handlers[type];
  if (!handler) throw new Error(`No engine handler for type: ${type}`);
  return handler;
}

// ── 测试 ──

describe("AgentType", () => {
  test("正向 - 三种引擎类型", () => {
    const types: AgentType[] = ["opencode", "ccb", "claude-code"];
    expect(types.length).toBe(3);
  });
});

describe("createInstanceState", () => {
  test("正向 - 创建初始状态", () => {
    const state = createInstanceState("i-1", "opencode", "/workspace/i-1");
    expect(state.instanceId).toBe("i-1");
    expect(state.agentType).toBe("opencode");
    expect(state.workspace).toBe("/workspace/i-1");
    expect(state.process).toBeNull();
    expect(state.connection).toBeNull();
    expect(state.capabilities).toBeNull();
    expect(state.sessionId).toBeNull();
  });

  test("正向 - sessionState 初始为空", () => {
    const state = createInstanceState("i-1", "ccb", "/ws");
    expect(state.sessionState.connection).toBeNull();
    expect(state.sessionState.sessionId).toBeNull();
    expect(state.sessionState.pendingPermissions.size).toBe(0);
    expect(state.sessionState.titleOverrides.size).toBe(0);
  });

  test("隔离 - 两个实例状态独立", () => {
    const a = createInstanceState("i-1", "opencode", "/ws");
    const b = createInstanceState("i-2", "claude-code", "/ws");
    a.sessionState.titleOverrides.set("s1", "title");
    expect(b.sessionState.titleOverrides.size).toBe(0);
  });

  test("正向 - 三种 agentType 都可创建", () => {
    expect(createInstanceState("i", "opencode", "/ws").agentType).toBe("opencode");
    expect(createInstanceState("i", "ccb", "/ws").agentType).toBe("ccb");
    expect(createInstanceState("i", "claude-code", "/ws").agentType).toBe("claude-code");
  });
});

describe("getHandler", () => {
  const handlers = { opencode: "oc-handler", ccb: "ccb-handler", "claude-code": "cc-handler" };

  test("正向 - 指定 engineType 返回对应 handler", () => {
    expect(getHandler(handlers, "opencode", "opencode")).toBe("oc-handler");
    expect(getHandler(handlers, "ccb", "opencode")).toBe("ccb-handler");
  });

  test("正向 - 未指定时使用 defaultEngine", () => {
    expect(getHandler(handlers, undefined, "ccb")).toBe("ccb-handler");
  });

  test("异常 - 不存在的类型抛错", () => {
    expect(() => getHandler(handlers, "unknown", "opencode")).toThrow("No engine handler for type: unknown");
  });
});
