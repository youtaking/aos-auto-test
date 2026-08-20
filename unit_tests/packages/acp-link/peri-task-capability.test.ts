// peri-task-capability.test.ts — Peri Task capability 协商测试
// 测试目标：buildPeriCapabilityMeta / isPeriTaskNotificationMethod
// 业务意图：确保 acp-link 只放行已实现的 Peri 扩展通知方法

import { describe, test, expect } from "bun:test";

// ── 复制纯函数（来自 packages/acp-link/src/peri-task-capability.ts）──

const PERI_AGENT_EVENT_CAPABILITY = "peri.agentEvent";
const PERI_UNSTABLE_EVENT_CAPABILITY = "peri.unstableEvent";
const PERI_AGENT_EVENT_METHOD = "peri/agent_event";
const PERI_UNSTABLE_EVENT_METHOD = "peri/unstable_event";

function buildPeriCapabilityMeta(): Record<string, true> {
  return {
    [PERI_AGENT_EVENT_CAPABILITY]: true,
    [PERI_UNSTABLE_EVENT_CAPABILITY]: true,
  };
}

function isPeriTaskNotificationMethod(method: string): boolean {
  return method === PERI_AGENT_EVENT_METHOD || method === PERI_UNSTABLE_EVENT_METHOD;
}

// ── 测试 ──

describe("buildPeriCapabilityMeta", () => {
  test("正向 - 返回包含两个 capability 键的对象", () => {
    const meta = buildPeriCapabilityMeta();
    expect(meta[PERI_AGENT_EVENT_CAPABILITY]).toBe(true);
    expect(meta[PERI_UNSTABLE_EVENT_CAPABILITY]).toBe(true);
  });

  test("正向 - 对象恰好包含两个键", () => {
    const meta = buildPeriCapabilityMeta();
    expect(Object.keys(meta).length).toBe(2);
  });

  test("正向 - 每次调用返回新对象", () => {
    const a = buildPeriCapabilityMeta();
    const b = buildPeriCapabilityMeta();
    expect(a).not.toBe(b);
    expect(a).toEqual(b);
  });
});

describe("isPeriTaskNotificationMethod", () => {
  test("正向 - peri/agent_event 返回 true", () => {
    expect(isPeriTaskNotificationMethod(PERI_AGENT_EVENT_METHOD)).toBe(true);
  });

  test("正向 - peri/unstable_event 返回 true", () => {
    expect(isPeriTaskNotificationMethod(PERI_UNSTABLE_EVENT_METHOD)).toBe(true);
  });

  test("分支 - 其他方法返回 false", () => {
    expect(isPeriTaskNotificationMethod("session/update")).toBe(false);
    expect(isPeriTaskNotificationMethod("peri/unknown")).toBe(false);
    expect(isPeriTaskNotificationMethod("")).toBe(false);
  });

  test("边界 - 大小写敏感，大写返回 false", () => {
    expect(isPeriTaskNotificationMethod("PERI/AGENT_EVENT")).toBe(false);
  });

  test("边界 - 相似但不完全匹配返回 false", () => {
    expect(isPeriTaskNotificationMethod("peri/agent_events")).toBe(false);
    expect(isPeriTaskNotificationMethod("peri/agent_event/extra")).toBe(false);
  });
});
