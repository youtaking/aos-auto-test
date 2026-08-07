import { describe, expect, it } from "bun:test";

// 复制 parseHeaders 逻辑进行纯单元测试（该函数为 private，无法直接 import）
// 确保 sanitizeTask 的 headers 解析逻辑正确覆盖以下场景：
// - jsonb 自动解析的对象
// - 旧数据中双重编码的 JSON 字符串
// - null / undefined
// - 非法 JSON 字符串
function parseHeaders(value: unknown): Record<string, string> | null {
  if (!value) return null;
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      if (typeof parsed === "string") {
        try {
          return JSON.parse(parsed);
        } catch {
          return null;
        }
      }
      return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)
        ? (parsed as Record<string, string>)
        : null;
    } catch {
      return null;
    }
  }
  if (typeof value === "object" && !Array.isArray(value)) return value as Record<string, string>;
  return null;
}

describe("parseHeaders", () => {
  it("返回已解析的对象", () => {
    const result = parseHeaders({ "Content-Type": "application/json", "X-Custom": "value" });
    expect(result).toEqual({ "Content-Type": "application/json", "X-Custom": "value" });
  });

  it("解析双重编码的 JSON 字符串", () => {
    const doubleEncoded = JSON.stringify(JSON.stringify({ Authorization: "Bearer abc" }));
    const result = parseHeaders(doubleEncoded);
    expect(result).toEqual({ Authorization: "Bearer abc" });
  });

  it("解析单层 JSON 字符串", () => {
    const result = parseHeaders('{"Content-Type":"text/html"}');
    expect(result).toEqual({ "Content-Type": "text/html" });
  });

  it("null 返回 null", () => {
    expect(parseHeaders(null)).toBeNull();
  });

  it("undefined 返回 null", () => {
    expect(parseHeaders(undefined)).toBeNull();
  });

  it("空字符串返回 null", () => {
    expect(parseHeaders("")).toBeNull();
  });

  it("非法 JSON 返回 null", () => {
    expect(parseHeaders("not-json")).toBeNull();
  });

  it("数组返回 null", () => {
    expect(parseHeaders([1, 2, 3])).toBeNull();
  });

  it("空对象返回空对象", () => {
    expect(parseHeaders({})).toEqual({});
  });
});
