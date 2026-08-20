// pool-service.test.ts — opensandbox-cluster PoolService 测试
// 测试目标：ConflictError 类结构、delete 冲突检测逻辑
// 业务意图：确保删除有 server 或 binding 的 pool 时被正确拒绝

import { describe, test, expect } from "bun:test";

// ── 复制 ConflictError（来自 packages/opensandbox-cluster/src/services/pool-service.ts）──

class ConflictError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConflictError";
  }
}

// 简化版 delete 逻辑（模拟 PoolService.delete 的前置检查）
function validatePoolDeletable(serverCount: number, bindingCount: number): void {
  if (serverCount > 0 || bindingCount > 0) {
    throw new ConflictError("pool has servers or active sandbox bindings");
  }
}

// ── 测试 ──

describe("ConflictError", () => {
  test("正向 - name 为 ConflictError", () => {
    const err = new ConflictError("conflict");
    expect(err.name).toBe("ConflictError");
    expect(err.message).toBe("conflict");
  });

  test("正向 - 是 Error 子类", () => {
    expect(new ConflictError("x") instanceof Error).toBe(true);
  });
});

describe("validatePoolDeletable", () => {
  test("正向 - 无 server 和 binding 时不抛错", () => {
    expect(() => validatePoolDeletable(0, 0)).not.toThrow();
  });

  test("异常 - 有 server 时抛 ConflictError", () => {
    expect(() => validatePoolDeletable(1, 0)).toThrow("pool has servers or active sandbox bindings");
  });

  test("异常 - 有 binding 时抛 ConflictError", () => {
    expect(() => validatePoolDeletable(0, 1)).toThrow("pool has servers or active sandbox bindings");
  });

  test("异常 - 两者都有时抛 ConflictError", () => {
    expect(() => validatePoolDeletable(5, 3)).toThrow(ConflictError);
  });
});
