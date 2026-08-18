import { describe, expect, it } from "bun:test";

// 测试 task-v2.ts 内部工具函数的边界场景

// ── toUnixTimestamp ──

function toUnixTimestamp(value: Date | null | undefined): number | null {
  return value ? Math.floor(value.getTime() / 1000) : null;
}

describe("toUnixTimestamp", () => {
  it("null/undefined 返回 null", () => {
    expect(toUnixTimestamp(null)).toBeNull();
    expect(toUnixTimestamp(undefined)).toBeNull();
  });

  it("正常日期转换为 Unix 时间戳", () => {
    const date = new Date("2026-05-17T12:00:00.000Z");
    expect(toUnixTimestamp(date)).toBe(Math.floor(date.getTime() / 1000));
  });

  it("毫秒部分被截断（Math.floor）", () => {
    const date = new Date("2026-05-17T12:00:00.999Z");
    const ts = toUnixTimestamp(date)!;
    expect(ts).toBe(Math.floor(date.getTime() / 1000));
    expect(ts * 1000).toBeLessThan(date.getTime());
  });

  it("epoch 零点返回 0", () => {
    expect(toUnixTimestamp(new Date("1970-01-01T00:00:00.000Z"))).toBe(0);
  });
});
