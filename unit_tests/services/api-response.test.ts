// api-response.test.ts — 对外 HTTP 错误契约分流测试
// 测试目标：classifyApiResponse 的路径分类与 formatApiError 的 v1/openai/other 三套错误形状
// 业务意图：v1 统一信封、chat/completions 用 OpenAI 原生错误、其余协议保持旧形状，三者不能互相污染
// 源：apps/server/src/protocol/api-response.ts（main a7f477a9e）

import { describe, expect, test } from "bun:test";

// ── 复制实现 ──

function classifyApiResponse(pathname: string): "v1" | "openai" | "other" {
  if (pathname === "/api/v1/chat/completions") return "openai";
  return pathname === "/api/v1" || pathname.startsWith("/api/v1/") ? "v1" : "other";
}

function formatApiError(url: string, code: string, message: string, status: number) {
  switch (classifyApiResponse(new URL(url, "http://localhost").pathname)) {
    case "v1":
      return { success: false as const, error: { code: code === "unauthorized" ? "UNAUTHORIZED" : code, message } };
    case "openai":
      return {
        error: {
          message,
          type:
            status === 401
              ? "authentication_error"
              : status === 429
                ? "rate_limit_error"
                : status >= 500
                  ? "server_error"
                  : "invalid_request_error",
          param: null,
          code,
        },
      };
    default:
      return { error: { type: code, message } };
  }
}

// ── tests ──

describe("classifyApiResponse 路径分类", () => {
  test("chat/completions 优先归为 openai", () => {
    expect(classifyApiResponse("/api/v1/chat/completions")).toBe("openai");
    expect(classifyApiResponse("/api/v1/chat/completions?x=1")).toBe("v1");
    expect(classifyApiResponse("/api/v1/chat/completions/")).toBe("v1");
  });

  test("v1 根与子路径归为 v1", () => {
    expect(classifyApiResponse("/api/v1")).toBe("v1");
    expect(classifyApiResponse("/api/v1/")).toBe("v1");
    expect(classifyApiResponse("/api/v1/agents")).toBe("v1");
    expect(classifyApiResponse("/api/v1/agents/1/mcp")).toBe("v1");
  });

  test("前缀相似与其它协议归为 other", () => {
    for (const path of ["/api/v10", "/api/v1x", "/api/agents", "/web/config/agents", "/health", "/"]) {
      expect(classifyApiResponse(path)).toBe("other");
    }
  });
});

describe("formatApiError v1 信封", () => {
  test("返回 success:false + error{code,message}", () => {
    expect(formatApiError("http://localhost/api/v1/agents", "NOT_FOUND", "Agent not found", 404)).toEqual({
      success: false,
      error: { code: "NOT_FOUND", message: "Agent not found" },
    });
  });

  test("unauthorized 小写码归一为 UNAUTHORIZED", () => {
    expect(formatApiError("/api/v1/agents", "unauthorized", "no key", 401)).toEqual({
      success: false,
      error: { code: "UNAUTHORIZED", message: "no key" },
    });
  });

  test("其它码保持原样", () => {
    expect(formatApiError("/api/v1", "VALIDATION_ERROR", "bad", 400)).toMatchObject({
      error: { code: "VALIDATION_ERROR" },
    });
  });
});

describe("formatApiError OpenAI 形状", () => {
  const body = (url: string, status: number) => formatApiError(url, "some_code", "boom", status);

  test("401 / 429 / 5xx / 4xx 分别映射 type", () => {
    const url = "/api/v1/chat/completions";
    expect(body(url, 401).error.type).toBe("authentication_error");
    expect(body(url, 429).error.type).toBe("rate_limit_error");
    expect(body(url, 500).error.type).toBe("server_error");
    expect(body(url, 503).error.type).toBe("server_error");
    expect(body(url, 400).error.type).toBe("invalid_request_error");
    expect(body(url, 404).error.type).toBe("invalid_request_error");
  });

  test("结构与 param/code 字段固定", () => {
    expect(body("/api/v1/chat/completions", 400)).toEqual({
      error: { message: "boom", type: "invalid_request_error", param: null, code: "some_code" },
    });
  });

  test("改写 unauthorized 的规则不适用于 OpenAI 形状", () => {
    expect(
      formatApiError("/api/v1/chat/completions", "unauthorized", "no key", 401),
    ).toMatchObject({ error: { code: "unauthorized", type: "authentication_error" } });
  });
});

describe("formatApiError 其它协议", () => {
  test("旧形状保留 error{type,message}", () => {
    expect(formatApiError("http://localhost/web/config/agents?name=a", "NOT_FOUND", "missing", 404)).toEqual({
      error: { type: "NOT_FOUND", message: "missing" },
    });
  });

  test("相对 URL 与带查询串的 URL 都能分类", () => {
    expect(formatApiError("/api/v1/agents?x=1", "E", "m", 400)).toHaveProperty("success", false);
    expect(formatApiError("http://node:8080/api/v1/mcp", "E", "m", 400)).toHaveProperty("success", false);
  });
});
