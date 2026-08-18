// scheduler-utils.test.ts — 调度器工具函数测试
// 测试目标：toInvocationDate 多种输入类型的日期转换
// 业务意图：确保 node-schedule invocation 对象在各种运行时环境下正确转换为 Date

import { describe, expect, test } from "bun:test";

// ── 复制纯函数（无外部依赖）──

function toInvocationDate(invocation: unknown): Date | null {
  if (!invocation) return null;
  if (invocation instanceof Date) return invocation;
  if (typeof invocation === "object" && invocation !== null) {
    if ("toDate" in invocation && typeof (invocation as any).toDate === "function") {
      return (invocation as { toDate: () => Date }).toDate();
    }
    if ("toJSDate" in invocation && typeof (invocation as any).toJSDate === "function") {
      return (invocation as { toJSDate: () => Date }).toJSDate();
    }
  }
  return null;
}

// ── tests ──

describe("toInvocationDate 调度器日期转换", () => {
  // ── null / undefined ──

  describe("空值输入", () => {
    test("null 返回 null", () => {
      expect(toInvocationDate(null)).toBeNull();
    });

    test("undefined 返回 null", () => {
      expect(toInvocationDate(undefined)).toBeNull();
    });
  });

  // ── Date 实例 ──

  describe("Date 实例", () => {
    test("Date 实例原样返回", () => {
      const date = new Date("2024-01-15T10:30:00Z");
      const result = toInvocationDate(date);
      expect(result).toBe(date); // 同一引用
    });

    test("当前时间的 Date 实例正确返回", () => {
      const date = new Date();
      expect(toInvocationDate(date)).toBe(date);
    });
  });

  // ── toDate() 方法 ──

  describe("带 toDate() 方法的对象", () => {
    test("调用 toDate() 返回 Date", () => {
      const expected = new Date("2024-06-01T12:00:00Z");
      const obj = { toDate: () => expected };
      const result = toInvocationDate(obj);
      expect(result).toBe(expected);
    });

    test("toDate() 返回新的 Date 对象", () => {
      const obj = {
        toDate() {
          return new Date("2024-03-20T08:00:00Z");
        },
      };
      const result = toInvocationDate(obj);
      expect(result).toBeInstanceOf(Date);
      expect(result!.toISOString()).toBe("2024-03-20T08:00:00.000Z");
    });
  });

  // ── toJSDate() 方法 ──

  describe("带 toJSDate() 方法的对象", () => {
    test("调用 toJSDate() 返回 Date", () => {
      const expected = new Date("2024-07-04T16:00:00Z");
      const obj = { toJSDate: () => expected };
      const result = toInvocationDate(obj);
      expect(result).toBe(expected);
    });

    test("toJSDate() 返回新的 Date 对象", () => {
      const obj = {
        toJSDate() {
          return new Date("2024-12-25T00:00:00Z");
        },
      };
      const result = toInvocationDate(obj);
      expect(result).toBeInstanceOf(Date);
      expect(result!.toISOString()).toBe("2024-12-25T00:00:00.000Z");
    });
  });

  // ── toDate 优先于 toJSDate ──

  describe("同时有 toDate 和 toJSDate", () => {
    test("toDate 优先被调用", () => {
      const fromDate = new Date("2024-01-01T00:00:00Z");
      const fromJSDate = new Date("2024-12-31T23:59:59Z");
      const obj = {
        toDate: () => fromDate,
        toJSDate: () => fromJSDate,
      };
      const result = toInvocationDate(obj);
      expect(result).toBe(fromDate);
    });
  });

  // ── 非日期对象 ──

  describe("非日期对象返回 null", () => {
    test("普通空对象返回 null", () => {
      expect(toInvocationDate({})).toBeNull();
    });

    test("含无关方法的对象返回 null", () => {
      expect(toInvocationDate({ toString: () => "2024-01-01" })).toBeNull();
    });

    test("toDate 不是函数的对象返回 null", () => {
      expect(toInvocationDate({ toDate: "not-a-function" })).toBeNull();
    });

    test("toJSDate 不是函数的对象返回 null", () => {
      expect(toInvocationDate({ toJSDate: 42 })).toBeNull();
    });

    test("数组返回 null", () => {
      expect(toInvocationDate([2024, 1, 1])).toBeNull();
    });
  });

  // ── 原始值 ──

  describe("原始值返回 null", () => {
    test("数字返回 null", () => {
      expect(toInvocationDate(1704067200000)).toBeNull();
    });

    test("字符串返回 null", () => {
      expect(toInvocationDate("2024-01-01")).toBeNull();
    });

    test("布尔值返回 null", () => {
      expect(toInvocationDate(true)).toBeNull();
    });

    test("0 (falsy) 返回 null", () => {
      expect(toInvocationDate(0)).toBeNull();
    });

    test("空字符串 (falsy) 返回 null", () => {
      expect(toInvocationDate("")).toBeNull();
    });

    test("false 返回 null", () => {
      expect(toInvocationDate(false)).toBeNull();
    });
  });
});
