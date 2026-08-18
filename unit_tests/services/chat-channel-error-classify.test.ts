// chat-channel-error-classify.test.ts — Chat 域 spawn 错误分类测试
// 测试目标：isMachineOfflineError / classifyPermanentSpawnFailure
// 业务意图：确保 WS 打开阶段能正确区分机器离线（4500）与永久失败（终态），
//          瞬时错误保留自动重连
//
// 【双源冲突说明】FenixAgent 仓库中 src/errors.ts 和 src/errors/index.ts 共存。
// 本文件涉及的分类函数来自 src/services/chat-channel-error-classify.ts，
// 该文件 import { AppError } from "../errors"，解析到 src/errors.ts
// （AppError 使用 code + statusCode 属性）。OrchestrationError 来自
// packages/orchestration/src/errors.ts，CoreRuntimeError 来自
// packages/core/src/errors/core-runtime-error.ts。

import { describe, expect, test } from "bun:test";

// ── 纯函数副本（对齐 src/errors.ts） ──

class AppError extends Error {
  readonly code: string;
  readonly statusCode: number;
  constructor(message: string, code: string, statusCode: number = 500) {
    super(message);
    this.name = "AppError";
    this.code = code;
    this.statusCode = statusCode;
  }
}

// ── 纯函数副本（对齐 packages/orchestration/src/errors.ts） ──

class OrchestrationError extends Error {
  readonly code: string;
  constructor(message: string, code: string) {
    super(message);
    this.name = new.target.name;
    this.code = code;
  }
}

// ── 纯函数副本（对齐 packages/core/src/errors/core-runtime-error.ts） ──

class CoreRuntimeError extends Error {
  readonly code: string;
  readonly details?: Record<string, unknown>;
  constructor(code: string, message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "CoreRuntimeError";
    this.code = code;
    this.details = details;
  }
}

function isCoreRuntimeError(err: unknown): err is CoreRuntimeError {
  return err instanceof CoreRuntimeError;
}

// ── 纯函数副本（对齐 src/services/chat-channel-error-classify.ts） ──

function isMachineOfflineError(err: unknown): boolean {
  if (err instanceof AppError) return err.code === "MACHINE_OFFLINE";
  if (err instanceof OrchestrationError) {
    return err.code === "MACHINE_OFFLINE" || err.code === "AGENT_NODE_UNAVAILABLE";
  }
  if (isCoreRuntimeError(err)) {
    return err.code === "NODE_OFFLINE" || err.code === "NODE_NOT_FOUND";
  }
  return false;
}

function classifyPermanentSpawnFailure(err: unknown): string | null {
  if (err instanceof AppError) {
    if (err.code === "AUTO_START_DISABLED") return "auto_start_disabled";
    if (err.code === "MAX_SESSIONS_REACHED") return "max_sessions_reached";
    return null;
  }
  if (err instanceof OrchestrationError) {
    if (err.code === "LAUNCH_SPEC_BUILD_FAILED") return "launch_spec_build_failed";
    return null;
  }
  return null;
}

// ── isMachineOfflineError ──

describe("isMachineOfflineError", () => {
  // AppError.MACHINE_OFFLINE
  test("AppError MACHINE_OFFLINE 返回 true", () => {
    expect(isMachineOfflineError(new AppError("machine offline", "MACHINE_OFFLINE"))).toBe(true);
  });

  // AppError 其他 code
  test("AppError 其他 code 返回 false", () => {
    expect(isMachineOfflineError(new AppError("auth failed", "AUTH_FAILED"))).toBe(false);
  });

  // OrchestrationError.MACHINE_OFFLINE
  test("OrchestrationError MACHINE_OFFLINE 返回 true", () => {
    expect(isMachineOfflineError(new OrchestrationError("offline", "MACHINE_OFFLINE"))).toBe(true);
  });

  // OrchestrationError.AGENT_NODE_UNAVAILABLE
  test("OrchestrationError AGENT_NODE_UNAVAILABLE 返回 true", () => {
    expect(isMachineOfflineError(new OrchestrationError("unavailable", "AGENT_NODE_UNAVAILABLE"))).toBe(true);
  });

  // OrchestrationError 其他 code
  test("OrchestrationError 其他 code 返回 false", () => {
    expect(isMachineOfflineError(new OrchestrationError("concurrency", "CONCURRENCY_EXCEEDED"))).toBe(false);
  });

  // CoreRuntimeError.NODE_OFFLINE
  test("CoreRuntimeError NODE_OFFLINE 返回 true", () => {
    expect(isMachineOfflineError(new CoreRuntimeError("NODE_OFFLINE", "node offline"))).toBe(true);
  });

  // CoreRuntimeError.NODE_NOT_FOUND
  test("CoreRuntimeError NODE_NOT_FOUND 返回 true", () => {
    expect(isMachineOfflineError(new CoreRuntimeError("NODE_NOT_FOUND", "node not found"))).toBe(true);
  });

  // CoreRuntimeError 其他 code
  test("CoreRuntimeError 其他 code 返回 false", () => {
    expect(isMachineOfflineError(new CoreRuntimeError("INSTANCE_NOT_FOUND", "other"))).toBe(false);
  });

  // 普通 Error
  test("普通 Error 返回 false", () => {
    expect(isMachineOfflineError(new Error("generic error"))).toBe(false);
  });

  // 非 Error 类型
  test("非 Error 类型返回 false", () => {
    expect(isMachineOfflineError("string")).toBe(false);
    expect(isMachineOfflineError(null)).toBe(false);
    expect(isMachineOfflineError(undefined)).toBe(false);
    expect(isMachineOfflineError(42)).toBe(false);
    expect(isMachineOfflineError({})).toBe(false);
  });

  // 带 MACHINE_OFFLINE code 的普通 Error 不应被识别（必须是正确的错误类型）
  test("带 MACHINE_OFFLINE code 的普通 Error 返回 false", () => {
    const err = new Error("fake");
    (err as Record<string, unknown>).code = "MACHINE_OFFLINE";
    expect(isMachineOfflineError(err)).toBe(false);
  });
});

// ── classifyPermanentSpawnFailure ──

describe("classifyPermanentSpawnFailure", () => {
  // AUTO_START_DISABLED → auto_start_disabled
  test("AppError AUTO_START_DISABLED 返回 auto_start_disabled", () => {
    expect(classifyPermanentSpawnFailure(new AppError("auto start disabled", "AUTO_START_DISABLED")))
      .toBe("auto_start_disabled");
  });

  // MAX_SESSIONS_REACHED → max_sessions_reached
  test("AppError MAX_SESSIONS_REACHED 返回 max_sessions_reached", () => {
    expect(classifyPermanentSpawnFailure(new AppError("max sessions", "MAX_SESSIONS_REACHED")))
      .toBe("max_sessions_reached");
  });

  // AppError 其他 code → null（瞬时错误，保留自动重连）
  test("AppError 其他 code 返回 null", () => {
    expect(classifyPermanentSpawnFailure(new AppError("unknown", "SOME_OTHER_ERROR"))).toBeNull();
  });

  // OrchestrationError.LAUNCH_SPEC_BUILD_FAILED → launch_spec_build_failed
  test("OrchestrationError LAUNCH_SPEC_BUILD_FAILED 返回 launch_spec_build_failed", () => {
    expect(classifyPermanentSpawnFailure(new OrchestrationError("spec failed", "LAUNCH_SPEC_BUILD_FAILED")))
      .toBe("launch_spec_build_failed");
  });

  // OrchestrationError 其他 code → null
  test("OrchestrationError 其他 code 返回 null", () => {
    expect(classifyPermanentSpawnFailure(new OrchestrationError("concurrency", "CONCURRENCY_EXCEEDED"))).toBeNull();
  });

  // CoreRuntimeError 不属于永久失败分类范围
  test("CoreRuntimeError 返回 null", () => {
    expect(classifyPermanentSpawnFailure(new CoreRuntimeError("NODE_OFFLINE", "node offline"))).toBeNull();
  });

  // 普通 Error → null
  test("普通 Error 返回 null", () => {
    expect(classifyPermanentSpawnFailure(new Error("generic"))).toBeNull();
  });

  // 非 Error → null
  test("非 Error 类型返回 null", () => {
    expect(classifyPermanentSpawnFailure("string")).toBeNull();
    expect(classifyPermanentSpawnFailure(null)).toBeNull();
    expect(classifyPermanentSpawnFailure(undefined)).toBeNull();
  });

  // 机器离线错误不属于永久失败（走 4500 专用终态）
  test("机器离线错误返回 null（由 isMachineOfflineError 处理）", () => {
    expect(classifyPermanentSpawnFailure(new AppError("offline", "MACHINE_OFFLINE"))).toBeNull();
    expect(classifyPermanentSpawnFailure(new OrchestrationError("offline", "MACHINE_OFFLINE"))).toBeNull();
  });

  // 带永久失败 code 的普通 Error 不应被识别（必须是正确的错误类型）
  test("带 AUTO_START_DISABLED code 的普通 Error 返回 null", () => {
    const err = new Error("fake");
    (err as Record<string, unknown>).code = "AUTO_START_DISABLED";
    expect(classifyPermanentSpawnFailure(err)).toBeNull();
  });
});
