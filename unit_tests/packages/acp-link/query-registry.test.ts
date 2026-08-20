// query-registry.test.ts — ACP 活跃 Query 注册表测试
// 测试目标：register/unregister/cancel/peekCancelRequested 的并发安全语义
// 业务意图：确保多会话并发时 cancel 只中断目标 session 的 query

import { describe, test, expect, beforeEach } from "bun:test";

// ── 复制纯函数（来自 packages/acp-link/src/client/query-registry.ts）──

class ActiveQueryRegistry<T extends { interrupt(): Promise<void> }> {
  private readonly queries = new Map<string, { query: T; cancelRequested: boolean }>();
  private static readonly NO_SESSION_KEY = "__no_session__";
  private readonly reportError?: (message: string, error?: unknown) => void;

  constructor(options: { reportError?: (message: string, error?: unknown) => void } = {}) {
    this.reportError = options.reportError;
  }

  private keyOf(sessionId: string | null): string {
    return sessionId ?? ActiveQueryRegistry.NO_SESSION_KEY;
  }

  register(sessionId: string | null, query: T): void {
    const key = this.keyOf(sessionId);
    if (this.queries.has(key)) {
      this.reportError?.(
        `[ActiveQueryRegistry] duplicate register for session "${key}": concurrent prompts ` +
          "on the same session violate the single-active-turn protocol; the previous query is no longer interruptible",
      );
    }
    this.queries.set(key, { query, cancelRequested: false });
  }

  peekCancelRequested(sessionId: string | null): boolean {
    return this.queries.get(this.keyOf(sessionId))?.cancelRequested ?? false;
  }

  unregister(sessionId: string | null): void {
    this.queries.delete(this.keyOf(sessionId));
  }

  async cancel(sessionId: string | null): Promise<boolean> {
    const entry = this.queries.get(this.keyOf(sessionId));
    if (!entry) return false;
    if (entry.cancelRequested) return true;
    entry.cancelRequested = true;
    try {
      await entry.query.interrupt();
    } catch {
      // interrupt 失败不阻塞 cancel
    }
    return true;
  }
}

// ── 辅助 ──

function makeQuery(interrupted: { called: boolean } = { called: false }) {
  return {
    interrupt: async () => {
      interrupted.called = true;
    },
  };
}

function makeThrowingQuery() {
  return {
    interrupt: async () => {
      throw new Error("interrupt failed");
    },
  };
}

// ── 测试 ──

describe("ActiveQueryRegistry", () => {
  let registry: ActiveQueryRegistry<{ interrupt(): Promise<void> }>;

  beforeEach(() => {
    registry = new ActiveQueryRegistry();
  });

  describe("register / unregister", () => {
    test("正向 - 注册后可 cancel", async () => {
      const q = makeQuery();
      registry.register("s1", q);
      expect(await registry.cancel("s1")).toBe(true);
    });

    test("正向 - 注销后 cancel 返回 false", async () => {
      const q = makeQuery();
      registry.register("s1", q);
      registry.unregister("s1");
      expect(await registry.cancel("s1")).toBe(false);
    });
  });

  describe("cancel", () => {
    test("正向 - cancel 调用 interrupt", async () => {
      const interrupted = { called: false };
      registry.register("s1", makeQuery(interrupted));
      await registry.cancel("s1");
      expect(interrupted.called).toBe(true);
    });

    test("正向 - cancel 后 peekCancelRequested 返回 true", async () => {
      registry.register("s1", makeQuery());
      await registry.cancel("s1");
      expect(registry.peekCancelRequested("s1")).toBe(true);
    });

    test("正向 - 未注册 session cancel 返回 false", async () => {
      expect(await registry.cancel("missing")).toBe(false);
    });

    test("正向 - 重复 cancel 幂等，不重复调 interrupt", async () => {
      let count = 0;
      const q = { interrupt: async () => { count++; } };
      registry.register("s1", q);
      await registry.cancel("s1");
      await registry.cancel("s1");
      expect(count).toBe(1);
    });

    test("分支 - interrupt 抛错不阻塞 cancel，仍返回 true", async () => {
      registry.register("s1", makeThrowingQuery());
      const result = await registry.cancel("s1");
      expect(result).toBe(true);
      expect(registry.peekCancelRequested("s1")).toBe(true);
    });

    test("隔离 - null session 使用兜底键", async () => {
      const q = makeQuery();
      registry.register(null, q);
      expect(await registry.cancel(null)).toBe(true);
    });
  });

  describe("peekCancelRequested", () => {
    test("正向 - 未注册返回 false", () => {
      expect(registry.peekCancelRequested("s1")).toBe(false);
    });

    test("正向 - 注册未 cancel 返回 false", () => {
      registry.register("s1", makeQuery());
      expect(registry.peekCancelRequested("s1")).toBe(false);
    });

    test("正向 - cancel 后返回 true", async () => {
      registry.register("s1", makeQuery());
      await registry.cancel("s1");
      expect(registry.peekCancelRequested("s1")).toBe(true);
    });
  });

  describe("duplicate register 告警", () => {
    test("正向 - 重复注册触发 reportError", () => {
      const errors: string[] = [];
      const reg = new ActiveQueryRegistry({ reportError: (msg) => errors.push(msg) });
      reg.register("s1", makeQuery());
      reg.register("s1", makeQuery());
      expect(errors.length).toBe(1);
      expect(errors[0]).toContain("duplicate register");
    });

    test("分支 - 无 reportError 时静默覆盖", () => {
      const reg = new ActiveQueryRegistry();
      reg.register("s1", makeQuery());
      expect(() => reg.register("s1", makeQuery())).not.toThrow();
    });
  });

  describe("多会话隔离", () => {
    test("正向 - 不同 session 的 cancel 互不干扰", async () => {
      const q1 = makeQuery();
      const q2 = makeQuery();
      registry.register("s1", q1);
      registry.register("s2", q2);
      await registry.cancel("s1");
      expect(registry.peekCancelRequested("s1")).toBe(true);
      expect(registry.peekCancelRequested("s2")).toBe(false);
    });
  });
});
