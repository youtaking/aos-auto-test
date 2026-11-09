// skill-mutation.test.ts — Skill 内容变更并发串行化测试
// 测试目标：withSkillMutation
// 业务意图：确保同组织同名的变更串行执行、多键按稳定顺序获取以避免死锁、异常也会释放锁
// 源：packages/resources/skill/src/server/services/skill-mutation.ts（main a7f477a9e）

import { describe, expect, test } from "bun:test";

// ── 复制实现 ──

const pending = new Map<string, Promise<void>>();

async function withSkillMutation<T>(
  organizationId: string,
  names: readonly string[],
  operation: () => Promise<T>,
): Promise<T> {
  const keys = [...new Set(names)].sort().map((name) => JSON.stringify([organizationId, name]));
  const acquire = async (index: number): Promise<T> => {
    if (index === keys.length) return operation();
    const key = keys[index]!;
    const previous = pending.get(key) ?? Promise.resolve();
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const current = previous.then(() => gate);
    pending.set(key, current);
    await previous;
    try {
      return await acquire(index + 1);
    } finally {
      release();
      if (pending.get(key) === current) pending.delete(key);
    }
  };
  return acquire(0);
}

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

const tick = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

// ── tests ──

describe("skill-mutation 变更串行化", () => {
  test("同一组织的同名变更串行执行", async () => {
    const order: string[] = [];
    const firstGate = deferred();
    const first = withSkillMutation("org-1", ["demo"], async () => {
      order.push("first-start");
      await firstGate.promise;
      order.push("first-end");
      return 1;
    });
    const second = withSkillMutation("org-1", ["demo"], async () => {
      order.push("second");
      return 2;
    });
    await tick();
    expect(order).toEqual(["first-start"]);
    firstGate.resolve();
    await expect(first).resolves.toBe(1);
    await expect(second).resolves.toBe(2);
    expect(order).toEqual(["first-start", "first-end", "second"]);
  });

  test("不同名称可并发执行", async () => {
    const gateA = deferred();
    const gateB = deferred();
    const events: string[] = [];
    const a = withSkillMutation("org-1", ["a"], async () => {
      events.push("a-start");
      await gateA.promise;
      events.push("a-end");
    });
    const b = withSkillMutation("org-1", ["b"], async () => {
      events.push("b-start");
      await gateB.promise;
      events.push("b-end");
    });
    await tick();
    expect(events).toEqual(["a-start", "b-start"]);
    gateA.resolve();
    gateB.resolve();
    await Promise.all([a, b]);
    expect(events).toEqual(["a-start", "b-start", "a-end", "b-end"]);
  });

  test("不同组织使用独立锁", async () => {
    const gate = deferred();
    const events: string[] = [];
    const orgOne = withSkillMutation("org-1", ["demo"], async () => {
      await gate.promise;
      events.push("org-1");
    });
    const orgTwo = withSkillMutation("org-2", ["demo"], async () => {
      events.push("org-2");
    });
    await orgTwo;
    expect(events).toEqual(["org-2"]);
    gate.resolve();
    await orgOne;
    expect(events).toEqual(["org-2", "org-1"]);
  });

  test("重复名称只获取一次锁", async () => {
    const order: string[] = [];
    const gate = deferred();
    const first = withSkillMutation("org-1", ["demo", "demo"], async () => {
      order.push("first");
      await gate.promise;
    });
    const second = withSkillMutation("org-1", ["demo"], async () => {
      order.push("second");
    });
    await tick();
    expect(order).toEqual(["first"]);
    gate.resolve();
    await Promise.all([first, second]);
    expect(order).toEqual(["first", "second"]);
  });

  test("多键按排序顺序获取，交叉请求不会死锁", async () => {
    const order: string[] = [];
    const first = withSkillMutation("org-1", ["b", "a"], async () => {
      order.push("first");
    });
    const second = withSkillMutation("org-1", ["a", "b"], async () => {
      order.push("second");
    });
    await Promise.all([first, second]);
    expect(order).toEqual(["first", "second"]);
  });

  test("操作抛错时仍释放锁", async () => {
    await expect(
      withSkillMutation("org-1", ["demo"], async () => {
        throw new Error("boom");
      }),
    ).rejects.toThrow("boom");
    await expect(withSkillMutation("org-1", ["demo"], async () => "ok")).resolves.toBe("ok");
  });

  test("空名称列表直接执行，不加锁", async () => {
    const order: string[] = [];
    const gate = deferred();
    const first = withSkillMutation("org-1", [], async () => {
      order.push("first");
      await gate.promise;
    });
    const second = withSkillMutation("org-1", [], async () => {
      order.push("second");
    });
    await tick();
    expect(order).toEqual(["first", "second"]);
    gate.resolve();
    await Promise.all([first, second]);
  });

  test("前一个操作结束后清理锁，后续请求不受影响", async () => {
    await withSkillMutation("org-1", ["demo"], async () => undefined);
    expect(pending.size).toBe(0);
    await withSkillMutation("org-1", ["demo"], async () => undefined);
    expect(pending.size).toBe(0);
  });
});
