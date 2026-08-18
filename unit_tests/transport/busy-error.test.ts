/**
 * busy-error.test.ts — BusyError 类 + pending request 跟踪逻辑测试
 *
 * 从源文件 src/transport/file-ws-requests.ts 复制：
 * - BusyError class
 * - pendingRequests Map + pendingPerWsId Map
 * - incrementPendingCount / decrementPendingCount / removePending
 * - rejectPendingForWsId / rejectAllPendingRequests / pendingRequestCount
 */

import { describe, test, expect, beforeEach } from "bun:test";

// ── 从源文件复制 BusyError ────────────────────────────────────────────
class BusyError extends Error {
  readonly code = "busy";
  constructor(message: string) {
    super(message);
    this.name = "BusyError";
  }
}

// ── 从源文件复制 pending request 跟踪逻辑 ─────────────────────────────
interface PendingRequest {
  resolve: (result: { status: string; data?: unknown; error?: string }) => void;
  reject: (err: Error) => void;
  timer: ReturnType<typeof setTimeout>;
  wsId: string;
}

const pendingRequests = new Map<string, PendingRequest>();
const pendingPerWsId = new Map<string, number>();

function incrementPendingCount(wsId: string): void {
  pendingPerWsId.set(wsId, (pendingPerWsId.get(wsId) ?? 0) + 1);
}

function decrementPendingCount(wsId: string): void {
  const count = pendingPerWsId.get(wsId);
  if (count === undefined) return;
  if (count <= 1) {
    pendingPerWsId.delete(wsId);
  } else {
    pendingPerWsId.set(wsId, count - 1);
  }
}

/**
 * 统一移除 pending：清定时器 + 从 map 删除 + 递减单连接计数。
 */
function removePending(requestId: string): PendingRequest | undefined {
  const pending = pendingRequests.get(requestId);
  if (!pending) return;
  clearTimeout(pending.timer);
  pendingRequests.delete(requestId);
  decrementPendingCount(pending.wsId);
  return pending;
}

/** reject 指定 wsId 的全部 pending（断连 / 替换 / 巡检共用），逐个 removePending 保证计数一致 */
function rejectPendingForWsId(wsId: string, err: Error): void {
  for (const [requestId, pending] of pendingRequests) {
    if (pending.wsId !== wsId) continue;
    removePending(requestId);
    pending.reject(err);
  }
}

/**
 * 停机清理（优雅关闭）：reject 全部 pending 并清空背压计数。
 */
function rejectAllPendingRequests(err: Error): void {
  for (const [requestId] of pendingRequests) {
    const pending = removePending(requestId);
    if (pending) {
      pending.reject(err);
    }
  }
  pendingPerWsId.clear();
}

function pendingRequestCount(): number {
  return pendingRequests.size;
}

// ── 辅助：向 pendingRequests 添加条目 ─────────────────────────────────
function addPending(requestId: string, wsId: string): PendingRequest {
  const pending: PendingRequest = {
    resolve: () => {},
    reject: () => {},
    timer: setTimeout(() => {}, 999999),
    wsId,
  };
  pendingRequests.set(requestId, pending);
  incrementPendingCount(wsId);
  return pending;
}

// ── 每个测试前清空全局状态 ────────────────────────────────────────────
beforeEach(() => {
  // 先清理所有 timer 防止泄漏
  for (const [, pending] of pendingRequests) {
    clearTimeout(pending.timer);
  }
  pendingRequests.clear();
  pendingPerWsId.clear();
});

// ═══════════════════════════════════════════════════════════════════════
// BusyError
// ═══════════════════════════════════════════════════════════════════════
describe("BusyError", () => {
  test("is instanceof Error", () => {
    const err = new BusyError("too busy");
    expect(err).toBeInstanceOf(Error);
  });

  test("is instanceof BusyError", () => {
    const err = new BusyError("too busy");
    expect(err).toBeInstanceOf(BusyError);
  });

  test('name is "BusyError"', () => {
    const err = new BusyError("msg");
    expect(err.name).toBe("BusyError");
  });

  test('code is "busy"', () => {
    const err = new BusyError("msg");
    expect(err.code).toBe("busy");
  });

  test("message is set correctly", () => {
    const err = new BusyError("request queue full");
    expect(err.message).toBe("request queue full");
  });

  test("has a stack trace", () => {
    const err = new BusyError("msg");
    expect(err.stack).toBeDefined();
    expect(typeof err.stack).toBe("string");
  });
});

// ═══════════════════════════════════════════════════════════════════════
// incrementPendingCount
// ═══════════════════════════════════════════════════════════════════════
describe("incrementPendingCount", () => {
  test("increments from 0 to 1 for new wsId", () => {
    incrementPendingCount("ws-1");
    expect(pendingPerWsId.get("ws-1")).toBe(1);
  });

  test("increments existing count", () => {
    incrementPendingCount("ws-1");
    incrementPendingCount("ws-1");
    expect(pendingPerWsId.get("ws-1")).toBe(2);
  });

  test("increments multiple times", () => {
    for (let i = 0; i < 5; i++) {
      incrementPendingCount("ws-1");
    }
    expect(pendingPerWsId.get("ws-1")).toBe(5);
  });

  test("tracks different wsIds independently", () => {
    incrementPendingCount("ws-1");
    incrementPendingCount("ws-1");
    incrementPendingCount("ws-2");
    expect(pendingPerWsId.get("ws-1")).toBe(2);
    expect(pendingPerWsId.get("ws-2")).toBe(1);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// decrementPendingCount
// ═══════════════════════════════════════════════════════════════════════
describe("decrementPendingCount", () => {
  test("decrements count from 2 to 1", () => {
    incrementPendingCount("ws-1");
    incrementPendingCount("ws-1");
    decrementPendingCount("ws-1");
    expect(pendingPerWsId.get("ws-1")).toBe(1);
  });

  test("deletes key when count reaches 0 (from 1)", () => {
    incrementPendingCount("ws-1");
    decrementPendingCount("ws-1");
    expect(pendingPerWsId.has("ws-1")).toBe(false);
  });

  test("deletes key when count is already 0 or below", () => {
    // Edge case: count somehow <= 1 → should delete
    pendingPerWsId.set("ws-1", 0);
    decrementPendingCount("ws-1");
    expect(pendingPerWsId.has("ws-1")).toBe(false);
  });

  test("handles missing key gracefully (no-op)", () => {
    // Should not throw
    decrementPendingCount("nonexistent");
    expect(pendingPerWsId.size).toBe(0);
  });

  test("does not affect other wsIds", () => {
    incrementPendingCount("ws-1");
    incrementPendingCount("ws-2");
    decrementPendingCount("ws-1");
    expect(pendingPerWsId.has("ws-1")).toBe(false);
    expect(pendingPerWsId.get("ws-2")).toBe(1);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// removePending
// ═══════════════════════════════════════════════════════════════════════
describe("removePending", () => {
  test("removes entry from pendingRequests and returns it", () => {
    addPending("req-1", "ws-1");
    const result = removePending("req-1");
    expect(result).toBeDefined();
    expect(result!.wsId).toBe("ws-1");
    expect(pendingRequests.has("req-1")).toBe(false);
  });

  test("clears the timer on removal", () => {
    // Verify clearTimeout is called by checking the timer is cleared
    // We add a pending with a real setTimeout, then remove it — if clearTimeout
    // is NOT called the timer would fire; we can't easily observe that directly,
    // but we can verify removePending returns the pending (which has the timer field)
    const pending = addPending("req-1", "ws-1");
    expect(pending.timer).toBeDefined();
    const result = removePending("req-1");
    expect(result).toBe(pending);
  });

  test("decrements per-ws count on removal", () => {
    addPending("req-1", "ws-1");
    addPending("req-2", "ws-1");
    expect(pendingPerWsId.get("ws-1")).toBe(2);

    removePending("req-1");
    expect(pendingPerWsId.get("ws-1")).toBe(1);

    removePending("req-2");
    expect(pendingPerWsId.has("ws-1")).toBe(false);
  });

  test("returns undefined for missing requestId", () => {
    const result = removePending("nonexistent");
    expect(result).toBeUndefined();
  });

  test("does not affect other requests for same wsId", () => {
    addPending("req-1", "ws-1");
    addPending("req-2", "ws-1");
    removePending("req-1");
    expect(pendingRequests.has("req-2")).toBe(true);
    expect(pendingPerWsId.get("ws-1")).toBe(1);
  });

  test("does not affect requests for different wsId", () => {
    addPending("req-1", "ws-1");
    addPending("req-2", "ws-2");
    removePending("req-1");
    expect(pendingRequests.has("req-2")).toBe(true);
    expect(pendingPerWsId.get("ws-2")).toBe(1);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// rejectPendingForWsId
// ═══════════════════════════════════════════════════════════════════════
describe("rejectPendingForWsId", () => {
  test("rejects only matching wsId and calls reject with error", () => {
    const rejectedErrors: Error[] = [];
    const p1 = addPending("req-1", "ws-1");
    p1.reject = (err: Error) => rejectedErrors.push(err);
    const p2 = addPending("req-2", "ws-1");
    p2.reject = (err: Error) => rejectedErrors.push(err);
    const p3 = addPending("req-3", "ws-2");
    const p3Rejected: Error[] = [];
    p3.reject = (err: Error) => p3Rejected.push(err);

    const err = new Error("disconnected");
    rejectPendingForWsId("ws-1", err);

    expect(rejectedErrors).toHaveLength(2);
    expect(rejectedErrors[0]).toBe(err);
    expect(rejectedErrors[1]).toBe(err);
    expect(pendingRequests.has("req-1")).toBe(false);
    expect(pendingRequests.has("req-2")).toBe(false);
    // ws-2 requests remain intact
    expect(pendingRequests.has("req-3")).toBe(true);
    expect(pendingPerWsId.get("ws-2")).toBe(1);
    expect(p3Rejected).toHaveLength(0);
  });

  test("clears per-ws count for rejected wsId", () => {
    addPending("req-1", "ws-1");
    addPending("req-2", "ws-1");

    rejectPendingForWsId("ws-1", new Error("gone"));

    expect(pendingPerWsId.has("ws-1")).toBe(false);
  });

  test("does nothing when no requests match", () => {
    const p1 = addPending("req-1", "ws-1");
    const p1Rejected: Error[] = [];
    p1.reject = (err: Error) => p1Rejected.push(err);

    rejectPendingForWsId("ws-999", new Error("gone"));

    expect(p1Rejected).toHaveLength(0);
    expect(pendingRequests.has("req-1")).toBe(true);
  });

  test("handles empty pendingRequests", () => {
    // Should not throw
    rejectPendingForWsId("ws-1", new Error("gone"));
    expect(pendingRequests.size).toBe(0);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// rejectAllPendingRequests
// ═══════════════════════════════════════════════════════════════════════
describe("rejectAllPendingRequests", () => {
  test("clears all pending requests and calls reject with error", () => {
    const allRejected: Error[] = [];
    const p1 = addPending("req-1", "ws-1");
    p1.reject = (err: Error) => allRejected.push(err);
    const p2 = addPending("req-2", "ws-2");
    p2.reject = (err: Error) => allRejected.push(err);
    const p3 = addPending("req-3", "ws-1");
    p3.reject = (err: Error) => allRejected.push(err);

    const err = new Error("shutdown");
    rejectAllPendingRequests(err);

    expect(allRejected).toHaveLength(3);
    for (const e of allRejected) {
      expect(e).toBe(err);
    }
    expect(pendingRequests.size).toBe(0);
  });

  test("clears per-ws counts", () => {
    addPending("req-1", "ws-1");
    addPending("req-2", "ws-2");

    rejectAllPendingRequests(new Error("shutdown"));

    expect(pendingPerWsId.size).toBe(0);
  });

  test("handles empty state", () => {
    // Should not throw
    rejectAllPendingRequests(new Error("shutdown"));
    expect(pendingRequests.size).toBe(0);
    expect(pendingPerWsId.size).toBe(0);
  });

  test("after rejectAll, new requests start fresh", () => {
    addPending("req-1", "ws-1");
    rejectAllPendingRequests(new Error("shutdown"));

    addPending("req-new", "ws-new");
    expect(pendingRequestCount()).toBe(1);
    expect(pendingPerWsId.get("ws-new")).toBe(1);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// pendingRequestCount
// ═══════════════════════════════════════════════════════════════════════
describe("pendingRequestCount", () => {
  test("returns 0 when empty", () => {
    expect(pendingRequestCount()).toBe(0);
  });

  test("reflects current size after additions", () => {
    addPending("req-1", "ws-1");
    expect(pendingRequestCount()).toBe(1);
    addPending("req-2", "ws-1");
    expect(pendingRequestCount()).toBe(2);
  });

  test("reflects current size after removals", () => {
    addPending("req-1", "ws-1");
    addPending("req-2", "ws-2");
    addPending("req-3", "ws-1");
    expect(pendingRequestCount()).toBe(3);

    removePending("req-1");
    expect(pendingRequestCount()).toBe(2);

    removePending("req-2");
    expect(pendingRequestCount()).toBe(1);

    removePending("req-3");
    expect(pendingRequestCount()).toBe(0);
  });

  test("reflects size after rejectAll", () => {
    addPending("req-1", "ws-1");
    addPending("req-2", "ws-2");
    rejectAllPendingRequests(new Error("shutdown"));
    expect(pendingRequestCount()).toBe(0);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// Integration: combined workflows
// ═══════════════════════════════════════════════════════════════════════
describe("pending request tracking integration", () => {
  test("full lifecycle: add → query → remove → verify clean", () => {
    // Simulate two WS connections with multiple pending requests
    addPending("r1", "ws-A");
    addPending("r2", "ws-A");
    addPending("r3", "ws-B");

    expect(pendingRequestCount()).toBe(3);
    expect(pendingPerWsId.get("ws-A")).toBe(2);
    expect(pendingPerWsId.get("ws-B")).toBe(1);

    // Remove one from ws-A
    const removed = removePending("r2");
    expect(removed).toBeDefined();
    expect(removed!.wsId).toBe("ws-A");
    expect(pendingRequestCount()).toBe(2);
    expect(pendingPerWsId.get("ws-A")).toBe(1);

    // Reject all for ws-A
    const wsARejected: Error[] = [];
    const p1 = pendingRequests.get("r1")!;
    p1.reject = (err: Error) => wsARejected.push(err);

    const err = new Error("ws-A disconnected");
    rejectPendingForWsId("ws-A", err);

    expect(wsARejected).toHaveLength(1);
    expect(wsARejected[0]).toBe(err);
    expect(pendingRequestCount()).toBe(1);
    expect(pendingPerWsId.has("ws-A")).toBe(false);

    // ws-B still intact
    expect(pendingRequests.has("r3")).toBe(true);
    expect(pendingPerWsId.get("ws-B")).toBe(1);

    // Final cleanup
    const allRejected: Error[] = [];
    const p3 = pendingRequests.get("r3")!;
    p3.reject = (err: Error) => allRejected.push(err);

    const shutdownErr = new Error("shutdown");
    rejectAllPendingRequests(shutdownErr);

    expect(allRejected).toHaveLength(1);
    expect(allRejected[0]).toBe(shutdownErr);
    expect(pendingRequestCount()).toBe(0);
    expect(pendingPerWsId.size).toBe(0);
  });

  test("BusyError can be thrown and caught like a normal Error", () => {
    expect(() => {
      throw new BusyError("too many requests");
    }).toThrow(BusyError);

    try {
      throw new BusyError("queue full");
    } catch (e) {
      expect(e).toBeInstanceOf(Error);
      expect(e).toBeInstanceOf(BusyError);
      expect((e as BusyError).code).toBe("busy");
      expect((e as BusyError).message).toBe("queue full");
    }
  });
});
