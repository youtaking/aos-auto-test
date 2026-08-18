// query-registry.test.ts — 活跃 SDK Query 注册表测试
// 测试目标：ActiveQueryRegistry 的 register/unregister/cancel 生命周期
// 业务意图：确保多会话并发场景下 cancel 精确中断目标 session，
//          重复 cancel 幂等，interrupt 失败不阻塞取消语义

import { describe, expect, test } from "bun:test";

// ── 复制源类（纯逻辑，无外部依赖）──

interface Interruptible {
  interrupt(): Promise<void>;
}

class ActiveQueryRegistry<T extends Interruptible> {
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

// ── 测试辅助 ──

function makeQuery(interrupted: { value: boolean }): Interruptible {
  return {
    interrupt: async () => {
      interrupted.value = true;
    },
  };
}

function makeFailingQuery(): Interruptible {
  return {
    interrupt: async () => {
      throw new Error("interrupt failed");
    },
  };
}

// ── register + cancel ──

describe("register + cancel", () => {
  // 注册后 cancel 返回 true 并调用 interrupt
  test("cancel 已注册的 session 返回 true 并调用 interrupt", async () => {
    const registry = new ActiveQueryRegistry();
    const interrupted = { value: false };
    registry.register("ses_1", makeQuery(interrupted));

    const result = await registry.cancel("ses_1");
    expect(result).toBe(true);
    expect(interrupted.value).toBe(true);
  });

  // cancel 后 peekCancelRequested 返回 true
  test("cancel 后 peekCancelRequested 返回 true", async () => {
    const registry = new ActiveQueryRegistry();
    registry.register("ses_1", makeQuery({ value: false }));

    await registry.cancel("ses_1");
    expect(registry.peekCancelRequested("ses_1")).toBe(true);
  });

  // cancel 未注册的 session 返回 false
  test("cancel 未注册的 session 返回 false", async () => {
    const registry = new ActiveQueryRegistry();
    const result = await registry.cancel("ses_unknown");
    expect(result).toBe(false);
  });
});

// ── unregister ──

describe("unregister", () => {
  // unregister 后 cancel 返回 false
  test("unregister 后 cancel 返回 false", async () => {
    const registry = new ActiveQueryRegistry();
    registry.register("ses_1", makeQuery({ value: false }));
    registry.unregister("ses_1");

    const result = await registry.cancel("ses_1");
    expect(result).toBe(false);
  });

  // unregister 后 peekCancelRequested 返回 false
  test("unregister 后 peekCancelRequested 返回 false", () => {
    const registry = new ActiveQueryRegistry();
    registry.register("ses_1", makeQuery({ value: false }));
    registry.unregister("ses_1");

    expect(registry.peekCancelRequested("ses_1")).toBe(false);
  });

  // unregister 未注册的 session 不抛错
  test("unregister 未注册的 session 不抛错", () => {
    const registry = new ActiveQueryRegistry();
    expect(() => registry.unregister("ses_x")).not.toThrow();
  });
});

// ── 重复 cancel 幂等 ──

describe("重复 cancel 幂等", () => {
  // 第二次 cancel 返回 true 但不重复调用 interrupt
  test("重复 cancel 返回 true 且 interrupt 只调用一次", async () => {
    const registry = new ActiveQueryRegistry();
    let interruptCount = 0;
    const query: Interruptible = {
      interrupt: async () => { interruptCount++; },
    };
    registry.register("ses_1", query);

    await registry.cancel("ses_1");
    await registry.cancel("ses_1");
    expect(interruptCount).toBe(1);
  });
});

// ── interrupt 失败 ──

describe("interrupt 失败处理", () => {
  // interrupt 抛错时 cancel 仍返回 true，cancelRequested 已置位
  test("interrupt 抛错时 cancel 仍返回 true", async () => {
    const registry = new ActiveQueryRegistry();
    registry.register("ses_1", makeFailingQuery());

    const result = await registry.cancel("ses_1");
    expect(result).toBe(true);
    expect(registry.peekCancelRequested("ses_1")).toBe(true);
  });
});

// ── null sessionId ──

describe("null sessionId（兜底键）", () => {
  // null sessionId 可注册和 cancel
  test("null sessionId 注册后可 cancel", async () => {
    const registry = new ActiveQueryRegistry();
    const interrupted = { value: false };
    registry.register(null, makeQuery(interrupted));

    const result = await registry.cancel(null);
    expect(result).toBe(true);
    expect(interrupted.value).toBe(true);
  });

  // null 和 string sessionId 互不干扰
  test("null 和 string sessionId 互不干扰", async () => {
    const registry = new ActiveQueryRegistry();
    const int1 = { value: false };
    const int2 = { value: false };
    registry.register(null, makeQuery(int1));
    registry.register("ses_1", makeQuery(int2));

    await registry.cancel(null);
    expect(int1.value).toBe(true);
    expect(int2.value).toBe(false);
  });

  // 未注册 null 时 cancel(null) 返回 false
  test("未注册 null 时 cancel(null) 返回 false", async () => {
    const registry = new ActiveQueryRegistry();
    const result = await registry.cancel(null);
    expect(result).toBe(false);
  });
});

// ── 多 session 隔离 ──

describe("多 session 隔离", () => {
  // cancel session A 不影响 session B
  test("cancel 一个 session 不影响另一个 session", async () => {
    const registry = new ActiveQueryRegistry();
    const intA = { value: false };
    const intB = { value: false };
    registry.register("ses_A", makeQuery(intA));
    registry.register("ses_B", makeQuery(intB));

    await registry.cancel("ses_A");
    expect(intA.value).toBe(true);
    expect(intB.value).toBe(false);
    expect(registry.peekCancelRequested("ses_B")).toBe(false);
  });
});

// ── 同 session 重复 register ──

describe("同 session 重复 register", () => {
  // 同 session 二次注册覆盖前一个，reportError 被调用
  test("重复 register 触发 reportError", () => {
    const errors: string[] = [];
    const registry = new ActiveQueryRegistry({
      reportError: (msg) => errors.push(msg),
    });
    registry.register("ses_1", makeQuery({ value: false }));
    registry.register("ses_1", makeQuery({ value: false }));

    expect(errors.length).toBe(1);
    expect(errors[0]).toContain("duplicate register");
  });

  // 无 reportError 时不抛错
  test("无 reportError 时重复 register 不抛错", () => {
    const registry = new ActiveQueryRegistry();
    expect(() => {
      registry.register("ses_1", makeQuery({ value: false }));
      registry.register("ses_1", makeQuery({ value: false }));
    }).not.toThrow();
  });

  // 覆盖后 cancel 中断的是新 query
  test("覆盖后 cancel 中断新 query", async () => {
    const registry = new ActiveQueryRegistry();
    const old = { value: false };
    const newer = { value: false };
    registry.register("ses_1", makeQuery(old));
    registry.register("ses_1", makeQuery(newer));

    await registry.cancel("ses_1");
    expect(old.value).toBe(false); // 旧 query 未被 interrupt
    expect(newer.value).toBe(true); // 新 query 被 interrupt
  });
});

// ── peekCancelRequested 初始值 ──

describe("peekCancelRequested 初始值", () => {
  // 未注册的 session peekCancelRequested 返回 false
  test("未注册 session 返回 false", () => {
    const registry = new ActiveQueryRegistry();
    expect(registry.peekCancelRequested("ses_new")).toBe(false);
  });

  // 已注册但未 cancel 的 session 返回 false
  test("已注册但未 cancel 返回 false", () => {
    const registry = new ActiveQueryRegistry();
    registry.register("ses_1", makeQuery({ value: false }));
    expect(registry.peekCancelRequested("ses_1")).toBe(false);
  });
});
