// chat-channel-error-classify.test.ts — Chat 域 spawn 错误分类测试
// 测试目标：isMachineOfflineError / classifyPermanentSpawnFailure
// 业务意图：确保 WS 打开阶段能正确区分机器离线（4500）与永久失败（终态），
//          瞬时错误保留自动重连

import { describe, expect, test } from "bun:test";

// ── 复制错误类和分类函数 ──

class AppError extends Error {
  readonly code: string;
  constructor(message: string, code: string) {
    super(message);
    this.name = "AppError";
    this.code = code;
  }
}

class OrchestrationError extends Error {
  readonly code: string;
  constructor(message: string, code: string) {
    super(message);
    this.name = new.target.name;
    this.code = code;
  }
}

class CoreRuntimeError extends Error {
  readonly code: string;
  readonly _isCoreRuntimeError = true;
  constructor(message: string, code: string) {
    super(message);
    this.name = "CoreRuntimeError";
    this.code = code;
  }
}

function isCoreRuntimeError(err: unknown): err is CoreRuntimeError {
  return err instanceof Error && (err as CoreRuntimeError)._isCoreRuntimeError === true;
}

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
    expect(isMachineOfflineError(new CoreRuntimeError("node offline", "NODE_OFFLINE"))).toBe(true);
  });

  // CoreRuntimeError.NODE_NOT_FOUND
  test("CoreRuntimeError NODE_NOT_FOUND 返回 true", () => {
    expect(isMachineOfflineError(new CoreRuntimeError("node not found", "NODE_NOT_FOUND"))).toBe(true);
  });

  // CoreRuntimeError 其他 code
  test("CoreRuntimeError 其他 code 返回 false", () => {
    expect(isMachineOfflineError(new CoreRuntimeError("other", "OTHER_ERROR"))).toBe(false);
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

  // 普通 Error → null
  test("普通 Error 返回 null", () => {
    expect(classifyPermanentSpawnFailure(new Error("generic"))).toBeNull();
  });

  // 非 Error → null
  test("非 Error 类型返回 null", () => {
    expect(classifyPermanentSpawnFailure("string")).toBeNull();
    expect(classifyPermanentSpawnFailure(null)).toBeNull();
  });

  // 机器离线错误不属于永久失败（走 4500 专用终态）
  test("机器离线错误返回 null（由 isMachineOfflineError 处理）", () => {
    expect(classifyPermanentSpawnFailure(new AppError("offline", "MACHINE_OFFLINE"))).toBeNull();
    expect(classifyPermanentSpawnFailure(new OrchestrationError("offline", "MACHINE_OFFLINE"))).toBeNull();
  });
});
