// sync-close-diagnostics.test.ts — 同步连接关闭诊断上下文测试
// 测试目标：setSyncCloseContextForConnection 的上下文派生与 logSyncClose 的兜底/截断
// 业务意图：关闭可能发生在任意异步分支，日志必须取到最近一次入站帧的事实，缺失字段明确为 null
// 源：packages/chat-channel/src/channel/sync-close-diagnostics.ts（main a7f477a9e）

import { describe, expect, test } from "bun:test";

// ── 复制实现 ──

interface SyncCloseContext {
  readonly wsId: string;
  readonly entryExists: boolean;
  readonly pendingTextFrames: number;
  readonly pendingBinaryFrames: number;
  readonly organizationId: string | null;
  readonly rcsSessionId: string | null;
  readonly acpSessionId: string | null;
  readonly relayReady: boolean | null;
  readonly sessionLoaded: boolean | null;
  readonly activeTurnId: string | null;
}

interface ClientConnection {
  organizationId?: string;
  rcsSessionId: string;
  acpSessionId?: string;
  relayReady?: boolean;
  sessionLoaded?: boolean;
}

function createDiagnostics(log: (event: string, fields: Record<string, unknown>) => void) {
  const contexts = new WeakMap<object, SyncCloseContext>();

  function setSyncCloseContext(ws: object, context: SyncCloseContext): void {
    contexts.set(ws, context);
  }

  function setSyncCloseContextForConnection(
    registry: { pendingTextCount(id: string): number; pendingBinaryCount(id: string): number },
    ws: object,
    wsId: string,
    entry: ClientConnection | undefined,
    docManager?: { getSessionYdoc(sessionId: string): unknown },
  ): void {
    const sessionDoc = entry ? docManager?.getSessionYdoc(entry.rcsSessionId) : undefined;
    const session = (sessionDoc as { getMap?: (name: string) => { get(key: string): unknown } } | undefined)
      ?.getMap?.("root")
      .get("session") as { get: (key: string) => unknown } | undefined;
    setSyncCloseContext(ws, {
      wsId,
      entryExists: entry !== undefined,
      pendingTextFrames: registry.pendingTextCount(wsId),
      pendingBinaryFrames: registry.pendingBinaryCount(wsId),
      organizationId: entry?.organizationId ?? null,
      rcsSessionId: entry?.rcsSessionId ?? null,
      acpSessionId: entry?.acpSessionId ?? null,
      relayReady: entry?.relayReady ?? null,
      sessionLoaded: entry?.sessionLoaded ?? null,
      activeTurnId: (session?.get("activeTurnId") as string | undefined) ?? null,
    });
  }

  function logSyncClose(
    ws: object,
    input: { readonly code: number; readonly reason: string; readonly source: "gateway-route" | "sync-provider" },
  ): void {
    const context = contexts.get(ws);
    log("同步连接关闭", {
      code: input.code,
      reason: input.reason.slice(0, 500),
      source: input.source,
      wsId: context?.wsId ?? null,
      entryExists: context?.entryExists ?? null,
      pendingTextFrames: context?.pendingTextFrames ?? null,
      pendingBinaryFrames: context?.pendingBinaryFrames ?? null,
      organizationId: context?.organizationId ?? null,
      rcsSessionId: context?.rcsSessionId ?? null,
      acpSessionId: context?.acpSessionId ?? null,
      relayReady: context?.relayReady ?? null,
      sessionLoaded: context?.sessionLoaded ?? null,
      activeTurnId: context?.activeTurnId ?? null,
    });
  }

  return { setSyncCloseContext, setSyncCloseContextForConnection, logSyncClose };
}

// ── 辅助 ──

function registry(text = 0, binary = 0) {
  const calls: string[] = [];
  return {
    calls,
    pendingTextCount: (id: string) => {
      calls.push(`text:${id}`);
      return text;
    },
    pendingBinaryCount: (id: string) => {
      calls.push(`binary:${id}`);
      return binary;
    },
  };
}

function sessionDoc(activeTurnId: unknown) {
  return {
    getMap: () => ({
      get: (key: string) => (key === "session" ? { get: (field: string) => (field === "activeTurnId" ? activeTurnId : undefined) } : undefined),
    }),
  };
}

// ── tests ──

describe("setSyncCloseContextForConnection 上下文派生", () => {
  test("已认证连接携带完整的入站事实", () => {
    let captured: Record<string, unknown> | undefined;
    const diagnostics = createDiagnostics((_event, fields) => {
      captured = fields;
    });
    const ws = {};
    const counts = registry(3, 2);
    diagnostics.setSyncCloseContextForConnection(counts, ws, "ws-1", {
      organizationId: "org-1",
      rcsSessionId: "rcs-1",
      acpSessionId: "acp-1",
      relayReady: true,
      sessionLoaded: false,
    }, { getSessionYdoc: () => sessionDoc("turn-1") });
    diagnostics.logSyncClose(ws, { code: 1000, reason: "bye", source: "gateway-route" });

    expect(counts.calls).toEqual(["text:ws-1", "binary:ws-1"]);
    expect(captured).toMatchObject({
      wsId: "ws-1",
      entryExists: true,
      pendingTextFrames: 3,
      pendingBinaryFrames: 2,
      organizationId: "org-1",
      rcsSessionId: "rcs-1",
      acpSessionId: "acp-1",
      relayReady: true,
      sessionLoaded: false,
      activeTurnId: "turn-1",
    });
  });

  test("entry 缺失时 scope 字段为 null 且不读取文档", () => {
    const reads: string[] = [];
    let captured: Record<string, unknown> | undefined;
    const diagnostics = createDiagnostics((_event, fields) => {
      captured = fields;
    });
    const ws = {};
    diagnostics.setSyncCloseContextForConnection(registry(1, 0), ws, "ws-2", undefined, {
      getSessionYdoc: (id) => {
        reads.push(id);
        return sessionDoc("turn");
      },
    });
    diagnostics.logSyncClose(ws, { code: 1000, reason: "bye", source: "gateway-route" });

    expect(reads).toEqual([]);
    expect(captured).toMatchObject({
      wsId: "ws-2",
      entryExists: false,
      pendingTextFrames: 1,
      pendingBinaryFrames: 0,
      organizationId: null,
      rcsSessionId: null,
      acpSessionId: null,
      relayReady: null,
      sessionLoaded: null,
      activeTurnId: null,
    });
  });

  test("文档缺失或 session 缺失时 activeTurnId 为 null", () => {
    for (const docManager of [
      undefined,
      { getSessionYdoc: () => undefined },
      { getSessionYdoc: () => ({ getMap: () => ({ get: () => undefined }) }) },
      { getSessionYdoc: () => sessionDoc(undefined) },
    ]) {
      let captured: Record<string, unknown> | undefined;
      const diagnostics = createDiagnostics((_event, fields) => {
        captured = fields;
      });
      const ws = {};
      diagnostics.setSyncCloseContextForConnection(registry(), ws, "ws-3", {
        organizationId: "org-1",
        rcsSessionId: "rcs-1",
      }, docManager as never);
      diagnostics.logSyncClose(ws, { code: 1001, reason: "x", source: "sync-provider" });
      expect(captured!.activeTurnId).toBeNull();
    }
  });

  test("非字符串激活轮次按原值透传（仅类型断言，不做运行时校验）", () => {
    let captured: Record<string, unknown> | undefined;
    const diagnostics = createDiagnostics((_event, fields) => {
      captured = fields;
    });
    const ws = {};
    diagnostics.setSyncCloseContextForConnection(registry(), ws, "ws-4", {
      organizationId: "org-1",
      rcsSessionId: "rcs-1",
    }, { getSessionYdoc: () => sessionDoc(42) });
    diagnostics.logSyncClose(ws, { code: 1001, reason: "x", source: "sync-provider" });
    expect(captured!.activeTurnId).toBe(42);
  });
});

describe("logSyncClose 日志输出", () => {
  test("使用最近一次上下文并截断 reason", () => {
    const events: Array<[string, Record<string, unknown>]> = [];
    const { setSyncCloseContextForConnection, logSyncClose } = createDiagnostics((event, fields) =>
      events.push([event, fields]),
    );
    const ws = {};
    setSyncCloseContextForConnection(registry(5, 4), ws, "ws-1", {
      organizationId: "org-1",
      rcsSessionId: "rcs-1",
    }, { getSessionYdoc: () => sessionDoc("turn-9") });
    logSyncClose(ws, { code: 1006, reason: "r".repeat(900), source: "sync-provider" });

    expect(events).toHaveLength(1);
    const [event, fields] = events[0]!;
    expect(event).toBe("同步连接关闭");
    expect(fields).toMatchObject({
      code: 1006,
      source: "sync-provider",
      wsId: "ws-1",
      entryExists: true,
      pendingTextFrames: 5,
      pendingBinaryFrames: 4,
      organizationId: "org-1",
      rcsSessionId: "rcs-1",
      activeTurnId: "turn-9",
    });
    expect((fields.reason as string).length).toBe(500);
  });

  test("未设置上下文时全部兜底为 null", () => {
    let captured: Record<string, unknown> | undefined;
    const { logSyncClose } = createDiagnostics((_event, fields) => {
      captured = fields;
    });
    logSyncClose({}, { code: 1000, reason: "bye", source: "gateway-route" });
    expect(captured).toEqual({
      code: 1000,
      reason: "bye",
      source: "gateway-route",
      wsId: null,
      entryExists: null,
      pendingTextFrames: null,
      pendingBinaryFrames: null,
      organizationId: null,
      rcsSessionId: null,
      acpSessionId: null,
      relayReady: null,
      sessionLoaded: null,
      activeTurnId: null,
    });
  });

  test("后续入站帧覆盖先前上下文", () => {
    let captured: Record<string, unknown> | undefined;
    const diagnostics = createDiagnostics((_event, fields) => {
      captured = fields;
    });
    const ws = {};
    diagnostics.setSyncCloseContext(ws, {
      wsId: "old",
      entryExists: true,
      pendingTextFrames: 1,
      pendingBinaryFrames: 1,
      organizationId: "old-org",
      rcsSessionId: null,
      acpSessionId: null,
      relayReady: null,
      sessionLoaded: null,
      activeTurnId: null,
    });
    diagnostics.setSyncCloseContext(ws, {
      wsId: "new",
      entryExists: false,
      pendingTextFrames: 0,
      pendingBinaryFrames: 0,
      organizationId: null,
      rcsSessionId: null,
      acpSessionId: null,
      relayReady: null,
      sessionLoaded: null,
      activeTurnId: null,
    });
    diagnostics.logSyncClose(ws, { code: 1001, reason: "x", source: "gateway-route" });
    expect(captured).toMatchObject({ wsId: "new", entryExists: false, organizationId: null });
  });

  test("不同连接互不串扰", () => {
    const captures: Array<Record<string, unknown>> = [];
    const diagnostics = createDiagnostics((_event, fields) => {
      captures.push(fields);
    });
    const first = {};
    const second = {};
    diagnostics.setSyncCloseContextForConnection(registry(), first, "ws-a", {
      organizationId: "org-a",
      rcsSessionId: "rcs-a",
    });
    diagnostics.setSyncCloseContextForConnection(registry(), second, "ws-b", {
      organizationId: "org-b",
      rcsSessionId: "rcs-b",
    });
    diagnostics.logSyncClose(first, { code: 1000, reason: "a", source: "gateway-route" });
    diagnostics.logSyncClose(second, { code: 1000, reason: "b", source: "gateway-route" });
    expect(captures.map((fields) => fields.organizationId)).toEqual(["org-a", "org-b"]);
    expect(captures.map((fields) => fields.wsId)).toEqual(["ws-a", "ws-b"]);
  });
});
