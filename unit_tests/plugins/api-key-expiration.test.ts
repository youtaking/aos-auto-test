// api-key-expiration.test.ts — API Key 创建时的名称归一与过期时间换算
// 测试目标：normalizeApiKeyName / expiresAt → expiresIn（秒）/ better-auth 过期错误映射
// 源码：packages/platform/identity/src/routes/web/api-keys.ts、
//       packages/platform/identity/src/services/caller-api-keys.ts（main 325208eb）
// 业务意图：前端传毫秒时间戳或 ISO 字符串，后端统一转成整数秒交给 better-auth；
//           过期时间必须晚于当前时间，否则 400；better-auth 的过近/过远错误要翻译成可读提示

import { describe, test, expect } from "bun:test";

// ── 复制纯逻辑（route 内联实现 + service 导出函数）──

function normalizeApiKeyName(name: unknown): string {
  return typeof name === "string" ? name.trim() : "";
}

type ExpiresResult = { ok: true; expiresIn: number | null } | { ok: false; message: string };

function resolveExpiresIn(expiresAtInput: unknown, now: number): ExpiresResult {
  let expiresIn: number | null = null;
  if (expiresAtInput !== undefined) {
    const expiresAt = new Date(expiresAtInput as string | number | Date).getTime();
    if (!Number.isFinite(expiresAt) || expiresAt <= now) {
      return { ok: false, message: "expiresAt must be a valid time later than the current time" };
    }
    expiresIn = Math.ceil((expiresAt - now) / 1000);
  }
  return { ok: true, expiresIn };
}

function mapExpiresError(code: string | undefined): string | null {
  if (code === "EXPIRES_IN_IS_TOO_SMALL") {
    return "expiresAt is too soon; choose a later expiration time";
  }
  if (code === "EXPIRES_IN_IS_TOO_LARGE") {
    return "expiresAt is too far in the future; choose an earlier expiration time";
  }
  return null;
}

// ── 测试 ──

describe("API Key 名称归一", () => {
  test("前后空格被去掉", () => {
    expect(normalizeApiKeyName("  rcs-key  ")).toBe("rcs-key");
  });

  test("普通名称原样返回", () => {
    expect(normalizeApiKeyName("部署机器人")).toBe("部署机器人");
  });

  test("纯空白归一为空串（调用方据此报 name required）", () => {
    expect(normalizeApiKeyName(" \t ")).toBe("");
  });

  test("非字符串归一为空串", () => {
    expect(normalizeApiKeyName(undefined)).toBe("");
    expect(normalizeApiKeyName(null)).toBe("");
    expect(normalizeApiKeyName(123)).toBe("");
  });
});

describe("API Key 过期时间换算", () => {
  const NOW = 1_700_000_000_000; // 固定时钟，避免依赖运行时间

  test("未传 expiresAt 时为永久有效（null）", () => {
    expect(resolveExpiresIn(undefined, NOW)).toEqual({ ok: true, expiresIn: null });
  });

  test("毫秒时间戳按向上取整换算成秒", () => {
    expect(resolveExpiresIn(NOW + 30_000, NOW)).toEqual({ ok: true, expiresIn: 30 });
  });

  test("不足一秒的余量向上取整", () => {
    expect(resolveExpiresIn(NOW + 1_500, NOW)).toEqual({ ok: true, expiresIn: 2 });
  });

  test("ISO 字符串同样被接受", () => {
    const iso = new Date(NOW + 86_400_000).toISOString();
    expect(resolveExpiresIn(iso, NOW)).toEqual({ ok: true, expiresIn: 86_400 });
  });

  test("等于当前时间被拒绝", () => {
    expect(resolveExpiresIn(NOW, NOW)).toEqual({
      ok: false,
      message: "expiresAt must be a valid time later than the current time",
    });
  });

  test("过去时间被拒绝", () => {
    expect(resolveExpiresIn(NOW - 1, NOW)).toEqual({
      ok: false,
      message: "expiresAt must be a valid time later than the current time",
    });
  });

  test("时间戳 0（1970）被拒绝", () => {
    expect(resolveExpiresIn(0, NOW)).toEqual({
      ok: false,
      message: "expiresAt must be a valid time later than the current time",
    });
  });

  test("空字符串被拒绝", () => {
    expect(resolveExpiresIn("", NOW)).toEqual({
      ok: false,
      message: "expiresAt must be a valid time later than the current time",
    });
  });

  test("非法日期字符串被拒绝", () => {
    expect(resolveExpiresIn("not-a-date", NOW)).toEqual({
      ok: false,
      message: "expiresAt must be a valid time later than the current time",
    });
  });

  test("null 会被解析成 1970，同样被拒绝", () => {
    expect(resolveExpiresIn(null, NOW)).toEqual({
      ok: false,
      message: "expiresAt must be a valid time later than the current time",
    });
  });
});

describe("better-auth 过期错误映射", () => {
  test("EXPIRES_IN_IS_TOO_SMALL 提示选择更晚的时间", () => {
    expect(mapExpiresError("EXPIRES_IN_IS_TOO_SMALL")).toBe(
      "expiresAt is too soon; choose a later expiration time",
    );
  });

  test("EXPIRES_IN_IS_TOO_LARGE 提示选择更早的时间", () => {
    expect(mapExpiresError("EXPIRES_IN_IS_TOO_LARGE")).toBe(
      "expiresAt is too far in the future; choose an earlier expiration time",
    );
  });

  test("其他错误码不映射（由上层原样抛出）", () => {
    expect(mapExpiresError("INVALID_NAME")).toBeNull();
    expect(mapExpiresError(undefined)).toBeNull();
  });
});
