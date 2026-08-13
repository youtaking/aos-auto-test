import { describe, expect, test } from "bun:test";
import {
  getAutomationStateSnapshot,
  getAutomationStateEventPayload,
  automationStatesEqual,
} from "@fenix/services/automationState";
import type { AutomationStateResponse } from "@fenix/types/api";

describe("getAutomationStateSnapshot", () => {
  test("metadata 无 automation_state 时返回 undefined", () => {
    expect(getAutomationStateSnapshot({})).toBeUndefined();
    expect(getAutomationStateSnapshot({ other: true })).toBeUndefined();
    expect(getAutomationStateSnapshot(null)).toBeUndefined();
    expect(getAutomationStateSnapshot(undefined)).toBeUndefined();
  });

  test("automation_state 为 null 时返回 disabled", () => {
    const result = getAutomationStateSnapshot({ automation_state: null });
    expect(result).toEqual({
      enabled: false,
      phase: null,
      next_tick_at: null,
      sleep_until: null,
    });
  });

  test("非 object 的 automation_state 返回 disabled", () => {
    for (const val of ["string", 123, true, []]) {
      const result = getAutomationStateSnapshot({ automation_state: val });
      expect(result?.enabled).toBe(false);
    }
  });

  test("enabled 为 true 时正确归一化", () => {
    const result = getAutomationStateSnapshot({ automation_state: { enabled: true } });
    expect(result?.enabled).toBe(true);
  });

  test("enabled 非 true 值归一化为 false", () => {
    const result = getAutomationStateSnapshot({ automation_state: { enabled: "yes" } });
    expect(result?.enabled).toBe(false);
  });

  test("接受 phase: standby", () => {
    const result = getAutomationStateSnapshot({
      automation_state: { enabled: true, phase: "standby" },
    });
    expect(result?.phase).toBe("standby");
  });

  test("接受 phase: sleeping", () => {
    const result = getAutomationStateSnapshot({
      automation_state: { enabled: true, phase: "sleeping" },
    });
    expect(result?.phase).toBe("sleeping");
  });

  test("拒绝非法 phase 值", () => {
    for (const phase of ["running", "idle", "active", "", null]) {
      const result = getAutomationStateSnapshot({
        automation_state: { enabled: true, phase },
      });
      expect(result?.phase).toBeNull();
    }
  });

  test("归一化 next_tick_at 为 number", () => {
    const result = getAutomationStateSnapshot({
      automation_state: { enabled: true, next_tick_at: 12345 },
    });
    expect(result?.next_tick_at).toBe(12345);
  });

  test("归一化非 number 的 next_tick_at 为 null", () => {
    const result = getAutomationStateSnapshot({
      automation_state: { enabled: true, next_tick_at: "soon" },
    });
    expect(result?.next_tick_at).toBeNull();
  });

  test("归一化 sleep_until 为 number", () => {
    const result = getAutomationStateSnapshot({
      automation_state: { enabled: true, sleep_until: 99999 },
    });
    expect(result?.sleep_until).toBe(99999);
  });

  test("完整有效状态归一化", () => {
    const result = getAutomationStateSnapshot({
      automation_state: {
        enabled: true,
        phase: "sleeping",
        next_tick_at: 100,
        sleep_until: 200,
      },
    });
    expect(result).toEqual({
      enabled: true,
      phase: "sleeping",
      next_tick_at: 100,
      sleep_until: 200,
    });
  });
});

describe("getAutomationStateEventPayload", () => {
  test("无 metadata 时返回 disabled 默认值", () => {
    const result = getAutomationStateEventPayload({});
    expect(result).toEqual({
      enabled: false,
      phase: null,
      next_tick_at: null,
      sleep_until: null,
    });
  });

  test("null metadata 返回 disabled 默认值", () => {
    const result = getAutomationStateEventPayload(null);
    expect(result).toEqual({
      enabled: false,
      phase: null,
      next_tick_at: null,
      sleep_until: null,
    });
  });

  test("有 automation_state 时返回归一化值", () => {
    const result = getAutomationStateEventPayload({
      automation_state: {
        enabled: true,
        phase: "standby",
        next_tick_at: 50,
        sleep_until: 60,
      },
    });
    expect(result).toEqual({
      enabled: true,
      phase: "standby",
      next_tick_at: 50,
      sleep_until: 60,
    });
  });

  test("每次调用返回新对象（不是冻结引用）", () => {
    const a = getAutomationStateEventPayload({});
    const b = getAutomationStateEventPayload({});
    expect(a).toEqual(b);
    expect(a).not.toBe(b);
  });
});

describe("automationStatesEqual", () => {
  const base: AutomationStateResponse = {
    enabled: true,
    phase: "standby",
    next_tick_at: 100,
    sleep_until: 200,
  };

  test("相同状态返回 true", () => {
    expect(automationStatesEqual(base, { ...base })).toBe(true);
  });

  test("enabled 不同返回 false", () => {
    expect(automationStatesEqual(base, { ...base, enabled: false })).toBe(false);
  });

  test("phase 不同返回 false", () => {
    expect(automationStatesEqual(base, { ...base, phase: "sleeping" })).toBe(false);
    expect(automationStatesEqual(base, { ...base, phase: null })).toBe(false);
  });

  test("next_tick_at 不同返回 false", () => {
    expect(automationStatesEqual(base, { ...base, next_tick_at: 999 })).toBe(false);
    expect(automationStatesEqual(base, { ...base, next_tick_at: null })).toBe(false);
  });

  test("sleep_until 不同返回 false", () => {
    expect(automationStatesEqual(base, { ...base, sleep_until: 999 })).toBe(false);
    expect(automationStatesEqual(base, { ...base, sleep_until: null })).toBe(false);
  });

  test("两个 disabled 默认值相等", () => {
    const disabled: AutomationStateResponse = {
      enabled: false,
      phase: null,
      next_tick_at: null,
      sleep_until: null,
    };
    expect(automationStatesEqual(disabled, { ...disabled })).toBe(true);
  });
});
