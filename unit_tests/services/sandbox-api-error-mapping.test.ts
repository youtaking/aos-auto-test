import { describe, expect, test } from "bun:test";
import { SandboxProviderError } from "@fenix/sandbox-provider";
import { mapSandboxApiError } from "@fenix/routes/api/sandbox";
import { SandboxProviderNotConfiguredError, SandboxRuntimeNotReadyError } from "@fenix/services/sandbox/sandbox-errors";

describe("sandbox API error mapping", () => {
  // Pool 唯一约束冲突必须转换为资源冲突，而不是通用参数错误。
  test("maps PostgreSQL unique constraint errors to HTTP 409", () => {
    const error = Object.assign(new Error("duplicate key value violates unique constraint"), { code: "23505" });
    expect(mapSandboxApiError(error)).toEqual({
      status: 409,
      body: { error: { code: "CONFLICT", message: "duplicate key value violates unique constraint" } },
    });
  });

  // Provider 未注册时返回 503，message 统一为 "Sandbox service is unavailable"。
  test("maps an unconfigured provider to HTTP 503", () => {
    expect(mapSandboxApiError(new SandboxProviderNotConfiguredError("opensandbox-cluster"))).toEqual({
      status: 503,
      body: {
        error: { code: "SERVICE_UNAVAILABLE", message: "Sandbox service is unavailable" },
      },
    });
  });

  // SandboxRuntimeNotReadyError 同样返回 503，message 统一为 "Sandbox service is unavailable"。
  test("maps SandboxRuntimeNotReadyError to HTTP 503", () => {
    expect(mapSandboxApiError(new SandboxRuntimeNotReadyError("sbi_abc123"))).toEqual({
      status: 503,
      body: {
        error: { code: "SERVICE_UNAVAILABLE", message: "Sandbox service is unavailable" },
      },
    });
  });

  // Provider 的远程服务错误应保留为网关/服务不可用错误。
  test("maps provider unavailable errors to HTTP 503", () => {
    const error = new SandboxProviderError("cluster unavailable", "UNAVAILABLE", true);
    expect(mapSandboxApiError(error)).toEqual({
      status: 503,
      body: { error: { code: "SERVICE_UNAVAILABLE", message: "cluster unavailable" } },
    });
  });

  // Provider NOT_FOUND 错误映射为 404
  test("maps provider NOT_FOUND errors to HTTP 404", () => {
    const error = new SandboxProviderError("sandbox not found", "NOT_FOUND", false);
    expect(mapSandboxApiError(error)).toEqual({
      status: 404,
      body: { error: { code: "NOT_FOUND", message: "sandbox not found" } },
    });
  });

  // Provider INVALID_REQUEST 错误映射为 400
  test("maps provider INVALID_REQUEST errors to HTTP 400", () => {
    const error = new SandboxProviderError("invalid pool config", "INVALID_REQUEST", false);
    expect(mapSandboxApiError(error)).toEqual({
      status: 400,
      body: { error: { code: "BAD_REQUEST", message: "invalid pool config" } },
    });
  });
});
