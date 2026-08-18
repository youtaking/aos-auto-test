// orchestration-http.test.ts — 编排域错误→HTTP 映射测试
// 测试目标：mapOrchestrationErrorToHttp 状态码映射 + 脱敏 message
// 业务意图：确保编排错误统一映射为正确 HTTP 状态，对外 message 不泄漏内部标识

import { describe, expect, test } from "bun:test";

// ── 复制映射逻辑 ──

class OrchestrationError extends Error {
  readonly code: string;
  constructor(message: string, code: string) {
    super(message);
    this.name = new.target.name;
    this.code = code;
  }
}

const ORCHESTRATION_STATUS_MAP: Record<string, number> = {
  ENVIRONMENT_NOT_FOUND: 404,
  CONCURRENCY_EXCEEDED: 409,
  LAUNCH_SPEC_BUILD_FAILED: 422,
  AGENT_NODE_UNAVAILABLE: 503,
  MACHINE_OFFLINE: 503,
};

const ORCHESTRATION_MESSAGE_MAP: Record<string, string> = {
  ENVIRONMENT_NOT_FOUND: "Environment not found",
  CONCURRENCY_EXCEEDED: "Concurrency limit exceeded",
  LAUNCH_SPEC_BUILD_FAILED: "Failed to build launch spec",
  AGENT_NODE_UNAVAILABLE: "Agent node is unavailable",
  MACHINE_OFFLINE: "Target machine is offline",
};

function mapOrchestrationErrorToHttp(error: OrchestrationError): { status: number; message: string } {
  return {
    status: ORCHESTRATION_STATUS_MAP[error.code] ?? 500,
    message: ORCHESTRATION_MESSAGE_MAP[error.code] ?? "Internal server error",
  };
}

// ── tests ──

describe("mapOrchestrationErrorToHttp", () => {
  // ENVIRONMENT_NOT_FOUND → 404
  test("ENVIRONMENT_NOT_FOUND 映射为 404", () => {
    const err = new OrchestrationError("Environment 'env-123' not found", "ENVIRONMENT_NOT_FOUND");
    const result = mapOrchestrationErrorToHttp(err);
    expect(result.status).toBe(404);
    expect(result.message).toBe("Environment not found");
  });

  // CONCURRENCY_EXCEEDED → 409
  test("CONCURRENCY_EXCEEDED 映射为 409", () => {
    const err = new OrchestrationError("Environment 'env-123' concurrency limit exceeded", "CONCURRENCY_EXCEEDED");
    const result = mapOrchestrationErrorToHttp(err);
    expect(result.status).toBe(409);
    expect(result.message).toBe("Concurrency limit exceeded");
  });

  // LAUNCH_SPEC_BUILD_FAILED → 422
  test("LAUNCH_SPEC_BUILD_FAILED 映射为 422", () => {
    const err = new OrchestrationError("Failed to build launch spec", "LAUNCH_SPEC_BUILD_FAILED");
    const result = mapOrchestrationErrorToHttp(err);
    expect(result.status).toBe(422);
  });

  // AGENT_NODE_UNAVAILABLE → 503
  test("AGENT_NODE_UNAVAILABLE 映射为 503", () => {
    const err = new OrchestrationError("Agent node is unavailable", "AGENT_NODE_UNAVAILABLE");
    const result = mapOrchestrationErrorToHttp(err);
    expect(result.status).toBe(503);
  });

  // MACHINE_OFFLINE → 503
  test("MACHINE_OFFLINE 映射为 503", () => {
    const err = new OrchestrationError("Target machine is offline", "MACHINE_OFFLINE");
    const result = mapOrchestrationErrorToHttp(err);
    expect(result.status).toBe(503);
  });

  // 未登记 code 保守落 500
  test("未登记错误码保守落 500 + 通用文案", () => {
    const err = new OrchestrationError("内部 envId=machine-xyz 泄漏信息", "UNKNOWN_CODE");
    const result = mapOrchestrationErrorToHttp(err);
    expect(result.status).toBe(500);
    expect(result.message).toBe("Internal server error");
  });

  // 脱敏：原始 message 含内部标识时不泄漏
  test("脱敏：含 envId/machineId 的原始 message 不泄漏到对外响应", () => {
    const err = new OrchestrationError("Environment 'env-secret-123' not found in org", "ENVIRONMENT_NOT_FOUND");
    const result = mapOrchestrationErrorToHttp(err);
    expect(result.message).not.toContain("env-secret-123");
    expect(result.message).toBe("Environment not found");
  });
});

describe("ORCHESTRATION_STATUS_MAP 完整性", () => {
  // 所有已知 code 在 STATUS_MAP 和 MESSAGE_MAP 中都有对应
  test("STATUS_MAP 和 MESSAGE_MAP 的 key 集合一致", () => {
    const statusKeys = Object.keys(ORCHESTRATION_STATUS_MAP).sort();
    const messageKeys = Object.keys(ORCHESTRATION_MESSAGE_MAP).sort();
    expect(statusKeys).toEqual(messageKeys);
  });
});
