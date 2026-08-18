import { describe, expect, test } from "bun:test";
import { ClusterHttpClient } from "@fenix/sandbox-provider/http-client";
import { SandboxProviderError } from "@fenix/sandbox-provider/provider";

describe("ClusterHttpClient", () => {
  // Cluster 管理请求必须使用 Bearer 鉴权并正确解析 JSON 响应。
  test("sends bearer authentication and decodes JSON", async () => {
    const client = new ClusterHttpClient(async (url, init) => {
      expect(String(url)).toBe("http://cluster.test/api/v1/pools/pool-1/sandboxes/sbi-1/allocate");
      expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer cluster-key");
      return Response.json({ server_id: "server-1" });
    });

    await expect(
      client.json("http://cluster.test", "cluster-key", "/api/v1/pools/pool-1/sandboxes/sbi-1/allocate", 1000),
    ).resolves.toEqual({ server_id: "server-1" });
  });

  // 远程 404 必须保留状态码，Provider 才能单独处理资源不存在。
  test("preserves HTTP status and retryability", async () => {
    const client = new ClusterHttpClient(async () => new Response("missing", { status: 404 }));

    await expect(client.json("http://cluster.test", "cluster-key", "/missing", 1000)).rejects.toMatchObject({
      code: "NOT_FOUND",
      retryable: false,
      status: 404,
    } satisfies Partial<SandboxProviderError>);
  });

  // 5xx 错误应标记为可重试，而不是转换成资源不存在。
  test("marks server errors as retryable", async () => {
    const client = new ClusterHttpClient(async () => new Response("down", { status: 503 }));

    await expect(client.json("http://cluster.test", "cluster-key", "/health", 1000)).rejects.toMatchObject({
      code: "UNAVAILABLE",
      retryable: true,
      status: 503,
    } satisfies Partial<SandboxProviderError>);
  });

  // 204 No Content 应返回 undefined，而非尝试解析 JSON。
  test("returns undefined for 204 No Content", async () => {
    const client = new ClusterHttpClient(async () => new Response(null, { status: 204 }));

    const result = await client.json("http://cluster.test", "cluster-key", "/delete", 1000);
    expect(result).toBeUndefined();
  });

  // 401/403 认证错误应映射为 INVALID_REQUEST，不可重试。
  test("maps 401 to INVALID_REQUEST", async () => {
    const client = new ClusterHttpClient(async () => new Response("Unauthorized", { status: 401 }));

    await expect(client.json("http://cluster.test", "bad-key", "/api", 1000)).rejects.toMatchObject({
      code: "INVALID_REQUEST",
      retryable: false,
      status: 401,
    } satisfies Partial<SandboxProviderError>);
  });

  test("maps 403 to INVALID_REQUEST", async () => {
    const client = new ClusterHttpClient(async () => new Response("Forbidden", { status: 403 }));

    await expect(client.json("http://cluster.test", "bad-key", "/api", 1000)).rejects.toMatchObject({
      code: "INVALID_REQUEST",
      retryable: false,
      status: 403,
    } satisfies Partial<SandboxProviderError>);
  });

  // 网络层异常（如 AbortSignal.timeout 触发）应抛出 UNAVAILABLE 且 retryable=true。
  test("network error throws UNAVAILABLE with retryable=true", async () => {
    const client = new ClusterHttpClient(async () => {
      throw new DOMException("The operation was aborted", "AbortError");
    });

    await expect(client.json("http://cluster.test", "cluster-key", "/api", 1000)).rejects.toMatchObject({
      code: "UNAVAILABLE",
      retryable: true,
    } satisfies Partial<SandboxProviderError>);
  });
});
