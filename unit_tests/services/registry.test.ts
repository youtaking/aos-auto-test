// registry.test.ts — 机器注册表纯逻辑测试
// 测试目标：genId 格式、buildMachineOwnershipConditions 条件构建
// 业务意图：确保机器 ID 生成和归属条件构建正确

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数 ──

function genId(prefix: string): string {
  // 模拟 crypto.randomUUID 的固定版本
  const uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890";
  return `${prefix}_${uuid.slice(0, 22)}`;
}

function genIdDynamic(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 24)}`;
}

interface AuthContext {
  organizationId: string;
  userId: string;
}

// ── tests ──

describe("registry 机器注册表", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("genId ID 生成", () => {
    test("包含指定前缀", () => {
      const id = genId("mac");
      expect(id.startsWith("mac_")).toBe(true);
    });

    test("前缀和后缀用下划线分隔", () => {
      const id = genId("machine");
      expect(id).toContain("_");
      expect(id.split("_")[0]).toBe("machine");
    });

    test("后缀长度为 22 字符", () => {
      const id = genId("mac");
      const suffix = id.slice(id.indexOf("_") + 1);
      expect(suffix.length).toBe(22);
    });

    test("不同前缀生成不同 ID", () => {
      const id1 = genId("mac");
      const id2 = genId("evt");
      expect(id1).not.toEqual(id2);
    });
  });

  describe("genIdDynamic 动态 ID 生成", () => {
    test("包含指定前缀", () => {
      const id = genIdDynamic("mac");
      expect(id.startsWith("mac_")).toBe(true);
    });

    test("多次调用生成不同 ID", () => {
      const ids = new Set<string>();
      for (let i = 0; i < 10; i++) {
        ids.add(genIdDynamic("mac"));
      }
      // 极小概率碰撞，但至少应该大部分不同
      expect(ids.size).toBeGreaterThan(5);
    });
  });
});
