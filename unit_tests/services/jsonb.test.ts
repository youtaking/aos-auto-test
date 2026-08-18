import { describe, expect, test } from "bun:test";
import { parseJsonb, parseJsonbOr } from "@fenix/services/config/jsonb";

describe("parseJsonb", () => {
  test("null 输入返回 null", () => {
    expect(parseJsonb(null)).toBeNull();
  });

  test("undefined 输入返回 null", () => {
    expect(parseJsonb(undefined)).toBeNull();
  });

  test("正常对象直接返回", () => {
    const obj = { key: "value" };
    expect(parseJsonb(obj)).toEqual(obj);
  });

  test("正常数组直接返回", () => {
    const arr = [1, 2, 3];
    expect(parseJsonb(arr)).toEqual(arr);
  });

  test("JSON 字符串被解析为对象", () => {
    expect(parseJsonb('{"key":"value"}')).toEqual({ key: "value" });
  });

  test("双重编码字符串被正确解析", () => {
    const doubleEncoded = JSON.stringify(JSON.stringify({ key: "value" }));
    expect(parseJsonb(doubleEncoded)).toEqual({ key: "value" });
  });

  test("无效 JSON 字符串返回 null", () => {
    expect(parseJsonb("not-json")).toBeNull();
  });

  test("解析后仍为纯字符串（非 JSON）返回 null", () => {
    expect(parseJsonb('"not-json-after-parse"')).toBeNull();
  });

  test("数字类型直接返回", () => {
    expect(parseJsonb(42)).toBe(42);
  });

  test("布尔类型直接返回", () => {
    expect(parseJsonb(true)).toBe(true);
  });

  // ── P1: falsy 值边界测试 ──

  test("falsy 数字 0 直接返回（非 null）", () => {
    expect(parseJsonb(0)).toBe(0);
  });

  test("falsy 布尔 false 直接返回（非 null）", () => {
    expect(parseJsonb(false)).toBe(false);
  });

  test("空字符串触发 JSON.parse 抛错 → 返回 null", () => {
    expect(parseJsonb("")).toBeNull();
  });
});

describe("parseJsonbOr", () => {
  test("解析成功返回解析结果", () => {
    expect(parseJsonbOr('{"a":1}', {})).toEqual({ a: 1 });
  });

  test("解析失败返回 fallback", () => {
    const fallback = { default: true };
    expect(parseJsonbOr("invalid", fallback)).toBe(fallback);
  });

  test("null 输入返回 fallback", () => {
    expect(parseJsonbOr(null, "default")).toBe("default");
  });

  test("对象输入直接返回（不走 JSON 解析）", () => {
    const obj = { existing: true };
    expect(parseJsonbOr(obj, "fallback")).toEqual(obj);
  });
});
