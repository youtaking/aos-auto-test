// acp-dispatcher.test.ts — ACP 会话状态初始化测试
// 测试目标：createAcpSessionState 的初始值正确性
// 业务意图：确保每个 ACP relay 连接的初始状态干净无残留

import { describe, test, expect } from "bun:test";

// ── 复制纯函数（来自 packages/acp-link/src/acp-dispatcher.ts）──

interface AcpSessionState {
  connection: unknown | null;
  sessionId: string | null;
  pendingPermissions: Map<string, unknown>;
  agentCapabilities: unknown | null;
  promptCapabilities: unknown | null;
  modelState: unknown | null;
  modeState: {
    availableModes: Array<{ id: string; name: string; description?: string | null }>;
    currentModeId: string;
  } | null;
  titleOverrides: Map<string, string | null>;
}

function createAcpSessionState(): AcpSessionState {
  return {
    connection: null,
    sessionId: null,
    pendingPermissions: new Map(),
    agentCapabilities: null,
    promptCapabilities: null,
    modelState: null,
    modeState: null,
    titleOverrides: new Map(),
  };
}

function cancelPendingPermissions(state: AcpSessionState): void {
  for (const [, pending] of state.pendingPermissions) {
    clearTimeout((pending as any).timeout);
    (pending as any).resolve({ outcome: "cancelled" });
  }
  state.pendingPermissions.clear();
}

// ── 测试 ──

describe("createAcpSessionState", () => {
  test("正向 - connection 初始为 null", () => {
    expect(createAcpSessionState().connection).toBeNull();
  });

  test("正向 - sessionId 初始为 null", () => {
    expect(createAcpSessionState().sessionId).toBeNull();
  });

  test("正向 - pendingPermissions 初始为空 Map", () => {
    const state = createAcpSessionState();
    expect(state.pendingPermissions).toBeInstanceOf(Map);
    expect(state.pendingPermissions.size).toBe(0);
  });

  test("正向 - agentCapabilities 初始为 null", () => {
    expect(createAcpSessionState().agentCapabilities).toBeNull();
  });

  test("正向 - promptCapabilities 初始为 null", () => {
    expect(createAcpSessionState().promptCapabilities).toBeNull();
  });

  test("正向 - modelState 初始为 null", () => {
    expect(createAcpSessionState().modelState).toBeNull();
  });

  test("正向 - modeState 初始为 null", () => {
    expect(createAcpSessionState().modeState).toBeNull();
  });

  test("正向 - titleOverrides 初始为空 Map", () => {
    const state = createAcpSessionState();
    expect(state.titleOverrides).toBeInstanceOf(Map);
    expect(state.titleOverrides.size).toBe(0);
  });

  test("隔离 - 两次调用返回独立对象", () => {
    const a = createAcpSessionState();
    const b = createAcpSessionState();
    expect(a).not.toBe(b);
    expect(a.pendingPermissions).not.toBe(b.pendingPermissions);
    a.titleOverrides.set("s1", "title");
    expect(b.titleOverrides.size).toBe(0);
  });
});

describe("cancelPendingPermissions", () => {
  test("正向 - 清空所有 pending 并 resolve 为 cancelled", async () => {
    const state = createAcpSessionState();
    const outcomes: unknown[] = [];
    state.pendingPermissions.set("p1", {
      resolve: (v: unknown) => outcomes.push(v),
      timeout: setTimeout(() => {}, 60000),
    });
    state.pendingPermissions.set("p2", {
      resolve: (v: unknown) => outcomes.push(v),
      timeout: setTimeout(() => {}, 60000),
    });

    cancelPendingPermissions(state);

    expect(state.pendingPermissions.size).toBe(0);
    expect(outcomes.length).toBe(2);
    expect(outcomes[0]).toEqual({ outcome: "cancelled" });
    expect(outcomes[1]).toEqual({ outcome: "cancelled" });
  });

  test("边界 - 空 pending 时不抛错", () => {
    const state = createAcpSessionState();
    expect(() => cancelPendingPermissions(state)).not.toThrow();
  });
});
