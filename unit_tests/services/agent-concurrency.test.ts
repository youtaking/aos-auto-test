// agent-concurrency.test.ts — Agent 并发统计与 spawn 预留测试
// 测试目标：isActiveRuntimeStatus / beginSpawnReservation / releaseSpawnReservation /
//          getActiveAgentCount / getActiveScheduledAgentCount / getActiveUserAgentCount
// 业务意图：确保并发额度统计正确涵盖 runtime 实例和 in-flight 预留

import { beforeEach, describe, expect, test } from "bun:test";

// ── 复制纯函数（无外部依赖）──

type InstanceSpawnSource = "interactive" | "scheduled" | "system";

interface SpawnReservation {
  readonly token: number;
  readonly userId: string;
  readonly source: InstanceSpawnSource;
}

let reservationTokenSeq = 0;
const pendingReservations = new Set<SpawnReservation>();

function isActiveRuntimeStatus(status: string): boolean {
  return status !== "stopped" && status !== "stopping" && status !== "error";
}

function getPendingSpawnReservations(): ReadonlySet<SpawnReservation> {
  return pendingReservations;
}

function beginSpawnReservation(
  userId: string,
  source: InstanceSpawnSource,
  limits?: { agentMaxConcurrency?: number; userAgentMaxConcurrency?: number; scheduledAgentMaxConcurrency?: number },
  listInstances?: () => Array<{ instanceId: string; status: string }>,
  registryGet?: (id: string) => { userId?: string; spawnSource?: string } | undefined,
): SpawnReservation {
  // 源码中 beginSpawnReservation 会先调用 assertAgentConcurrencyAvailable
  // 测试版注入 limits 参数替代 config 依赖
  if (limits) {
    assertAgentConcurrencyAvailable(
      userId, source, limits,
      listInstances ?? (() => []),
      registryGet ?? (() => undefined),
    );
  }
  const reservation: SpawnReservation = { token: ++reservationTokenSeq, userId, source };
  pendingReservations.add(reservation);
  return reservation;
}

function releaseSpawnReservation(reservation: SpawnReservation): void {
  pendingReservations.delete(reservation);
}

function getActiveAgentCount(listInstances: () => Array<{ status: string }>): number {
  return listInstances().filter((s) => isActiveRuntimeStatus(s.status)).length + pendingReservations.size;
}

function getActiveScheduledAgentCount(
  listInstances: () => Array<{ instanceId: string; status: string }>,
  registryGet: (id: string) => { spawnSource?: string } | undefined,
): number {
  let count = 0;
  for (const snapshot of listInstances()) {
    if (!isActiveRuntimeStatus(snapshot.status)) continue;
    const supplement = registryGet(snapshot.instanceId);
    if (supplement?.spawnSource === "scheduled") count += 1;
  }
  for (const reservation of pendingReservations) {
    if (reservation.source === "scheduled") count += 1;
  }
  return count;
}

function getActiveUserAgentCount(
  userId: string,
  listInstances: () => Array<{ instanceId: string; status: string }>,
  registryGet: (id: string) => { userId?: string } | undefined,
): number {
  let count = 0;
  for (const snapshot of listInstances()) {
    if (!isActiveRuntimeStatus(snapshot.status)) continue;
    const supplement = registryGet(snapshot.instanceId);
    if (supplement?.userId === userId) count += 1;
  }
  for (const reservation of pendingReservations) {
    if (reservation.userId === userId) count += 1;
  }
  return count;
}

// assertAgentConcurrencyAvailable 纯函数副本（注入 limits 替代 config 依赖）
function assertAgentConcurrencyAvailable(
  userId: string,
  source: InstanceSpawnSource,
  limits: { agentMaxConcurrency?: number; userAgentMaxConcurrency?: number; scheduledAgentMaxConcurrency?: number },
  listInstances: () => Array<{ instanceId: string; status: string }>,
  registryGet: (id: string) => { userId?: string; spawnSource?: string } | undefined,
): void {
  const totalLimit = limits.agentMaxConcurrency;
  if (totalLimit && getActiveAgentCount(listInstances) >= totalLimit) {
    throw new Error("AGENT_CONCURRENCY_LIMIT_REACHED");
  }

  const userLimit = limits.userAgentMaxConcurrency;
  if (userLimit && getActiveUserAgentCount(userId, listInstances, registryGet) >= userLimit) {
    throw new Error("USER_AGENT_CONCURRENCY_LIMIT_REACHED");
  }

  const scheduledLimit = limits.scheduledAgentMaxConcurrency;
  if (source === "scheduled" && scheduledLimit && getActiveScheduledAgentCount(listInstances, registryGet) >= scheduledLimit) {
    throw new Error("SCHEDULED_AGENT_CONCURRENCY_LIMIT_REACHED");
  }
}

// ── tests ──

describe("Agent 并发统计", () => {
  beforeEach(() => {
    pendingReservations.clear();
    reservationTokenSeq = 0;
  });

  // ── isActiveRuntimeStatus ──

  describe("isActiveRuntimeStatus 状态判定", () => {
    test("running 是活跃状态", () => {
      expect(isActiveRuntimeStatus("running")).toBe(true);
    });

    test("starting 是活跃状态", () => {
      expect(isActiveRuntimeStatus("starting")).toBe(true);
    });

    test("idle 是活跃状态", () => {
      expect(isActiveRuntimeStatus("idle")).toBe(true);
    });

    test("paused 是活跃状态", () => {
      expect(isActiveRuntimeStatus("paused")).toBe(true);
    });

    test("stopped 不是活跃状态", () => {
      expect(isActiveRuntimeStatus("stopped")).toBe(false);
    });

    test("stopping 不是活跃状态", () => {
      expect(isActiveRuntimeStatus("stopping")).toBe(false);
    });

    test("error 不是活跃状态", () => {
      expect(isActiveRuntimeStatus("error")).toBe(false);
    });
  });

  // ── beginSpawnReservation / releaseSpawnReservation ──

  describe("SpawnReservation 预留机制", () => {
    test("beginSpawnReservation 创建预留并加入 pending 集合", () => {
      const r = beginSpawnReservation("user-1", "interactive");
      expect(r.userId).toBe("user-1");
      expect(r.source).toBe("interactive");
      expect(r.token).toBe(1);
      expect(getPendingSpawnReservations().size).toBe(1);
    });

    test("token 自增", () => {
      const r1 = beginSpawnReservation("user-1", "interactive");
      const r2 = beginSpawnReservation("user-2", "scheduled");
      expect(r1.token).toBe(1);
      expect(r2.token).toBe(2);
    });

    test("releaseSpawnReservation 移除预留", () => {
      const r = beginSpawnReservation("user-1", "interactive");
      expect(getPendingSpawnReservations().size).toBe(1);
      releaseSpawnReservation(r);
      expect(getPendingSpawnReservations().size).toBe(0);
    });

    test("重复 release 无副作用（幂等）", () => {
      const r = beginSpawnReservation("user-1", "interactive");
      releaseSpawnReservation(r);
      releaseSpawnReservation(r);
      expect(getPendingSpawnReservations().size).toBe(0);
    });

    test("多个预留独立管理", () => {
      const r1 = beginSpawnReservation("user-1", "interactive");
      const r2 = beginSpawnReservation("user-2", "scheduled");
      const r3 = beginSpawnReservation("user-3", "system");
      expect(getPendingSpawnReservations().size).toBe(3);

      releaseSpawnReservation(r2);
      expect(getPendingSpawnReservations().size).toBe(2);
      expect(getPendingSpawnReservations().has(r1)).toBe(true);
      expect(getPendingSpawnReservations().has(r2)).toBe(false);
      expect(getPendingSpawnReservations().has(r3)).toBe(true);
    });
  });

  // ── getActiveAgentCount ──

  describe("getActiveAgentCount 总活跃计数", () => {
    test("只统计活跃实例", () => {
      const count = getActiveAgentCount(() => [
        { status: "running" },
        { status: "stopped" },
        { status: "starting" },
        { status: "error" },
      ]);
      expect(count).toBe(2); // running + starting
    });

    test("包含 pending 预留", () => {
      beginSpawnReservation("user-1", "interactive");
      beginSpawnReservation("user-2", "scheduled");
      const count = getActiveAgentCount(() => [{ status: "running" }]);
      expect(count).toBe(3); // 1 running + 2 pending
    });

    test("无实例无预留时返回 0", () => {
      const count = getActiveAgentCount(() => []);
      expect(count).toBe(0);
    });

    test("全部 stopped 时只算 pending", () => {
      beginSpawnReservation("user-1", "interactive");
      const count = getActiveAgentCount(() => [
        { status: "stopped" },
        { status: "error" },
      ]);
      expect(count).toBe(1);
    });
  });

  // ── getActiveScheduledAgentCount ──

  describe("getActiveScheduledAgentCount 定时任务计数", () => {
    test("只统计 spawnSource=scheduled 的活跃实例", () => {
      const instances = [
        { instanceId: "inst-1", status: "running" },
        { instanceId: "inst-2", status: "running" },
        { instanceId: "inst-3", status: "running" },
      ];
      const registryGet = (id: string) => {
        if (id === "inst-1") return { spawnSource: "scheduled" };
        if (id === "inst-2") return { spawnSource: "interactive" };
        if (id === "inst-3") return { spawnSource: "scheduled" };
        return undefined;
      };
      expect(getActiveScheduledAgentCount(() => instances, registryGet)).toBe(2);
    });

    test("不活跃的实例不计入", () => {
      const instances = [
        { instanceId: "inst-1", status: "stopped" },
        { instanceId: "inst-2", status: "running" },
      ];
      const registryGet = (id: string) => {
        return { spawnSource: "scheduled" };
      };
      expect(getActiveScheduledAgentCount(() => instances, registryGet)).toBe(1);
    });

    test("缺少 supplement 的实例不计入", () => {
      const instances = [{ instanceId: "inst-1", status: "running" }];
      const registryGet = (_id: string) => undefined;
      expect(getActiveScheduledAgentCount(() => instances, registryGet)).toBe(0);
    });

    test("spawnSource 非 scheduled 不计入", () => {
      const instances = [{ instanceId: "inst-1", status: "running" }];
      const registryGet = (_id: string) => ({ spawnSource: "interactive" });
      expect(getActiveScheduledAgentCount(() => instances, registryGet)).toBe(0);
    });

    test("包含 scheduled 来源的 pending 预留", () => {
      beginSpawnReservation("user-1", "scheduled");
      beginSpawnReservation("user-2", "interactive"); // 不应计入
      const instances = [{ instanceId: "inst-1", status: "running" }];
      const registryGet = (_id: string) => ({ spawnSource: "scheduled" });
      // inst-1(scheduled) + 1 pending(scheduled) = 2
      expect(getActiveScheduledAgentCount(() => instances, registryGet)).toBe(2);
    });

    test("无实例只有 pending 预留", () => {
      beginSpawnReservation("user-1", "scheduled");
      expect(getActiveScheduledAgentCount(() => [], () => undefined)).toBe(1);
    });
  });

  // ── getActiveUserAgentCount ──

  describe("getActiveUserAgentCount 用户级计数", () => {
    test("只统计指定用户的活跃实例", () => {
      const instances = [
        { instanceId: "inst-1", status: "running" },
        { instanceId: "inst-2", status: "running" },
        { instanceId: "inst-3", status: "running" },
      ];
      const registryGet = (id: string) => {
        if (id === "inst-1") return { userId: "alice" };
        if (id === "inst-2") return { userId: "bob" };
        if (id === "inst-3") return { userId: "alice" };
        return undefined;
      };
      expect(getActiveUserAgentCount("alice", () => instances, registryGet)).toBe(2);
      expect(getActiveUserAgentCount("bob", () => instances, registryGet)).toBe(1);
    });

    test("不活跃的实例不计入", () => {
      const instances = [
        { instanceId: "inst-1", status: "stopped" },
        { instanceId: "inst-2", status: "running" },
      ];
      const registryGet = (_id: string) => ({ userId: "alice" });
      expect(getActiveUserAgentCount("alice", () => instances, registryGet)).toBe(1);
    });

    test("缺少 supplement 的实例不计入", () => {
      const instances = [{ instanceId: "inst-1", status: "running" }];
      const registryGet = (_id: string) => undefined;
      expect(getActiveUserAgentCount("alice", () => instances, registryGet)).toBe(0);
    });

    test("包含用户的 pending 预留", () => {
      beginSpawnReservation("alice", "interactive");
      beginSpawnReservation("bob", "interactive");
      beginSpawnReservation("alice", "scheduled");
      const instances = [{ instanceId: "inst-1", status: "running" }];
      const registryGet = (_id: string) => ({ userId: "alice" });
      // inst-1(alice) + 2 pending(alice) = 3
      expect(getActiveUserAgentCount("alice", () => instances, registryGet)).toBe(3);
      // 0 instances(bob) + 1 pending(bob) = 1
      expect(getActiveUserAgentCount("bob", () => instances, registryGet)).toBe(1);
    });

    test("指定用户无任何实例和预留时返回 0", () => {
      const instances = [{ instanceId: "inst-1", status: "running" }];
      const registryGet = (_id: string) => ({ userId: "bob" });
      expect(getActiveUserAgentCount("alice", () => instances, registryGet)).toBe(0);
    });

    test("stopping/error 状态排除在外", () => {
      const instances = [
        { instanceId: "inst-1", status: "stopping" },
        { instanceId: "inst-2", status: "error" },
        { instanceId: "inst-3", status: "running" },
      ];
      const registryGet = (_id: string) => ({ userId: "alice" });
      expect(getActiveUserAgentCount("alice", () => instances, registryGet)).toBe(1);
    });
  });

  // ── 综合场景 ──

  describe("综合场景", () => {
    test("预留生命周期与统计一致", () => {
      // spawn 前
      expect(getActiveAgentCount(() => [])).toBe(0);

      // 预留中
      const r = beginSpawnReservation("user-1", "interactive");
      expect(getActiveAgentCount(() => [])).toBe(1);

      // 释放后
      releaseSpawnReservation(r);
      expect(getActiveAgentCount(() => [])).toBe(0);
    });

    test("混合来源统计互不干扰", () => {
      beginSpawnReservation("alice", "interactive");
      beginSpawnReservation("bob", "scheduled");

      const instances = [
        { instanceId: "inst-1", status: "running" },
        { instanceId: "inst-2", status: "running" },
      ];
      const registryGet = (id: string) => {
        if (id === "inst-1") return { userId: "alice", spawnSource: "interactive" };
        if (id === "inst-2") return { userId: "bob", spawnSource: "scheduled" };
        return undefined;
      };

      // 总活跃 = 2 instances + 2 pending = 4
      expect(getActiveAgentCount(() => instances)).toBe(4);
      // scheduled 活跃 = inst-2 + pending(bob/scheduled) = 2
      expect(getActiveScheduledAgentCount(() => instances, registryGet)).toBe(2);
      // alice 活跃 = inst-1 + pending(alice/interactive) = 2
      expect(getActiveUserAgentCount("alice", () => instances, registryGet)).toBe(2);
      // bob 活跃 = inst-2 + pending(bob/scheduled) = 2
      expect(getActiveUserAgentCount("bob", () => instances, registryGet)).toBe(2);
    });
  });

  // ── assertAgentConcurrencyAvailable ──

  describe("assertAgentConcurrencyAvailable 并发检查", () => {
    const noInstances = () => [] as Array<{ instanceId: string; status: string }>;
    const noRegistry = () => undefined;

    test("未达上限时正常通过", () => {
      expect(() =>
        assertAgentConcurrencyAvailable(
          "user-1", "interactive",
          { agentMaxConcurrency: 10, userAgentMaxConcurrency: 5 },
          noInstances, noRegistry,
        ),
      ).not.toThrow();
    });

    test("总并发达上限时抛出 AGENT_CONCURRENCY_LIMIT_REACHED", () => {
      // 3 个活跃实例，总上限 3
      const instances = [
        { instanceId: "a", status: "running" },
        { instanceId: "b", status: "running" },
        { instanceId: "c", status: "running" },
      ];
      expect(() =>
        assertAgentConcurrencyAvailable(
          "user-1", "interactive",
          { agentMaxConcurrency: 3 },
          () => instances, noRegistry,
        ),
      ).toThrow("AGENT_CONCURRENCY_LIMIT_REACHED");
    });

    test("用户级并发达上限时抛出 USER_AGENT_CONCURRENCY_LIMIT_REACHED", () => {
      // alice 已有 2 个活跃实例，用户上限 2
      const instances = [
        { instanceId: "a", status: "running" },
        { instanceId: "b", status: "running" },
      ];
      const registryGet = (id: string) => ({ userId: "alice", spawnSource: "interactive" });
      expect(() =>
        assertAgentConcurrencyAvailable(
          "alice", "interactive",
          { userAgentMaxConcurrency: 2 },
          () => instances, registryGet,
        ),
      ).toThrow("USER_AGENT_CONCURRENCY_LIMIT_REACHED");
    });

    test("定时任务并发达上限时仅 source=scheduled 抛出", () => {
      // 2 个 scheduled 活跃实例，定时上限 2
      const instances = [
        { instanceId: "a", status: "running" },
        { instanceId: "b", status: "running" },
      ];
      const registryGet = () => ({ spawnSource: "scheduled" });

      // scheduled source → 抛错
      expect(() =>
        assertAgentConcurrencyAvailable(
          "user-1", "scheduled",
          { scheduledAgentMaxConcurrency: 2 },
          () => instances, registryGet,
        ),
      ).toThrow("SCHEDULED_AGENT_CONCURRENCY_LIMIT_REACHED");

      // interactive source → 不检查 scheduled 上限，正常通过
      expect(() =>
        assertAgentConcurrencyAvailable(
          "user-1", "interactive",
          { scheduledAgentMaxConcurrency: 2 },
          () => instances, registryGet,
        ),
      ).not.toThrow();
    });
  });

  // ── beginSpawnReservation 集成 assertAgentConcurrencyAvailable ──

  describe("beginSpawnReservation 集成并发检查", () => {
    test("达限时 beginSpawnReservation 抛出且不登记预留", () => {
      const instances = [
        { instanceId: "a", status: "running" },
        { instanceId: "b", status: "running" },
      ];
      expect(() =>
        beginSpawnReservation(
          "user-1", "interactive",
          { agentMaxConcurrency: 2 },
          () => instances,
        ),
      ).toThrow("AGENT_CONCURRENCY_LIMIT_REACHED");
      // 检查失败时不应登记预留
      expect(getPendingSpawnReservations().size).toBe(0);
    });

    test("未达限时 beginSpawnReservation 正常登记", () => {
      const r = beginSpawnReservation(
        "user-1", "interactive",
        { agentMaxConcurrency: 10 },
      );
      expect(r.userId).toBe("user-1");
      expect(getPendingSpawnReservations().size).toBe(1);
    });

    test("不传 limits 时跳过检查（向后兼容）", () => {
      // 即使已有大量实例也不抛错
      const r = beginSpawnReservation("user-1", "interactive");
      expect(r.userId).toBe("user-1");
      expect(getPendingSpawnReservations().size).toBe(1);
    });
  });
});
