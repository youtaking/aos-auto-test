// instance-registry.test.ts — InstanceRegistry 内存注册表测试
// 测试目标：register/unregister/get/has/touchActivity/attachRelay/detachRelay/
//          getByEnvironment/nextInstanceNumber/deleteCounter/reconcile/clear/size/entries
// 业务意图：确保 RCS 实例补充信息的内存注册表在各种生命周期操作下状态正确

import { beforeEach, describe, expect, test } from "bun:test";

// ── 复制 InstanceRegistry 类（纯内存，无外部依赖）──

interface InstanceSupplement {
  environmentId: string;
  instanceNumber: number;
  userId: string;
  spawnSource: "interactive" | "scheduled" | "system";
  lastActivityAt: number;
  relayCount: number;
  lastRelayDetachedAt: number | null;
  organizationId?: string;
  [key: string]: unknown;
}

class InstanceRegistry {
  static readonly IDLE_RECLAIM_CLOSE_CODE = 4001;

  private supplements = new Map<string, InstanceSupplement>();
  private envCounters = new Map<string, number>();
  private byEnvironment = new Map<string, Set<string>>();

  register(instanceId: string, supplement: InstanceSupplement): void {
    this.supplements.set(instanceId, supplement);
    let set = this.byEnvironment.get(supplement.environmentId);
    if (!set) {
      set = new Set();
      this.byEnvironment.set(supplement.environmentId, set);
    }
    set.add(instanceId);
  }

  unregister(instanceId: string): void {
    const sup = this.supplements.get(instanceId);
    if (!sup) return;
    this.supplements.delete(instanceId);
    const set = this.byEnvironment.get(sup.environmentId);
    if (set) {
      set.delete(instanceId);
      if (set.size === 0) this.byEnvironment.delete(sup.environmentId);
    }
  }

  get(instanceId: string): InstanceSupplement | undefined {
    return this.supplements.get(instanceId);
  }

  has(instanceId: string): boolean {
    return this.supplements.has(instanceId);
  }

  touchActivity(instanceId: string, at = Date.now()): void {
    const supplement = this.supplements.get(instanceId);
    if (!supplement) return;
    supplement.lastActivityAt = at;
    if (supplement.relayCount > 0) {
      supplement.lastRelayDetachedAt = null;
    }
  }

  attachRelay(instanceId: string, at = Date.now()): void {
    const supplement = this.supplements.get(instanceId);
    if (!supplement) return;
    supplement.relayCount += 1;
    supplement.lastActivityAt = at;
    supplement.lastRelayDetachedAt = null;
  }

  detachRelay(instanceId: string, at = Date.now()): void {
    const supplement = this.supplements.get(instanceId);
    if (!supplement) return;
    supplement.relayCount = Math.max(0, supplement.relayCount - 1);
    if (supplement.relayCount === 0) {
      supplement.lastRelayDetachedAt = at;
    }
  }

  getByEnvironment(environmentId: string): Array<[string, InstanceSupplement]> {
    const ids = this.byEnvironment.get(environmentId);
    if (!ids) return [];
    return [...ids]
      .map((id) => [id, this.supplements.get(id)!] as [string, InstanceSupplement])
      .filter(([, s]) => s);
  }

  nextInstanceNumber(environmentId: string): number {
    const counter = this.envCounters.get(environmentId) ?? 0;
    const instances = this.getByEnvironment(environmentId);
    const maxFromInstances = instances.length > 0 ? Math.max(...instances.map(([, s]) => s.instanceNumber)) : 0;
    const next = Math.max(counter, maxFromInstances) + 1;
    this.envCounters.set(environmentId, next);
    return next;
  }

  deleteCounter(environmentId: string): void {
    const instances = this.getByEnvironment(environmentId);
    if (instances.length === 0) {
      this.envCounters.delete(environmentId);
    }
  }

  clear(): void {
    this.supplements.clear();
    this.envCounters.clear();
    this.byEnvironment.clear();
  }

  entries(): IterableIterator<[string, InstanceSupplement]> {
    return this.supplements.entries();
  }

  get size(): number {
    return this.supplements.size;
  }

  reconcile(listCoreInstances: () => Array<{ instanceId: string }>): void {
    const coreIds = new Set(listCoreInstances().map((i) => i.instanceId));
    const orphaned: string[] = [];
    for (const [id] of this.supplements) {
      if (!coreIds.has(id)) {
        orphaned.push(id);
      }
    }
    for (const id of orphaned) {
      this.unregister(id);
    }
  }
}

// ── 辅助工厂 ──

function makeSupplement(overrides: Partial<InstanceSupplement> = {}): InstanceSupplement {
  return {
    environmentId: "env-1",
    instanceNumber: 1,
    userId: "user-1",
    spawnSource: "interactive",
    lastActivityAt: 1000,
    relayCount: 0,
    lastRelayDetachedAt: null,
    ...overrides,
  };
}

// ── tests ──

describe("InstanceRegistry 内存注册表", () => {
  let registry: InstanceRegistry;

  beforeEach(() => {
    registry = new InstanceRegistry();
  });

  // ── 静态常量 ──

  test("IDLE_RECLAIM_CLOSE_CODE 值为 4001", () => {
    expect(InstanceRegistry.IDLE_RECLAIM_CLOSE_CODE).toBe(4001);
  });

  // ── register / get / has / unregister 生命周期 ──

  describe("register / get / has / unregister", () => {
    test("register 后 get 返回 supplement", () => {
      const sup = makeSupplement();
      registry.register("inst-1", sup);
      expect(registry.get("inst-1")).toBe(sup);
    });

    test("register 后 has 返回 true", () => {
      registry.register("inst-1", makeSupplement());
      expect(registry.has("inst-1")).toBe(true);
    });

    test("未注册的实例 get 返回 undefined, has 返回 false", () => {
      expect(registry.get("nonexistent")).toBeUndefined();
      expect(registry.has("nonexistent")).toBe(false);
    });

    test("unregister 后 get 返回 undefined, has 返回 false", () => {
      registry.register("inst-1", makeSupplement());
      registry.unregister("inst-1");
      expect(registry.get("inst-1")).toBeUndefined();
      expect(registry.has("inst-1")).toBe(false);
    });

    test("unregister 不存在的实例不抛错", () => {
      expect(() => registry.unregister("nonexistent")).not.toThrow();
    });

    test("register 多个实例互不影响", () => {
      registry.register("inst-1", makeSupplement({ userId: "alice" }));
      registry.register("inst-2", makeSupplement({ userId: "bob" }));
      expect(registry.get("inst-1")!.userId).toBe("alice");
      expect(registry.get("inst-2")!.userId).toBe("bob");
    });

    test("重复 register 同一 ID 覆盖旧数据", () => {
      registry.register("inst-1", makeSupplement({ userId: "alice" }));
      registry.register("inst-1", makeSupplement({ userId: "bob" }));
      expect(registry.get("inst-1")!.userId).toBe("bob");
      expect(registry.size).toBe(1);
    });
  });

  // ── size 和 entries ──

  describe("size 和 entries", () => {
    test("空注册表 size 为 0", () => {
      expect(registry.size).toBe(0);
    });

    test("register 后 size 递增", () => {
      registry.register("inst-1", makeSupplement());
      registry.register("inst-2", makeSupplement({ environmentId: "env-2" }));
      expect(registry.size).toBe(2);
    });

    test("unregister 后 size 递减", () => {
      registry.register("inst-1", makeSupplement());
      registry.register("inst-2", makeSupplement({ environmentId: "env-2" }));
      registry.unregister("inst-1");
      expect(registry.size).toBe(1);
    });

    test("entries 返回所有注册条目", () => {
      registry.register("inst-1", makeSupplement({ userId: "alice" }));
      registry.register("inst-2", makeSupplement({ userId: "bob", environmentId: "env-2" }));
      const entries = [...registry.entries()];
      expect(entries.length).toBe(2);
      const ids = entries.map(([id]) => id).sort();
      expect(ids).toEqual(["inst-1", "inst-2"]);
    });

    test("entries 空注册表返回空迭代器", () => {
      const entries = [...registry.entries()];
      expect(entries.length).toBe(0);
    });
  });

  // ── byEnvironment 索引 ──

  describe("getByEnvironment 按环境查询", () => {
    test("注册后按环境查询返回正确条目", () => {
      registry.register("inst-1", makeSupplement({ environmentId: "env-1" }));
      registry.register("inst-2", makeSupplement({ environmentId: "env-1" }));
      registry.register("inst-3", makeSupplement({ environmentId: "env-2" }));

      const env1 = registry.getByEnvironment("env-1");
      expect(env1.length).toBe(2);
      const env1Ids = env1.map(([id]) => id).sort();
      expect(env1Ids).toEqual(["inst-1", "inst-2"]);
    });

    test("查询无结果的环境返回空数组", () => {
      registry.register("inst-1", makeSupplement({ environmentId: "env-1" }));
      expect(registry.getByEnvironment("env-nonexistent")).toEqual([]);
    });

    test("unregister 后 byEnvironment 索引正确清理", () => {
      registry.register("inst-1", makeSupplement({ environmentId: "env-1" }));
      registry.register("inst-2", makeSupplement({ environmentId: "env-1" }));
      registry.unregister("inst-1");

      const env1 = registry.getByEnvironment("env-1");
      expect(env1.length).toBe(1);
      expect(env1[0][0]).toBe("inst-2");
    });

    test("环境最后一个实例注销后索引项被移除", () => {
      registry.register("inst-1", makeSupplement({ environmentId: "env-1" }));
      registry.unregister("inst-1");
      expect(registry.getByEnvironment("env-1")).toEqual([]);
    });
  });

  // ── touchActivity ──

  describe("touchActivity 更新活跃时间", () => {
    test("更新 lastActivityAt", () => {
      registry.register("inst-1", makeSupplement({ lastActivityAt: 1000 }));
      registry.touchActivity("inst-1", 5000);
      expect(registry.get("inst-1")!.lastActivityAt).toBe(5000);
    });

    test("不存在的实例不抛错", () => {
      expect(() => registry.touchActivity("nonexistent", 5000)).not.toThrow();
    });

    test("relayCount > 0 时清空 lastRelayDetachedAt", () => {
      registry.register("inst-1", makeSupplement({ relayCount: 1, lastRelayDetachedAt: 3000 }));
      registry.touchActivity("inst-1", 5000);
      expect(registry.get("inst-1")!.lastRelayDetachedAt).toBeNull();
    });

    test("relayCount === 0 时不影响 lastRelayDetachedAt", () => {
      registry.register("inst-1", makeSupplement({ relayCount: 0, lastRelayDetachedAt: 3000 }));
      registry.touchActivity("inst-1", 5000);
      expect(registry.get("inst-1")!.lastRelayDetachedAt).toBe(3000);
    });
  });

  // ── attachRelay ──

  describe("attachRelay relay 连接附着", () => {
    test("relayCount 递增", () => {
      registry.register("inst-1", makeSupplement({ relayCount: 0 }));
      registry.attachRelay("inst-1", 2000);
      expect(registry.get("inst-1")!.relayCount).toBe(1);
    });

    test("多次 attach 持续递增", () => {
      registry.register("inst-1", makeSupplement({ relayCount: 0 }));
      registry.attachRelay("inst-1", 2000);
      registry.attachRelay("inst-1", 3000);
      registry.attachRelay("inst-1", 4000);
      expect(registry.get("inst-1")!.relayCount).toBe(3);
    });

    test("同时更新 lastActivityAt", () => {
      registry.register("inst-1", makeSupplement({ lastActivityAt: 1000 }));
      registry.attachRelay("inst-1", 5000);
      expect(registry.get("inst-1")!.lastActivityAt).toBe(5000);
    });

    test("清空 lastRelayDetachedAt", () => {
      registry.register("inst-1", makeSupplement({ relayCount: 0, lastRelayDetachedAt: 3000 }));
      registry.attachRelay("inst-1", 5000);
      expect(registry.get("inst-1")!.lastRelayDetachedAt).toBeNull();
    });

    test("不存在的实例不抛错", () => {
      expect(() => registry.attachRelay("nonexistent", 5000)).not.toThrow();
    });
  });

  // ── detachRelay ──

  describe("detachRelay relay 连接分离", () => {
    test("relayCount 递减", () => {
      registry.register("inst-1", makeSupplement({ relayCount: 2 }));
      registry.detachRelay("inst-1", 5000);
      expect(registry.get("inst-1")!.relayCount).toBe(1);
    });

    test("计数归零时设置 lastRelayDetachedAt", () => {
      registry.register("inst-1", makeSupplement({ relayCount: 1, lastRelayDetachedAt: null }));
      registry.detachRelay("inst-1", 5000);
      expect(registry.get("inst-1")!.relayCount).toBe(0);
      expect(registry.get("inst-1")!.lastRelayDetachedAt).toBe(5000);
    });

    test("计数未归零时不设置 lastRelayDetachedAt", () => {
      registry.register("inst-1", makeSupplement({ relayCount: 2, lastRelayDetachedAt: null }));
      registry.detachRelay("inst-1", 5000);
      expect(registry.get("inst-1")!.relayCount).toBe(1);
      expect(registry.get("inst-1")!.lastRelayDetachedAt).toBeNull();
    });

    test("relayCount 为 0 时 detach 不会变为负数", () => {
      registry.register("inst-1", makeSupplement({ relayCount: 0 }));
      registry.detachRelay("inst-1", 5000);
      expect(registry.get("inst-1")!.relayCount).toBe(0);
      expect(registry.get("inst-1")!.lastRelayDetachedAt).toBe(5000);
    });

    test("不存在的实例不抛错", () => {
      expect(() => registry.detachRelay("nonexistent", 5000)).not.toThrow();
    });

    test("多个 relay 逐个 detach 直到最后一个才设置 detachedAt", () => {
      registry.register("inst-1", makeSupplement({ relayCount: 3, lastRelayDetachedAt: null }));

      registry.detachRelay("inst-1", 1000);
      expect(registry.get("inst-1")!.relayCount).toBe(2);
      expect(registry.get("inst-1")!.lastRelayDetachedAt).toBeNull();

      registry.detachRelay("inst-1", 2000);
      expect(registry.get("inst-1")!.relayCount).toBe(1);
      expect(registry.get("inst-1")!.lastRelayDetachedAt).toBeNull();

      registry.detachRelay("inst-1", 3000);
      expect(registry.get("inst-1")!.relayCount).toBe(0);
      expect(registry.get("inst-1")!.lastRelayDetachedAt).toBe(3000);
    });
  });

  // ── nextInstanceNumber 单调计数器 ──

  describe("nextInstanceNumber 单调计数器", () => {
    test("空环境从 1 开始", () => {
      expect(registry.nextInstanceNumber("env-1")).toBe(1);
    });

    test("连续调用单调递增", () => {
      expect(registry.nextInstanceNumber("env-1")).toBe(1);
      expect(registry.nextInstanceNumber("env-1")).toBe(2);
      expect(registry.nextInstanceNumber("env-1")).toBe(3);
    });

    test("不同环境独立计数", () => {
      expect(registry.nextInstanceNumber("env-1")).toBe(1);
      expect(registry.nextInstanceNumber("env-2")).toBe(1);
      expect(registry.nextInstanceNumber("env-1")).toBe(2);
      expect(registry.nextInstanceNumber("env-2")).toBe(2);
    });

    test("双保险：取 max(counter, 现有实例最大编号) + 1", () => {
      // 手动注册 instanceNumber=10 的实例
      registry.register("inst-10", makeSupplement({ environmentId: "env-1", instanceNumber: 10 }));
      // counter 为 0，maxFromInstances 为 10，结果应为 11
      expect(registry.nextInstanceNumber("env-1")).toBe(11);
    });

    test("counter 大于实例编号时使用 counter", () => {
      registry.register("inst-1", makeSupplement({ environmentId: "env-1", instanceNumber: 1 }));
      // 先调几次让 counter 涨上去
      registry.nextInstanceNumber("env-1"); // max(0,1)+1 = 2, counter→2
      registry.nextInstanceNumber("env-1"); // max(2,1)+1 = 3, counter→3
      registry.nextInstanceNumber("env-1"); // max(3,1)+1 = 4, counter→4
      // 注销唯一实例，counter 仍然是 4
      registry.unregister("inst-1");
      // 无实例，counter=4 → next = 5
      expect(registry.nextInstanceNumber("env-1")).toBe(5);
    });
  });

  // ── deleteCounter ──

  describe("deleteCounter 环境计数器清理", () => {
    test("无残留实例时删除计数器", () => {
      registry.nextInstanceNumber("env-1"); // counter = 1
      registry.deleteCounter("env-1");
      // 删除后再调用 nextInstanceNumber 从 1 开始
      expect(registry.nextInstanceNumber("env-1")).toBe(1);
    });

    test("有残留实例时不删除计数器", () => {
      registry.register("inst-1", makeSupplement({ environmentId: "env-1" }));
      registry.nextInstanceNumber("env-1"); // counter 涨到某值
      registry.deleteCounter("env-1"); // 有实例，不应删除
      // 再调 nextInstanceNumber 应该继续递增而非从 1 开始
      const next = registry.nextInstanceNumber("env-1");
      expect(next).toBeGreaterThan(1);
    });
  });

  // ── reconcile 对账 ──

  describe("reconcile 与 Core 对账", () => {
    test("移除孤儿条目（registry 有但 core 无）", () => {
      registry.register("inst-1", makeSupplement({ environmentId: "env-1" }));
      registry.register("inst-2", makeSupplement({ environmentId: "env-1" }));
      registry.register("inst-3", makeSupplement({ environmentId: "env-2" }));

      // core 只有 inst-1 和 inst-3
      registry.reconcile(() => [{ instanceId: "inst-1" }, { instanceId: "inst-3" }]);

      expect(registry.has("inst-1")).toBe(true);
      expect(registry.has("inst-2")).toBe(false); // 被移除
      expect(registry.has("inst-3")).toBe(true);
    });

    test("core 空数组则移除所有条目", () => {
      registry.register("inst-1", makeSupplement({ environmentId: "env-1" }));
      registry.register("inst-2", makeSupplement({ environmentId: "env-2" }));

      registry.reconcile(() => []);

      expect(registry.size).toBe(0);
    });

    test("registry 空时 reconcile 不抛错", () => {
      expect(() => registry.reconcile(() => [{ instanceId: "inst-1" }])).not.toThrow();
      expect(registry.size).toBe(0);
    });

    test("reconcile 后 byEnvironment 索引也正确清理", () => {
      registry.register("inst-1", makeSupplement({ environmentId: "env-1" }));
      registry.register("inst-2", makeSupplement({ environmentId: "env-1" }));

      registry.reconcile(() => [{ instanceId: "inst-1" }]);

      const env1 = registry.getByEnvironment("env-1");
      expect(env1.length).toBe(1);
      expect(env1[0][0]).toBe("inst-1");
    });

    test("完全匹配时无变化", () => {
      registry.register("inst-1", makeSupplement({ environmentId: "env-1" }));
      registry.register("inst-2", makeSupplement({ environmentId: "env-2" }));

      registry.reconcile(() => [{ instanceId: "inst-1" }, { instanceId: "inst-2" }]);

      expect(registry.size).toBe(2);
      expect(registry.has("inst-1")).toBe(true);
      expect(registry.has("inst-2")).toBe(true);
    });
  });

  // ── clear ──

  describe("clear 清空所有状态", () => {
    test("清空后 size 为 0", () => {
      registry.register("inst-1", makeSupplement({ environmentId: "env-1" }));
      registry.register("inst-2", makeSupplement({ environmentId: "env-2" }));
      registry.clear();
      expect(registry.size).toBe(0);
    });

    test("清空后 has 返回 false", () => {
      registry.register("inst-1", makeSupplement({ environmentId: "env-1" }));
      registry.clear();
      expect(registry.has("inst-1")).toBe(false);
    });

    test("清空后 getByEnvironment 返回空数组", () => {
      registry.register("inst-1", makeSupplement({ environmentId: "env-1" }));
      registry.clear();
      expect(registry.getByEnvironment("env-1")).toEqual([]);
    });

    test("清空后计数器也被重置", () => {
      registry.nextInstanceNumber("env-1"); // counter = 1
      registry.clear();
      expect(registry.nextInstanceNumber("env-1")).toBe(1); // 重新从 1 开始
    });

    test("清空后再注册正常工作", () => {
      registry.register("inst-1", makeSupplement({ environmentId: "env-1" }));
      registry.clear();
      registry.register("inst-2", makeSupplement({ environmentId: "env-2" }));
      expect(registry.size).toBe(1);
      expect(registry.has("inst-2")).toBe(true);
    });
  });

  // ── 综合场景 ──

  describe("综合场景", () => {
    test("完整生命周期：register → attachRelay → touchActivity → detachRelay → unregister", () => {
      const sup = makeSupplement({ relayCount: 0, lastActivityAt: 1000, lastRelayDetachedAt: null });
      registry.register("inst-1", sup);

      // relay 连接
      registry.attachRelay("inst-1", 2000);
      expect(registry.get("inst-1")!.relayCount).toBe(1);
      expect(registry.get("inst-1")!.lastActivityAt).toBe(2000);

      // 业务活跃
      registry.touchActivity("inst-1", 3000);
      expect(registry.get("inst-1")!.lastActivityAt).toBe(3000);

      // relay 断开
      registry.detachRelay("inst-1", 4000);
      expect(registry.get("inst-1")!.relayCount).toBe(0);
      expect(registry.get("inst-1")!.lastRelayDetachedAt).toBe(4000);

      // 注销
      registry.unregister("inst-1");
      expect(registry.has("inst-1")).toBe(false);
      expect(registry.size).toBe(0);
    });

    test("多环境多实例 nextInstanceNumber 各自独立递增", () => {
      registry.register("inst-a1", makeSupplement({ environmentId: "env-a", instanceNumber: 1 }));
      registry.register("inst-b1", makeSupplement({ environmentId: "env-b", instanceNumber: 1 }));

      // 不同环境独立计数，各自从 max(counter, maxInstanceNumber) + 1 开始
      const nextA1 = registry.nextInstanceNumber("env-a");
      const nextB1 = registry.nextInstanceNumber("env-b");
      expect(nextA1).toBe(2);
      expect(nextB1).toBe(2);

      // 各自继续递增互不影响
      const nextA2 = registry.nextInstanceNumber("env-a");
      expect(nextA2).toBe(3);
      const nextB2 = registry.nextInstanceNumber("env-b");
      expect(nextB2).toBe(3);
    });
  });
});
