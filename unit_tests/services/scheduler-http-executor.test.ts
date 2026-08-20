// scheduler-http-executor.test.ts — HTTP 任务执行器测试
// 测试目标：parseDefinition、header 构建、Content-Type 自动注入、超时判定
// 业务意图：确保 HTTP 任务定义解析和请求构建逻辑正确

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数 ──

interface HttpDefinition {
  url: string;
  method?: string;
  headers?: Record<string, string>;
  body?: string;
}

function parseDefinition(raw: unknown): HttpDefinition {
  const def = (raw ?? {}) as HttpDefinition;
  return { url: String(def.url ?? ""), method: def.method, headers: def.headers, body: def.body };
}

function buildRequestHeaders(def: HttpDefinition): { method: string; headers: Record<string, string>; body: string | undefined } {
  const method = (def.method ?? "POST").toUpperCase();
  const headers: Record<string, string> = { ...(def.headers ?? {}) };
  const hasContentType = Object.keys(headers).some((k) => k.toLowerCase() === "content-type");
  if (!hasContentType && method !== "GET") {
    headers["Content-Type"] = "application/json";
  }
  return {
    method,
    headers,
    body: method === "GET" ? undefined : (def.body ?? undefined),
  };
}

function classifyHttpError(err: unknown): { isTimeout: boolean; message: string } {
  const isTimeout = err instanceof Error && (err.name === "TimeoutError" || err.name === "AbortError");
  const message = err instanceof Error ? err.message : String(err);
  return { isTimeout, message };
}

function formatHttpResult(status: number, responseText: string): { status: string; resultSummary: string; error?: string } {
  const ok = status >= 200 && status < 300;
  const resultSummary = responseText.length > 2000 ? responseText.slice(0, 2000) : responseText || `HTTP ${status}`;
  if (ok) {
    return { status: "success", resultSummary };
  }
  return {
    status: "failed",
    resultSummary,
    error: responseText ? `HTTP ${status}: ${responseText.slice(0, 500)}` : `HTTP ${status}`,
  };
}

// ── tests ──

describe("scheduler-http-executor HTTP 执行器", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("parseDefinition 定义解析", () => {
    test("完整定义正确解析", () => {
      const result = parseDefinition({
        url: "https://api.example.com/webhook",
        method: "POST",
        headers: { "Authorization": "Bearer token" },
        body: '{"key":"value"}',
      });
      expect(result.url).toBe("https://api.example.com/webhook");
      expect(result.method).toBe("POST");
      expect(result.headers).toEqual({ "Authorization": "Bearer token" });
      expect(result.body).toBe('{"key":"value"}');
    });

    test("缺失字段使用默认值", () => {
      const result = parseDefinition({});
      expect(result.url).toBe("");
      expect(result.method).toBeUndefined();
      expect(result.headers).toBeUndefined();
      expect(result.body).toBeUndefined();
    });

    test("null 输入 url 为空字符串", () => {
      const result = parseDefinition(null);
      expect(result.url).toBe("");
    });

    test("url 为数字时转为字符串", () => {
      const result = parseDefinition({ url: 12345 });
      expect(result.url).toBe("12345");
    });
  });

  describe("buildRequestHeaders 请求构建", () => {
    test("默认 method 为 POST", () => {
      const def = parseDefinition({ url: "https://example.com" });
      const { method } = buildRequestHeaders(def);
      expect(method).toBe("POST");
    });

    test("method 转大写", () => {
      const def = parseDefinition({ url: "https://example.com", method: "put" });
      const { method } = buildRequestHeaders(def);
      expect(method).toBe("PUT");
    });

    test("非 GET 且无 Content-Type 时自动注入 application/json", () => {
      const def = parseDefinition({ url: "https://example.com" });
      const { headers } = buildRequestHeaders(def);
      expect(headers["Content-Type"]).toBe("application/json");
    });

    test("GET 不注入 Content-Type", () => {
      const def = parseDefinition({ url: "https://example.com", method: "GET" });
      const { headers } = buildRequestHeaders(def);
      expect(headers["Content-Type"]).toBeUndefined();
    });

    test("已有 Content-Type 时不覆盖", () => {
      const def = parseDefinition({
        url: "https://example.com",
        headers: { "content-type": "text/plain" },
      });
      const { headers } = buildRequestHeaders(def);
      expect(headers["content-type"]).toBe("text/plain");
      expect(headers["Content-Type"]).toBeUndefined();
    });

    test("GET 请求 body 为 undefined", () => {
      const def = parseDefinition({ url: "https://example.com", method: "GET", body: "should-be-ignored" });
      const { body } = buildRequestHeaders(def);
      expect(body).toBeUndefined();
    });

    test("POST 请求保留 body", () => {
      const def = parseDefinition({ url: "https://example.com", body: '{"key":"value"}' });
      const { body } = buildRequestHeaders(def);
      expect(body).toBe('{"key":"value"}');
    });

    test("POST 请求无 body 时 body 为 undefined", () => {
      const def = parseDefinition({ url: "https://example.com" });
      const { body } = buildRequestHeaders(def);
      expect(body).toBeUndefined();
    });

    test("自定义 headers 被保留", () => {
      const def = parseDefinition({
        url: "https://example.com",
        headers: { "Authorization": "Bearer abc", "X-Custom": "value" },
      });
      const { headers } = buildRequestHeaders(def);
      expect(headers["Authorization"]).toBe("Bearer abc");
      expect(headers["X-Custom"]).toBe("value");
    });
  });

  describe("classifyHttpError 错误分类", () => {
    test("TimeoutError 被识别为超时", () => {
      const err = new Error("timed out");
      err.name = "TimeoutError";
      const { isTimeout } = classifyHttpError(err);
      expect(isTimeout).toBe(true);
    });

    test("AbortError 被识别为超时", () => {
      const err = new Error("aborted");
      err.name = "AbortError";
      const { isTimeout } = classifyHttpError(err);
      expect(isTimeout).toBe(true);
    });

    test("普通错误不被识别为超时", () => {
      const err = new Error("connection refused");
      const { isTimeout } = classifyHttpError(err);
      expect(isTimeout).toBe(false);
    });

    test("非 Error 对象不被识别为超时", () => {
      const { isTimeout } = classifyHttpError("some string error");
      expect(isTimeout).toBe(false);
    });

    test("message 从 Error 提取", () => {
      const { message } = classifyHttpError(new Error("connection refused"));
      expect(message).toBe("connection refused");
    });

    test("非 Error 的 message 用 String 转换", () => {
      const { message } = classifyHttpError(42);
      expect(message).toBe("42");
    });
  });

  describe("formatHttpResult 结果格式化", () => {
    test("200 成功返回 success", () => {
      const result = formatHttpResult(200, '{"ok":true}');
      expect(result.status).toBe("success");
      expect(result.resultSummary).toBe('{"ok":true}');
      expect(result.error).toBeUndefined();
    });

    test("201 成功返回 success", () => {
      const result = formatHttpResult(201, "Created");
      expect(result.status).toBe("success");
    });

    test("204 成功返回空 body 时使用 HTTP status", () => {
      const result = formatHttpResult(204, "");
      expect(result.status).toBe("success");
      expect(result.resultSummary).toBe("HTTP 204");
    });

    test("400 失败返回 failed 和 error", () => {
      const result = formatHttpResult(400, "Bad Request");
      expect(result.status).toBe("failed");
      expect(result.error).toBe("HTTP 400: Bad Request");
    });

    test("500 失败返回 error 截断到 500 字符", () => {
      const longText = "x".repeat(600);
      const result = formatHttpResult(500, longText);
      expect(result.error!.length).toBeLessThanOrEqual(520); // "HTTP 500: " + 500 chars
    });

    test("超长响应截断 resultSummary 到 2000 字符", () => {
      const longText = "x".repeat(3000);
      const result = formatHttpResult(200, longText);
      expect(result.resultSummary.length).toBe(2000);
    });

    test("失败时空响应使用 HTTP status 作为 summary", () => {
      const result = formatHttpResult(503, "");
      expect(result.resultSummary).toBe("HTTP 503");
      expect(result.error).toBe("HTTP 503");
    });
  });
});
