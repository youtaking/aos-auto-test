// body-limit.test.ts — 全局请求体上限判定测试
// 测试目标：isRequestBodyOverLimit 对 content-length 的解析口径与 108MiB 传输预算
// 业务意图：缺失/非数值长度不推测，交由宿主流计数兜底；预算必须高于文件单体 92MiB 硬上限
// 源：apps/server/src/plugins/body-limit.ts（main a7f477a9e）

import { describe, expect, test } from "bun:test";

// ── 复制实现 ──

const MAX_REQUEST_BODY_BYTES = 108 * 1024 * 1024;
const FILE_SINGLE_LIMIT_BYTES = 92 * 1024 * 1024;

function isRequestBodyOverLimit(contentLength: string | null): boolean {
  if (!contentLength) return false;
  const parsed = Number.parseInt(contentLength, 10);
  return Number.isFinite(parsed) && parsed > MAX_REQUEST_BODY_BYTES;
}

// ── tests ──

describe("传输预算", () => {
  test("请求体上限为 108MiB 且高于文件单体 92MiB", () => {
    expect(MAX_REQUEST_BODY_BYTES).toBe(113_246_208);
    expect(MAX_REQUEST_BODY_BYTES).toBeGreaterThan(FILE_SINGLE_LIMIT_BYTES);
    expect(MAX_REQUEST_BODY_BYTES - FILE_SINGLE_LIMIT_BYTES).toBe(16 * 1024 * 1024);
  });
});

describe("isRequestBodyOverLimit", () => {
  test("缺失或空串不判定超限", () => {
    expect(isRequestBodyOverLimit(null)).toBe(false);
    expect(isRequestBodyOverLimit("")).toBe(false);
  });

  test("恰好等于上限不超限，多 1 字节超限", () => {
    expect(isRequestBodyOverLimit(String(MAX_REQUEST_BODY_BYTES))).toBe(false);
    expect(isRequestBodyOverLimit(String(MAX_REQUEST_BODY_BYTES + 1))).toBe(true);
  });

  test("0、负数与小数前缀按整数解析", () => {
    expect(isRequestBodyOverLimit("0")).toBe(false);
    expect(isRequestBodyOverLimit("-1")).toBe(false);
    expect(isRequestBodyOverLimit(`${MAX_REQUEST_BODY_BYTES + 10}.9`)).toBe(true);
  });

  test("非数值不推测长度", () => {
    for (const value of ["abc", "NaN", "Infinity", "1e9"]) {
      expect(isRequestBodyOverLimit(value)).toBe(false);
    }
  });

  test("带数字前缀的畸形值按前缀解析", () => {
    expect(isRequestBodyOverLimit("123abc")).toBe(false);
    expect(isRequestBodyOverLimit(`${MAX_REQUEST_BODY_BYTES + 1}abc`)).toBe(true);
    expect(isRequestBodyOverLimit(" 123 ")).toBe(false);
  });
});
