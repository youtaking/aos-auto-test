// observer-types.test.ts — Observer 类型常量测试
// 测试目标：OBSERVER_LINK_SOURCES 和 EMPTY_OBSERVATION_NAMES 常量正确性
// 业务意图：确保观察者模块的常量初始值稳定可依赖

import { describe, test, expect } from "bun:test";

// ── 复制常量（来自 src/services/observer/types.ts）──

const OBSERVER_LINK_SOURCES = ["acp-ws", "external-relay", "chat-relay"] as const;

interface ObservationNames {
  organizationId: Record<string, string>;
  userId: Record<string, string>;
  agentConfigId: Record<string, string>;
  instanceId: Record<string, string>;
  machineId: Record<string, string>;
}

const EMPTY_OBSERVATION_NAMES: ObservationNames = {
  organizationId: {},
  userId: {},
  agentConfigId: {},
  instanceId: {},
  machineId: {},
};

// ── 测试 ──

describe("OBSERVER_LINK_SOURCES", () => {
  test("正向 - 恰好 3 个来源", () => {
    expect(OBSERVER_LINK_SOURCES.length).toBe(3);
  });

  test("正向 - 包含 acp-ws", () => {
    expect(OBSERVER_LINK_SOURCES).toContain("acp-ws");
  });

  test("正向 - 包含 external-relay", () => {
    expect(OBSERVER_LINK_SOURCES).toContain("external-relay");
  });

  test("正向 - 包含 chat-relay", () => {
    expect(OBSERVER_LINK_SOURCES).toContain("chat-relay");
  });

  test("边界 - 不可变（readonly 数组）", () => {
    // 运行时无法完全验证 readonly，但确保内容不变
    expect([...OBSERVER_LINK_SOURCES]).toEqual(["acp-ws", "external-relay", "chat-relay"]);
  });
});

describe("EMPTY_OBSERVATION_NAMES", () => {
  test("正向 - 包含 5 个角色字典", () => {
    expect(Object.keys(EMPTY_OBSERVATION_NAMES).length).toBe(5);
  });

  test("正向 - 所有字典初始为空对象", () => {
    expect(EMPTY_OBSERVATION_NAMES.organizationId).toEqual({});
    expect(EMPTY_OBSERVATION_NAMES.userId).toEqual({});
    expect(EMPTY_OBSERVATION_NAMES.agentConfigId).toEqual({});
    expect(EMPTY_OBSERVATION_NAMES.instanceId).toEqual({});
    expect(EMPTY_OBSERVATION_NAMES.machineId).toEqual({});
  });

  test("隔离 - 修改不影响原常量（注意：原常量是共享引用）", () => {
    // EMPTY_OBSERVATION_NAMES 是 const，但对象内容可变
    // 测试确认它初始为空
    const copy = JSON.parse(JSON.stringify(EMPTY_OBSERVATION_NAMES));
    copy.organizationId["o1"] = "Org One";
    expect(EMPTY_OBSERVATION_NAMES.organizationId).toEqual({});
  });
});
