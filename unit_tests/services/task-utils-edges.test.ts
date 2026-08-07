import { describe, expect, it } from "bun:test";

// 测试 task.ts 内部工具函数的边界场景

// ── truncateSummary ──

function truncateSummary(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  return value.length > 2000 ? value.slice(0, 2000) : value;
}

describe("truncateSummary", () => {
  it("null/undefined 返回 null", () => {
    expect(truncateSummary(null)).toBeNull();
    expect(truncateSummary(undefined)).toBeNull();
  });

  it("空字符串返回 null", () => {
    expect(truncateSummary("")).toBeNull();
  });

  it("短字符串原样返回", () => {
    expect(truncateSummary("hello")).toBe("hello");
  });

  it("恰好 2000 字符不截断", () => {
    const s = "a".repeat(2000);
    expect(truncateSummary(s)).toBe(s);
    expect(truncateSummary(s)!.length).toBe(2000);
  });

  it("超过 2000 字符截断", () => {
    const s = "a".repeat(2001);
    const result = truncateSummary(s);
    expect(result!.length).toBe(2000);
  });

  it("保留 unicode 字符", () => {
    expect(truncateSummary("你好世界")).toBe("你好世界");
  });
});

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
