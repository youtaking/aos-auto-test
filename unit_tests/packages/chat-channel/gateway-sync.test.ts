// gateway-sync.test.ts — chat-channel 初始同步逻辑测试
// 测试目标：PendingInitialSync 类型结构和 expected/received 集合匹配逻辑
// 业务意图：确保 Y.Doc 初始同步等待机制的完成判定正确

import { describe, test, expect } from "bun:test";

// ── 复制纯逻辑（来自 packages/chat-channel/src/channel/gateway-sync.ts）──

interface PendingInitialSync {
  expected: Set<string>;
  received: Set<string>;
  resolve: () => void;
}

/** 判断初始同步是否完成（所有 expected 的 doc 都已 received） */
function isSyncComplete(pending: PendingInitialSync): boolean {
  for (const docName of pending.expected) {
    if (!pending.received.has(docName)) return false;
  }
  return true;
}

/** 创建 PendingInitialSync 实例 */
function createPendingSync(docNames: string[], resolveFn: () => void): PendingInitialSync {
  return {
    expected: new Set(docNames),
    received: new Set(),
    resolve: resolveFn,
  };
}

/** 标记一个 doc 已收到，返回是否全部完成 */
function markDocReceived(pending: PendingInitialSync, docName: string): boolean {
  pending.received.add(docName);
  return isSyncComplete(pending);
}

// ── 测试 ──

describe("PendingInitialSync", () => {
  test("正向 - 创建时 expected 包含所有 doc 名", () => {
    const sync = createPendingSync(["chat:abc", "session:abc"], () => {});
    expect(sync.expected.size).toBe(2);
    expect(sync.expected.has("chat:abc")).toBe(true);
    expect(sync.expected.has("session:abc")).toBe(true);
  });

  test("正向 - 创建时 received 为空", () => {
    const sync = createPendingSync(["chat:abc"], () => {});
    expect(sync.received.size).toBe(0);
  });
});

describe("isSyncComplete", () => {
  test("正向 - 所有 expected 都已 received 时返回 true", () => {
    const sync = createPendingSync(["chat:abc", "session:abc"], () => {});
    sync.received.add("chat:abc");
    sync.received.add("session:abc");
    expect(isSyncComplete(sync)).toBe(true);
  });

  test("分支 - 部分 received 返回 false", () => {
    const sync = createPendingSync(["chat:abc", "session:abc"], () => {});
    sync.received.add("chat:abc");
    expect(isSyncComplete(sync)).toBe(false);
  });

  test("分支 - 全空时返回 false", () => {
    const sync = createPendingSync(["chat:abc"], () => {});
    expect(isSyncComplete(sync)).toBe(false);
  });

  test("边界 - expected 为空时返回 true（vacuously true）", () => {
    const sync = createPendingSync([], () => {});
    expect(isSyncComplete(sync)).toBe(true);
  });

  test("边界 - received 包含 expected 之外的 doc 不影响判定", () => {
    const sync = createPendingSync(["chat:abc"], () => {});
    sync.received.add("chat:abc");
    sync.received.add("extra:doc");
    expect(isSyncComplete(sync)).toBe(true);
  });
});

describe("markDocReceived", () => {
  test("正向 - 标记后 received 增加", () => {
    const sync = createPendingSync(["chat:abc", "session:abc"], () => {});
    markDocReceived(sync, "chat:abc");
    expect(sync.received.has("chat:abc")).toBe(true);
    expect(sync.received.size).toBe(1);
  });

  test("正向 - 最后一个 doc 标记后返回 true", () => {
    const sync = createPendingSync(["chat:abc", "session:abc"], () => {});
    markDocReceived(sync, "chat:abc");
    expect(markDocReceived(sync, "session:abc")).toBe(true);
  });

  test("分支 - 非最后一个返回 false", () => {
    const sync = createPendingSync(["chat:abc", "session:abc"], () => {});
    expect(markDocReceived(sync, "chat:abc")).toBe(false);
  });

  test("边界 - 重复标记同一 doc 不重复计数", () => {
    const sync = createPendingSync(["chat:abc"], () => {});
    markDocReceived(sync, "chat:abc");
    markDocReceived(sync, "chat:abc");
    expect(sync.received.size).toBe(1);
  });
});
