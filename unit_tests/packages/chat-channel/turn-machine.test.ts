import { describe, test, expect } from "bun:test";

// ========== Pure function copies from packages/chat-channel/src/state/turn-machine.ts ==========
//
// convergeTurnExit / expireTurnPermissions / cancelTurnToolCalls 依赖 Yjs Y.Doc，
// 以下为纯逻辑复制：用 mock 接口替代 Yjs Map，保留完整业务逻辑，仅替换数据访问层。

function turnAssistantEntryId(turnId: string): string {
  return `${turnId}:assistant`;
}

// ---------- Mock interfaces (模拟 Yjs Map 接口) ----------

interface MockEntry {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
}

interface MockPermission {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
}

interface MockToolCall {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
}

interface MockSessionInfo {
  get(key: string): unknown;
  set(key: string, value: unknown): void;
}

interface MockChatStore {
  entries: Map<string, MockEntry>;
  toolCalls: Map<string, MockToolCall>;
}

interface MockSessionStore {
  sessionInfo: MockSessionInfo;
  pendingPermissions: Map<string, MockPermission>;
}

interface MockDocPair {
  chat: MockChatStore;
  session: MockSessionStore;
}

interface TurnExitOptions {
  finalStatus?: "completed" | "cancelled" | "interrupted" | "failed";
  entryStatus?: "completed" | "cancelled" | "error";
  meta?: { error?: { code: string; message: string } | null; usage?: Record<string, unknown> | null };
}

// ---------- Mock factory helpers ----------

function createMockEntry(data: Record<string, unknown> = {}): MockEntry {
  const store = new Map<string, unknown>(Object.entries(data));
  return {
    get: (key: string) => store.get(key),
    set: (key: string, value: unknown) => { store.set(key, value); },
  };
}

function createMockPermission(data: Record<string, unknown>): MockPermission {
  const store = new Map<string, unknown>(Object.entries(data));
  return {
    get: (key: string) => store.get(key),
    set: (key: string, value: unknown) => { store.set(key, value); },
  };
}

function createMockToolCall(data: Record<string, unknown>): MockToolCall {
  const store = new Map<string, unknown>(Object.entries(data));
  return {
    get: (key: string) => store.get(key),
    set: (key: string, value: unknown) => { store.set(key, value); },
  };
}

function createMockSessionInfo(data: Record<string, unknown> = {}): MockSessionInfo {
  const store = new Map<string, unknown>(Object.entries(data));
  return {
    get: (key: string) => store.get(key),
    set: (key: string, value: unknown) => { store.set(key, value); },
  };
}

function createMockDocPair(opts?: {
  entries?: Record<string, MockEntry>;
  toolCalls?: Record<string, MockToolCall>;
  permissions?: Record<string, MockPermission>;
  sessionInfo?: Record<string, unknown>;
}): MockDocPair {
  const chatEntries = new Map<string, MockEntry>();
  if (opts?.entries) {
    for (const [k, v] of Object.entries(opts.entries)) chatEntries.set(k, v);
  }
  const toolCalls = new Map<string, MockToolCall>();
  if (opts?.toolCalls) {
    for (const [k, v] of Object.entries(opts.toolCalls)) toolCalls.set(k, v);
  }
  const permissions = new Map<string, MockPermission>();
  if (opts?.permissions) {
    for (const [k, v] of Object.entries(opts.permissions)) permissions.set(k, v);
  }
  return {
    chat: { entries: chatEntries, toolCalls },
    session: {
      sessionInfo: createMockSessionInfo(opts?.sessionInfo),
      pendingPermissions: permissions,
    },
  };
}

// ---------- Pure logic copies (模拟 chat-writer 的访问辅助) ----------

function getEntry(chat: MockChatStore, entryId: string): MockEntry | null {
  return chat.entries.get(entryId) ?? null;
}

function setEntryStatus(chat: MockChatStore, entryId: string, status: string): void {
  const entry = getEntry(chat, entryId);
  if (entry) entry.set("status", status);
}

function setEntryTokenUsage(chat: MockChatStore, entryId: string, usage: Record<string, unknown>): void {
  const entry = getEntry(chat, entryId);
  if (entry && usage) entry.set("tokenUsage", usage);
}

function readActiveTurn(session: MockSessionStore): { turnId: string | null; turnStatus: string | null } {
  return {
    turnId: (session.sessionInfo.get("activeTurnId") as string) ?? null,
    turnStatus: (session.sessionInfo.get("activeTurnStatus") as string) ?? null,
  };
}

function setActiveTurn(session: MockSessionStore, turnId: string | null, turnStatus: string | null): void {
  session.sessionInfo.set("activeTurnId", turnId);
  session.sessionInfo.set("activeTurnStatus", turnStatus);
}

// ---------- Pure logic copies (turn-machine.ts 核心函数) ----------

/**
 * expireTurnPermissions: turn 退出时该 turn 的 pending 权限请求失效迁移（expired），不残留 pending 项。
 * 来源: packages/chat-channel/src/state/turn-machine.ts L58-63
 */
function expireTurnPermissions(pair: MockDocPair, turnId: string): void {
  for (const permission of pair.session.pendingPermissions.values()) {
    if (permission.get("turnId") !== turnId || permission.get("status") !== "pending") continue;
    permission.set("status", "expired");
  }
}

/**
 * cancelTurnToolCalls: turn 退出时该 turn 的工具调用收敛。
 * - awaiting_permission → cancelled
 * - running → cancelled
 * 返回收敛数量。
 * 来源: packages/chat-channel/src/state/turn-machine.ts L73-84
 */
function cancelTurnToolCalls(pair: MockDocPair, turnId: string): number {
  let count = 0;
  for (const tool of pair.chat.toolCalls.values()) {
    if (tool.get("turnId") !== turnId) continue;
    const status = tool.get("status");
    if (status === "awaiting_permission" || status === "running") {
      tool.set("status", "cancelled");
      count++;
    }
  }
  return count;
}

/**
 * convergeTurnExit: 统一收敛「turn 离开活动态」：assistant entry 终态 + 权限失效迁移 + 工具收敛。
 * 幂等：entry 不存在 / 权限已非 pending / 工具已终态时各自 no-op，可重复调用。
 * 来源: packages/chat-channel/src/state/turn-machine.ts L40-55
 */
function convergeTurnExit(pair: MockDocPair, turnId: string, opts: TurnExitOptions): void {
  const entryId = turnAssistantEntryId(turnId);
  const entry = getEntry(pair.chat, entryId);
  if (entry) {
    if (opts.entryStatus) setEntryStatus(pair.chat, entryId, opts.entryStatus);
    if (opts.meta?.error) entry.set("error", opts.meta.error);
    if (opts.meta?.usage) setEntryTokenUsage(pair.chat, entryId, opts.meta.usage);
  }
  // finalStatus 仅在 turnId 仍是 active 时写入：用户连发场景新 turn 已接管，不得回退
  if (opts.finalStatus) {
    const active = readActiveTurn(pair.session);
    if (active.turnId === turnId) setActiveTurn(pair.session, turnId, opts.finalStatus);
  }
  expireTurnPermissions(pair, turnId);
  cancelTurnToolCalls(pair, turnId);
}

// ========== Tests ==========

describe("turnAssistantEntryId", () => {
  test("creates assistant entry ID from turnId", () => {
    expect(turnAssistantEntryId("turn-123")).toBe("turn-123:assistant");
  });

  test("handles empty turnId", () => {
    expect(turnAssistantEntryId("")).toBe(":assistant");
  });

  test("handles turnId with special characters", () => {
    expect(turnAssistantEntryId("turn_replay_abc")).toBe("turn_replay_abc:assistant");
  });

  test("handles turnId with dots and hyphens", () => {
    expect(turnAssistantEntryId("turn.2024-01-01.abc-123")).toBe("turn.2024-01-01.abc-123:assistant");
  });

  test("is consistent (deterministic)", () => {
    const id1 = turnAssistantEntryId("same-turn");
    const id2 = turnAssistantEntryId("same-turn");
    expect(id1).toBe(id2);
  });

  test("different turnIds produce different entry IDs", () => {
    const id1 = turnAssistantEntryId("turn-a");
    const id2 = turnAssistantEntryId("turn-b");
    expect(id1).not.toBe(id2);
  });
});

describe("expireTurnPermissions", () => {
  test("将同 turnId 的 pending 权限迁移为 expired", () => {
    const pair = createMockDocPair({
      permissions: {
        "perm-1": createMockPermission({ permissionId: "perm-1", turnId: "turn-1", status: "pending" }),
        "perm-2": createMockPermission({ permissionId: "perm-2", turnId: "turn-1", status: "pending" }),
      },
    });
    expireTurnPermissions(pair, "turn-1");

    expect(pair.session.pendingPermissions.get("perm-1")!.get("status")).toBe("expired");
    expect(pair.session.pendingPermissions.get("perm-2")!.get("status")).toBe("expired");
  });

  test("不影响其他 turnId 的权限", () => {
    const pair = createMockDocPair({
      permissions: {
        "perm-1": createMockPermission({ permissionId: "perm-1", turnId: "turn-1", status: "pending" }),
        "perm-2": createMockPermission({ permissionId: "perm-2", turnId: "turn-2", status: "pending" }),
      },
    });
    expireTurnPermissions(pair, "turn-1");

    expect(pair.session.pendingPermissions.get("perm-1")!.get("status")).toBe("expired");
    expect(pair.session.pendingPermissions.get("perm-2")!.get("status")).toBe("pending");
  });

  test("不影响已经是 resolved 状态的权限", () => {
    const pair = createMockDocPair({
      permissions: {
        "perm-1": createMockPermission({ permissionId: "perm-1", turnId: "turn-1", status: "resolved" }),
      },
    });
    expireTurnPermissions(pair, "turn-1");

    expect(pair.session.pendingPermissions.get("perm-1")!.get("status")).toBe("resolved");
  });

  test("不影响已经是 expired 状态的权限（幂等）", () => {
    const pair = createMockDocPair({
      permissions: {
        "perm-1": createMockPermission({ permissionId: "perm-1", turnId: "turn-1", status: "expired" }),
      },
    });
    expireTurnPermissions(pair, "turn-1");

    expect(pair.session.pendingPermissions.get("perm-1")!.get("status")).toBe("expired");
  });

  test("空权限列表不抛错", () => {
    const pair = createMockDocPair();
    // 不应抛错
    expireTurnPermissions(pair, "turn-1");
  });

  test("混合状态：仅 pending 的被迁移", () => {
    const pair = createMockDocPair({
      permissions: {
        "perm-1": createMockPermission({ permissionId: "perm-1", turnId: "turn-1", status: "pending" }),
        "perm-2": createMockPermission({ permissionId: "perm-2", turnId: "turn-1", status: "resolved" }),
        "perm-3": createMockPermission({ permissionId: "perm-3", turnId: "turn-1", status: "expired" }),
        "perm-4": createMockPermission({ permissionId: "perm-4", turnId: "turn-2", status: "pending" }),
      },
    });
    expireTurnPermissions(pair, "turn-1");

    expect(pair.session.pendingPermissions.get("perm-1")!.get("status")).toBe("expired");
    expect(pair.session.pendingPermissions.get("perm-2")!.get("status")).toBe("resolved");
    expect(pair.session.pendingPermissions.get("perm-3")!.get("status")).toBe("expired");
    expect(pair.session.pendingPermissions.get("perm-4")!.get("status")).toBe("pending");
  });

  test("重复调用保持幂等", () => {
    const pair = createMockDocPair({
      permissions: {
        "perm-1": createMockPermission({ permissionId: "perm-1", turnId: "turn-1", status: "pending" }),
      },
    });
    expireTurnPermissions(pair, "turn-1");
    expireTurnPermissions(pair, "turn-1");
    expect(pair.session.pendingPermissions.get("perm-1")!.get("status")).toBe("expired");
  });
});

describe("cancelTurnToolCalls", () => {
  test("将 awaiting_permission 工具调用收敛为 cancelled", () => {
    const pair = createMockDocPair({
      toolCalls: {
        "tc-1": createMockToolCall({ toolCallId: "tc-1", turnId: "turn-1", status: "awaiting_permission" }),
      },
    });
    const count = cancelTurnToolCalls(pair, "turn-1");
    expect(count).toBe(1);
    expect(pair.chat.toolCalls.get("tc-1")!.get("status")).toBe("cancelled");
  });

  test("将 running 工具调用收敛为 cancelled", () => {
    const pair = createMockDocPair({
      toolCalls: {
        "tc-1": createMockToolCall({ toolCallId: "tc-1", turnId: "turn-1", status: "running" }),
      },
    });
    const count = cancelTurnToolCalls(pair, "turn-1");
    expect(count).toBe(1);
    expect(pair.chat.toolCalls.get("tc-1")!.get("status")).toBe("cancelled");
  });

  test("不影响已完成 (completed) 的工具调用", () => {
    const pair = createMockDocPair({
      toolCalls: {
        "tc-1": createMockToolCall({ toolCallId: "tc-1", turnId: "turn-1", status: "completed" }),
      },
    });
    const count = cancelTurnToolCalls(pair, "turn-1");
    expect(count).toBe(0);
    expect(pair.chat.toolCalls.get("tc-1")!.get("status")).toBe("completed");
  });

  test("不影响已取消 (cancelled) 的工具调用", () => {
    const pair = createMockDocPair({
      toolCalls: {
        "tc-1": createMockToolCall({ toolCallId: "tc-1", turnId: "turn-1", status: "cancelled" }),
      },
    });
    const count = cancelTurnToolCalls(pair, "turn-1");
    expect(count).toBe(0);
    expect(pair.chat.toolCalls.get("tc-1")!.get("status")).toBe("cancelled");
  });

  test("不影响已错误 (error) 的工具调用", () => {
    const pair = createMockDocPair({
      toolCalls: {
        "tc-1": createMockToolCall({ toolCallId: "tc-1", turnId: "turn-1", status: "error" }),
      },
    });
    const count = cancelTurnToolCalls(pair, "turn-1");
    expect(count).toBe(0);
    expect(pair.chat.toolCalls.get("tc-1")!.get("status")).toBe("error");
  });

  test("不影响其他 turnId 的工具调用", () => {
    const pair = createMockDocPair({
      toolCalls: {
        "tc-1": createMockToolCall({ toolCallId: "tc-1", turnId: "turn-1", status: "running" }),
        "tc-2": createMockToolCall({ toolCallId: "tc-2", turnId: "turn-2", status: "running" }),
      },
    });
    const count = cancelTurnToolCalls(pair, "turn-1");
    expect(count).toBe(1);
    expect(pair.chat.toolCalls.get("tc-1")!.get("status")).toBe("cancelled");
    expect(pair.chat.toolCalls.get("tc-2")!.get("status")).toBe("running");
  });

  test("返回收敛数量", () => {
    const pair = createMockDocPair({
      toolCalls: {
        "tc-1": createMockToolCall({ toolCallId: "tc-1", turnId: "turn-1", status: "running" }),
        "tc-2": createMockToolCall({ toolCallId: "tc-2", turnId: "turn-1", status: "awaiting_permission" }),
        "tc-3": createMockToolCall({ toolCallId: "tc-3", turnId: "turn-1", status: "completed" }),
        "tc-4": createMockToolCall({ toolCallId: "tc-4", turnId: "turn-1", status: "pending" }),
      },
    });
    const count = cancelTurnToolCalls(pair, "turn-1");
    expect(count).toBe(2);
  });

  test("空工具列表返回 0", () => {
    const pair = createMockDocPair();
    expect(cancelTurnToolCalls(pair, "turn-1")).toBe(0);
  });

  test("混合状态：仅 awaiting_permission 和 running 被收敛", () => {
    const pair = createMockDocPair({
      toolCalls: {
        "tc-1": createMockToolCall({ toolCallId: "tc-1", turnId: "turn-1", status: "running" }),
        "tc-2": createMockToolCall({ toolCallId: "tc-2", turnId: "turn-1", status: "awaiting_permission" }),
        "tc-3": createMockToolCall({ toolCallId: "tc-3", turnId: "turn-1", status: "completed" }),
        "tc-4": createMockToolCall({ toolCallId: "tc-4", turnId: "turn-1", status: "error" }),
        "tc-5": createMockToolCall({ toolCallId: "tc-5", turnId: "turn-1", status: "cancelled" }),
        "tc-6": createMockToolCall({ toolCallId: "tc-6", turnId: "turn-1", status: "pending" }),
      },
    });
    const count = cancelTurnToolCalls(pair, "turn-1");
    expect(count).toBe(2);
    expect(pair.chat.toolCalls.get("tc-1")!.get("status")).toBe("cancelled");
    expect(pair.chat.toolCalls.get("tc-2")!.get("status")).toBe("cancelled");
    expect(pair.chat.toolCalls.get("tc-3")!.get("status")).toBe("completed");
    expect(pair.chat.toolCalls.get("tc-4")!.get("status")).toBe("error");
    expect(pair.chat.toolCalls.get("tc-5")!.get("status")).toBe("cancelled");
    expect(pair.chat.toolCalls.get("tc-6")!.get("status")).toBe("pending");
  });
});

describe("convergeTurnExit", () => {
  test("完整收敛：entry 终态 + 权限失效 + 工具收敛 + turn 终态", () => {
    const entry = createMockEntry({ entryId: "turn-1:assistant", status: "streaming" });
    const pair = createMockDocPair({
      entries: { "turn-1:assistant": entry },
      permissions: {
        "perm-1": createMockPermission({ permissionId: "perm-1", turnId: "turn-1", status: "pending" }),
      },
      toolCalls: {
        "tc-1": createMockToolCall({ toolCallId: "tc-1", turnId: "turn-1", status: "running" }),
      },
      sessionInfo: { activeTurnId: "turn-1", activeTurnStatus: "running" },
    });

    convergeTurnExit(pair, "turn-1", {
      finalStatus: "completed",
      entryStatus: "completed",
    });

    // entry 终态
    expect(entry.get("status")).toBe("completed");
    // 权限失效
    expect(pair.session.pendingPermissions.get("perm-1")!.get("status")).toBe("expired");
    // 工具收敛
    expect(pair.chat.toolCalls.get("tc-1")!.get("status")).toBe("cancelled");
    // turn 终态
    expect(pair.session.sessionInfo.get("activeTurnStatus")).toBe("completed");
  });

  test("无 entry 时不抛错（entry 不存在）", () => {
    const pair = createMockDocPair({
      sessionInfo: { activeTurnId: "turn-1", activeTurnStatus: "running" },
    });
    // 不应抛错
    convergeTurnExit(pair, "turn-1", {
      finalStatus: "completed",
      entryStatus: "completed",
    });
    // 权限和工具收敛仍然执行
    expect(pair.session.sessionInfo.get("activeTurnStatus")).toBe("completed");
  });

  test("写入 error 元数据", () => {
    const entry = createMockEntry({ entryId: "turn-1:assistant", status: "streaming" });
    const pair = createMockDocPair({
      entries: { "turn-1:assistant": entry },
      sessionInfo: { activeTurnId: "turn-1", activeTurnStatus: "running" },
    });

    convergeTurnExit(pair, "turn-1", {
      finalStatus: "failed",
      entryStatus: "error",
      meta: { error: { code: "ERR_TEST", message: "test error" } },
    });

    expect(entry.get("status")).toBe("error");
    expect(entry.get("error")).toEqual({ code: "ERR_TEST", message: "test error" });
    expect(pair.session.sessionInfo.get("activeTurnStatus")).toBe("failed");
  });

  test("写入 usage 元数据", () => {
    const entry = createMockEntry({ entryId: "turn-1:assistant", status: "streaming" });
    const pair = createMockDocPair({
      entries: { "turn-1:assistant": entry },
      sessionInfo: { activeTurnId: "turn-1", activeTurnStatus: "running" },
    });

    convergeTurnExit(pair, "turn-1", {
      finalStatus: "completed",
      entryStatus: "completed",
      meta: { usage: { inputTokens: 100, outputTokens: 50 } },
    });

    expect(entry.get("tokenUsage")).toEqual({ inputTokens: 100, outputTokens: 50 });
  });

  test("error 为 null 时不写入 error 字段", () => {
    const entry = createMockEntry({ entryId: "turn-1:assistant", status: "streaming", error: null });
    const pair = createMockDocPair({
      entries: { "turn-1:assistant": entry },
      sessionInfo: { activeTurnId: "turn-1", activeTurnStatus: "running" },
    });

    convergeTurnExit(pair, "turn-1", {
      entryStatus: "completed",
      meta: { error: null },
    });

    // error 保持原值（null），不被覆盖
    expect(entry.get("error")).toBeNull();
  });

  test("usage 为 null 时不写入 tokenUsage 字段", () => {
    const entry = createMockEntry({ entryId: "turn-1:assistant", status: "streaming" });
    const pair = createMockDocPair({
      entries: { "turn-1:assistant": entry },
      sessionInfo: { activeTurnId: "turn-1", activeTurnStatus: "running" },
    });

    convergeTurnExit(pair, "turn-1", {
      entryStatus: "completed",
      meta: { usage: null },
    });

    expect(entry.get("tokenUsage")).toBeUndefined();
  });

  test("finalStatus 仅在 turnId 匹配 active turn 时写入", () => {
    const pair = createMockDocPair({
      sessionInfo: { activeTurnId: "turn-other", activeTurnStatus: "running" },
    });

    convergeTurnExit(pair, "turn-1", {
      finalStatus: "completed",
    });

    // active turn 不应被修改（turn-1 不是当前 active turn）
    expect(pair.session.sessionInfo.get("activeTurnId")).toBe("turn-other");
    expect(pair.session.sessionInfo.get("activeTurnStatus")).toBe("running");
  });

  test("无 finalStatus 时不修改 active turn", () => {
    const pair = createMockDocPair({
      sessionInfo: { activeTurnId: "turn-1", activeTurnStatus: "running" },
    });

    convergeTurnExit(pair, "turn-1", {
      entryStatus: "completed",
    });

    // active turn 不应被修改
    expect(pair.session.sessionInfo.get("activeTurnStatus")).toBe("running");
  });

  test("幂等：重复调用不破坏已收敛状态", () => {
    const entry = createMockEntry({ entryId: "turn-1:assistant", status: "streaming" });
    const pair = createMockDocPair({
      entries: { "turn-1:assistant": entry },
      permissions: {
        "perm-1": createMockPermission({ permissionId: "perm-1", turnId: "turn-1", status: "pending" }),
      },
      toolCalls: {
        "tc-1": createMockToolCall({ toolCallId: "tc-1", turnId: "turn-1", status: "running" }),
      },
      sessionInfo: { activeTurnId: "turn-1", activeTurnStatus: "running" },
    });

    convergeTurnExit(pair, "turn-1", { finalStatus: "completed", entryStatus: "completed" });
    convergeTurnExit(pair, "turn-1", { finalStatus: "completed", entryStatus: "completed" });

    expect(entry.get("status")).toBe("completed");
    expect(pair.session.pendingPermissions.get("perm-1")!.get("status")).toBe("expired");
    expect(pair.chat.toolCalls.get("tc-1")!.get("status")).toBe("cancelled");
  });

  test("cancelled 终态（用户取消场景）", () => {
    const entry = createMockEntry({ entryId: "turn-1:assistant", status: "streaming" });
    const pair = createMockDocPair({
      entries: { "turn-1:assistant": entry },
      permissions: {
        "perm-1": createMockPermission({ permissionId: "perm-1", turnId: "turn-1", status: "pending" }),
      },
      toolCalls: {
        "tc-1": createMockToolCall({ toolCallId: "tc-1", turnId: "turn-1", status: "awaiting_permission" }),
      },
      sessionInfo: { activeTurnId: "turn-1", activeTurnStatus: "awaiting_permission" },
    });

    convergeTurnExit(pair, "turn-1", {
      finalStatus: "cancelled",
      entryStatus: "cancelled",
    });

    expect(entry.get("status")).toBe("cancelled");
    expect(pair.session.sessionInfo.get("activeTurnStatus")).toBe("cancelled");
    expect(pair.session.pendingPermissions.get("perm-1")!.get("status")).toBe("expired");
    expect(pair.chat.toolCalls.get("tc-1")!.get("status")).toBe("cancelled");
  });

  test("interrupted 终态", () => {
    const pair = createMockDocPair({
      sessionInfo: { activeTurnId: "turn-1", activeTurnStatus: "running" },
    });

    convergeTurnExit(pair, "turn-1", {
      finalStatus: "interrupted",
    });

    expect(pair.session.sessionInfo.get("activeTurnStatus")).toBe("interrupted");
  });

  test("同时写入 error 和 usage 元数据", () => {
    const entry = createMockEntry({ entryId: "turn-1:assistant", status: "streaming" });
    const pair = createMockDocPair({
      entries: { "turn-1:assistant": entry },
      sessionInfo: { activeTurnId: "turn-1", activeTurnStatus: "running" },
    });

    convergeTurnExit(pair, "turn-1", {
      finalStatus: "failed",
      entryStatus: "error",
      meta: {
        error: { code: "TIMEOUT", message: "request timed out" },
        usage: { inputTokens: 200 },
      },
    });

    expect(entry.get("status")).toBe("error");
    expect(entry.get("error")).toEqual({ code: "TIMEOUT", message: "request timed out" });
    expect(entry.get("tokenUsage")).toEqual({ inputTokens: 200 });
  });

  test("不传 meta 时不写入 error 和 usage", () => {
    const entry = createMockEntry({ entryId: "turn-1:assistant", status: "streaming" });
    const pair = createMockDocPair({
      entries: { "turn-1:assistant": entry },
      sessionInfo: { activeTurnId: "turn-1", activeTurnStatus: "running" },
    });

    convergeTurnExit(pair, "turn-1", {
      finalStatus: "completed",
      entryStatus: "completed",
    });

    expect(entry.get("error")).toBeUndefined();
    expect(entry.get("tokenUsage")).toBeUndefined();
  });

  test("多权限多工具的综合收敛", () => {
    const entry = createMockEntry({ entryId: "turn-1:assistant", status: "streaming" });
    const pair = createMockDocPair({
      entries: { "turn-1:assistant": entry },
      permissions: {
        "perm-1": createMockPermission({ permissionId: "perm-1", turnId: "turn-1", status: "pending" }),
        "perm-2": createMockPermission({ permissionId: "perm-2", turnId: "turn-1", status: "pending" }),
        "perm-3": createMockPermission({ permissionId: "perm-3", turnId: "turn-2", status: "pending" }),
        "perm-4": createMockPermission({ permissionId: "perm-4", turnId: "turn-1", status: "resolved" }),
      },
      toolCalls: {
        "tc-1": createMockToolCall({ toolCallId: "tc-1", turnId: "turn-1", status: "running" }),
        "tc-2": createMockToolCall({ toolCallId: "tc-2", turnId: "turn-1", status: "awaiting_permission" }),
        "tc-3": createMockToolCall({ toolCallId: "tc-3", turnId: "turn-1", status: "completed" }),
        "tc-4": createMockToolCall({ toolCallId: "tc-4", turnId: "turn-2", status: "running" }),
      },
      sessionInfo: { activeTurnId: "turn-1", activeTurnStatus: "running" },
    });

    convergeTurnExit(pair, "turn-1", {
      finalStatus: "completed",
      entryStatus: "completed",
    });

    // entry 终态
    expect(entry.get("status")).toBe("completed");
    // turn-1 的 pending 权限失效
    expect(pair.session.pendingPermissions.get("perm-1")!.get("status")).toBe("expired");
    expect(pair.session.pendingPermissions.get("perm-2")!.get("status")).toBe("expired");
    // turn-2 的权限不受影响
    expect(pair.session.pendingPermissions.get("perm-3")!.get("status")).toBe("pending");
    // 已 resolved 的权限不变
    expect(pair.session.pendingPermissions.get("perm-4")!.get("status")).toBe("resolved");
    // turn-1 的 running/awaiting_permission 工具收敛
    expect(pair.chat.toolCalls.get("tc-1")!.get("status")).toBe("cancelled");
    expect(pair.chat.toolCalls.get("tc-2")!.get("status")).toBe("cancelled");
    // turn-1 的 completed 工具不变
    expect(pair.chat.toolCalls.get("tc-3")!.get("status")).toBe("completed");
    // turn-2 的工具不受影响
    expect(pair.chat.toolCalls.get("tc-4")!.get("status")).toBe("running");
    // turn 终态
    expect(pair.session.sessionInfo.get("activeTurnStatus")).toBe("completed");
  });
});
