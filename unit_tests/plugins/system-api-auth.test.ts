// system-api-auth.test.ts — 系统级 API 认证逻辑测试
// 测试目标：extractSystemToken / getSystemApiKeys 的 token 提取与匹配
// 业务意图：确保系统级 API 只接受配置的系统 key

import { describe, test, expect } from "bun:test";

// ── 复制纯函数（来自 src/plugins/system-api-auth.ts）──

function extractSystemToken(request: Request): string | null {
  const authHeader = request.headers.get("Authorization");
  if (authHeader?.startsWith("Bearer ")) {
    return authHeader.slice("Bearer ".length).trim();
  }
  const url = new URL(request.url);
  return url.searchParams.get("token");
}

function getSystemApiKeys(envValue: string): string[] {
  return envValue.split(",").map((value) => value.trim()).filter(Boolean);
}

function isSystemAuthorized(request: Request, envValue: string): boolean {
  const token = extractSystemToken(request);
  const allowedKeys = getSystemApiKeys(envValue);
  if (!token || allowedKeys.length === 0 || !allowedKeys.includes(token)) {
    return false;
  }
  return true;
}

// ── 测试 ──

describe("extractSystemToken", () => {
  test("正向 - 从 Bearer header 提取 token", () => {
    const req = new Request("http://localhost/api/test", {
      headers: { Authorization: "Bearer my-secret-key" },
    });
    expect(extractSystemToken(req)).toBe("my-secret-key");
  });

  test("正向 - 从 URL query 提取 token", () => {
    const req = new Request("http://localhost/api/test?token=query-key");
    expect(extractSystemToken(req)).toBe("query-key");
  });

  test("分支 - 无 token 返回 null", () => {
    const req = new Request("http://localhost/api/test");
    expect(extractSystemToken(req)).toBeNull();
  });

  test("分支 - 非 Bearer header 返回 null（fallback 到 query）", () => {
    const req = new Request("http://localhost/api/test", {
      headers: { Authorization: "Basic abc" },
    });
    expect(extractSystemToken(req)).toBeNull();
  });

  test("边界 - Bearer 后多余空格被 trim", () => {
    const req = new Request("http://localhost/api/test", {
      headers: { Authorization: "Bearer  spaced-key  " },
    });
    expect(extractSystemToken(req)).toBe("spaced-key");
  });
});

describe("getSystemApiKeys", () => {
  test("正向 - 逗号分隔的多个 key", () => {
    expect(getSystemApiKeys("key1,key2,key3")).toEqual(["key1", "key2", "key3"]);
  });

  test("正向 - 单个 key", () => {
    expect(getSystemApiKeys("only-key")).toEqual(["only-key"]);
  });

  test("正向 - 自动 trim 空白", () => {
    expect(getSystemApiKeys(" key1 , key2 ")).toEqual(["key1", "key2"]);
  });

  test("边界 - 空字符串返回空数组", () => {
    expect(getSystemApiKeys("")).toEqual([]);
  });

  test("边界 - 只有逗号返回空数组", () => {
    expect(getSystemApiKeys(",,")).toEqual([]);
  });
});

describe("isSystemAuthorized", () => {
  test("正向 - 匹配的 Bearer token 返回 true", () => {
    const req = new Request("http://localhost/api", {
      headers: { Authorization: "Bearer sys-key-1" },
    });
    expect(isSystemAuthorized(req, "sys-key-1,sys-key-2")).toBe(true);
  });

  test("正向 - 匹配的 query token 返回 true", () => {
    const req = new Request("http://localhost/api?token=sys-key-1");
    expect(isSystemAuthorized(req, "sys-key-1")).toBe(true);
  });

  test("分支 - 不匹配的 token 返回 false", () => {
    const req = new Request("http://localhost/api", {
      headers: { Authorization: "Bearer wrong-key" },
    });
    expect(isSystemAuthorized(req, "sys-key-1")).toBe(false);
  });

  test("分支 - 无配置 key 返回 false", () => {
    const req = new Request("http://localhost/api", {
      headers: { Authorization: "Bearer any-key" },
    });
    expect(isSystemAuthorized(req, "")).toBe(false);
  });

  test("分支 - 无 token 返回 false", () => {
    const req = new Request("http://localhost/api");
    expect(isSystemAuthorized(req, "sys-key-1")).toBe(false);
  });
});
