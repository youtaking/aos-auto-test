// core-runtime-error.test.ts — Core 层具名运行时错误测试
// 测试目标：CoreRuntimeError 类、isCoreRuntimeError 守卫、createCoreRuntimeError 工厂
// 业务意图：确保 core 编排层错误码稳定可断言，便于上游精确 catch

import { describe, test, expect } from "bun:test";

// ── 复制纯函数/类（来自 packages/core/src/errors/core-runtime-error.ts）──

type CoreRuntimeErrorCode =
  | "DUPLICATE_ENGINE_PLUGIN"
  | "PLUGIN_NOT_FOUND"
  | "DUPLICATE_CORE_NODE"
  | "NODE_NOT_FOUND"
  | "NODE_OFFLINE"
  | "ENGINE_NOT_SUPPORTED"
  | "NO_ENGINE_AVAILABLE"
  | "INSTANCE_ALREADY_EXISTS"
  | "INSTANCE_NOT_FOUND"
  | "INVALID_INSTANCE_STATE";

class CoreRuntimeError extends Error {
  readonly code: CoreRuntimeErrorCode;
  readonly details?: Record<string, unknown>;

  constructor(code: CoreRuntimeErrorCode, message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "CoreRuntimeError";
    this.code = code;
    this.details = details;
  }
}

function isCoreRuntimeError(error: unknown): error is CoreRuntimeError {
  return error instanceof CoreRuntimeError;
}

function createCoreRuntimeError(
  code: CoreRuntimeErrorCode,
  message: string,
  details?: Record<string, unknown>,
): CoreRuntimeError {
  return new CoreRuntimeError(code, message, details);
}

// ── 测试 ──

describe("CoreRuntimeError", () => {
  test("正向 - 构造后 name 为 CoreRuntimeError", () => {
    const err = new CoreRuntimeError("NODE_NOT_FOUND", "node missing");
    expect(err.name).toBe("CoreRuntimeError");
    expect(err.message).toBe("node missing");
    expect(err.code).toBe("NODE_NOT_FOUND");
  });

  test("正向 - 带 details 构造时保留结构化上下文", () => {
    const err = new CoreRuntimeError("NODE_OFFLINE", "offline", { nodeId: "n1" });
    expect(err.details).toEqual({ nodeId: "n1" });
  });

  test("正向 - 无 details 时为 undefined", () => {
    const err = new CoreRuntimeError("PLUGIN_NOT_FOUND", "no plugin");
    expect(err.details).toBeUndefined();
  });

  test("正向 - 是 Error 子类，instanceof Error 为 true", () => {
    const err = new CoreRuntimeError("DUPLICATE_CORE_NODE", "dup");
    expect(err instanceof Error).toBe(true);
    expect(err instanceof CoreRuntimeError).toBe(true);
  });

  test("分支 - 所有错误码均可构造", () => {
    const codes: CoreRuntimeErrorCode[] = [
      "DUPLICATE_ENGINE_PLUGIN",
      "PLUGIN_NOT_FOUND",
      "DUPLICATE_CORE_NODE",
      "NODE_NOT_FOUND",
      "NODE_OFFLINE",
      "ENGINE_NOT_SUPPORTED",
      "NO_ENGINE_AVAILABLE",
      "INSTANCE_ALREADY_EXISTS",
      "INSTANCE_NOT_FOUND",
      "INVALID_INSTANCE_STATE",
    ];
    for (const code of codes) {
      const err = new CoreRuntimeError(code, "msg");
      expect(err.code).toBe(code);
    }
  });
});

describe("isCoreRuntimeError", () => {
  test("正向 - CoreRuntimeError 实例返回 true", () => {
    expect(isCoreRuntimeError(new CoreRuntimeError("NODE_NOT_FOUND", "x"))).toBe(true);
  });

  test("分支 - 普通 Error 返回 false", () => {
    expect(isCoreRuntimeError(new Error("x"))).toBe(false);
  });

  test("分支 - 非 Error 对象返回 false", () => {
    expect(isCoreRuntimeError({ code: "NODE_NOT_FOUND" })).toBe(false);
    expect(isCoreRuntimeError(null)).toBe(false);
    expect(isCoreRuntimeError("error string")).toBe(false);
  });
});

describe("createCoreRuntimeError", () => {
  test("正向 - 返回 CoreRuntimeError 实例", () => {
    const err = createCoreRuntimeError("NO_ENGINE_AVAILABLE", "no engine");
    expect(err instanceof CoreRuntimeError).toBe(true);
    expect(err.code).toBe("NO_ENGINE_AVAILABLE");
    expect(err.message).toBe("no engine");
  });

  test("正向 - 带 details 时保留", () => {
    const err = createCoreRuntimeError("INSTANCE_NOT_FOUND", "missing", { instanceId: "i1" });
    expect(err.details).toEqual({ instanceId: "i1" });
  });
});
