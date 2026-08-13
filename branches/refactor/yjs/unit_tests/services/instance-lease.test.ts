// instance-lease.test.ts — 实例租约（引用计数）测试
// 测试目标：acquire/release/hasActive/clear
// 业务意图：确保并发 workflow run 共享实例时租约正确计数，最后使用者释放后归零

import { beforeEach, describe, expect, test } from "bun:test";

// ── 复制租约逻辑（纯进程内状态，无外部依赖）──

const leases = new Map<string, number>();

function acquireInstanceLease(instanceId: string): void {
  leases.set(instanceId, (leases.get(instanceId) ?? 0) + 1);
}

function releaseInstanceLease(instanceId: string): void {
  const count = leases.get(instanceId);
  if (count === undefined) return;
  if (count <= 1) {
    leases.delete(instanceId);
  } else {
    leases.set(instanceId, count - 1);
  }
}

function hasActiveInstanceLease(instanceId: string): boolean {
  return (leases.get(instanceId) ?? 0) > 0;
}

function clearInstanceLeases(): void {
  leases.clear();
}

// ── tests ──

describe("InstanceLease 实例租约", () => {
  beforeEach(() => { clearInstanceLeases(); });

  // acquire 后实例有活跃租约
  test("acquire 后 hasActive 返回 true", () => {
    acquireInstanceLease("inst-1");
    expect(hasActiveInstanceLease("inst-1")).toBe(true);
  });

  // 未 acquire 的实例无活跃租约
  test("未 acquire 的实例 hasActive 返回 false", () => {
    expect(hasActiveInstanceLease("inst-unknown")).toBe(false);
  });

  // 多次 acquire 增加引用计数
  test("多次 acquire 增加引用计数", () => {
    acquireInstanceLease("inst-1");
    acquireInstanceLease("inst-1");
    acquireInstanceLease("inst-1");
    expect(leases.get("inst-1")).toBe(3);
  });

  // 配对 release 减少计数
  test("release 减少引用计数", () => {
    acquireInstanceLease("inst-1");
    acquireInstanceLease("inst-1");
    releaseInstanceLease("inst-1");
    expect(leases.get("inst-1")).toBe(1);
    expect(hasActiveInstanceLease("inst-1")).toBe(true);
  });

  // 计数归零时删除条目
  test("计数归零时删除条目，hasActive 返回 false", () => {
    acquireInstanceLease("inst-1");
    releaseInstanceLease("inst-1");
    expect(hasActiveInstanceLease("inst-1")).toBe(false);
    expect(leases.has("inst-1")).toBe(false);
  });

  // 未知实例 release 幂等忽略
  test("未知实例 release 幂等不抛异常", () => {
    expect(() => releaseInstanceLease("inst-unknown")).not.toThrow();
  });

  // 不同实例独立计数
  test("不同实例租约独立", () => {
    acquireInstanceLease("inst-1");
    acquireInstanceLease("inst-2");
    acquireInstanceLease("inst-2");
    releaseInstanceLease("inst-2");
    expect(hasActiveInstanceLease("inst-1")).toBe(true);
    expect(hasActiveInstanceLease("inst-2")).toBe(true); // 还剩 1
    releaseInstanceLease("inst-2");
    expect(hasActiveInstanceLease("inst-2")).toBe(false);
    expect(hasActiveInstanceLease("inst-1")).toBe(true); // inst-1 不受影响
  });

  // clearInstanceLeases 清理所有
  test("clearInstanceLeases 清理全部租约", () => {
    acquireInstanceLease("inst-1");
    acquireInstanceLease("inst-2");
    clearInstanceLeases();
    expect(hasActiveInstanceLease("inst-1")).toBe(false);
    expect(hasActiveInstanceLease("inst-2")).toBe(false);
  });

  // 并发场景模拟：A 先 acquire/release，B 后 acquire/release
  test("并发场景：短 run A 释放后长 run B 仍有租约", () => {
    // A 和 B 共用 inst-1
    acquireInstanceLease("inst-1"); // A acquire
    acquireInstanceLease("inst-1"); // B acquire
    releaseInstanceLease("inst-1"); // A 先结束释放
    // B 仍在使用，cleanup 不应停止 inst-1
    expect(hasActiveInstanceLease("inst-1")).toBe(true);
    releaseInstanceLease("inst-1"); // B 结束
    expect(hasActiveInstanceLease("inst-1")).toBe(false);
  });
});
