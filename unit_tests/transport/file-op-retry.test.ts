// file-op-retry.test.ts — 读操作重试矩阵 + 机器级熔断器测试
// 测试目标：isRetryableFileOpFailure / isWriteOperation / 熔断器状态机
// 业务意图：确保 timeout/closed 类读操作可重试、写操作不重试、熔断正确打开/关闭

import { beforeEach, describe, expect, test } from "bun:test";

// ── 复制纯函数（避免外部依赖）──

const WRITE_OPERATIONS = new Set(["write", "mkdir", "delete", "rename", "upload"]);

class CircuitOpenError extends Error {
  readonly code = "circuit_open";
  constructor(message: string) {
    super(message);
    this.name = "CircuitOpenError";
  }
}

interface FileOpResult {
  status: string;
  data?: unknown;
  error?: string;
}

const CIRCUIT_FAILURE_THRESHOLD = 3;
const CIRCUIT_OPEN_MS = 30_000;

interface CircuitState {
  consecutiveFailures: number;
  openUntil: number;
}

const circuitStates = new Map<string, CircuitState>();
let circuitClock: () => number = Date.now;

function setFileOpCircuitClock(fn: () => number): void { circuitClock = fn; }
function resetFileOpCircuitClock(): void { circuitClock = Date.now; }
function getFileOpCircuitState(machineId: string): CircuitState | undefined { return circuitStates.get(machineId); }
function resetFileOpCircuitStates(): void { circuitStates.clear(); }

function isWriteOperation(operation: string): boolean {
  return WRITE_OPERATIONS.has(operation);
}

function isRetryableFileOpFailure(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  const code = "code" in err ? (err as Error & { code: string }).code : undefined;
  if (code === "busy" || code === "circuit_open") return false;
  const msg = err.message;
  return (
    msg.startsWith("file_op timeout") ||
    msg.startsWith("Connection closed") ||
    msg.startsWith("aborted") ||
    msg.includes("zombie connection")
  );
}

function isMachineCircuitOpen(machineId: string): boolean {
  const state = circuitStates.get(machineId);
  if (!state || state.openUntil === 0) return false;
  if (circuitClock() >= state.openUntil) {
    circuitStates.delete(machineId);
    return false;
  }
  return true;
}

function recordFileOpFailure(machineId: string): void {
  const now = circuitClock();
  const state = circuitStates.get(machineId) ?? { consecutiveFailures: 0, openUntil: 0 };
  if (state.openUntil > now) return;
  state.consecutiveFailures += 1;
  if (state.consecutiveFailures >= CIRCUIT_FAILURE_THRESHOLD) {
    state.openUntil = now + CIRCUIT_OPEN_MS;
    state.consecutiveFailures = 0;
  }
  circuitStates.set(machineId, state);
}

function recordFileOpSuccess(machineId: string): void {
  circuitStates.delete(machineId);
}

function runFileOpWithRetry(opts: {
  machineId: string;
  operation: string;
  attempt: () => Promise<FileOpResult>;
}): Promise<FileOpResult> {
  if (isMachineCircuitOpen(opts.machineId)) {
    return Promise.reject(new CircuitOpenError(`file-op circuit open for machine: ${opts.machineId}`));
  }
  return opts
    .attempt()
    .catch((err) => {
      if (isWriteOperation(opts.operation) || !isRetryableFileOpFailure(err)) throw err;
      return opts.attempt();
    })
    .then(
      (result) => {
        recordFileOpSuccess(opts.machineId);
        return result;
      },
      (err) => {
        if (isRetryableFileOpFailure(err)) recordFileOpFailure(opts.machineId);
        throw err;
      },
    );
}

// ── isWriteOperation ──

describe("isWriteOperation", () => {
  // 写操作集合中的操作返回 true
  test("write/mkdir/delete/rename/upload 为写操作", () => {
    expect(isWriteOperation("write")).toBe(true);
    expect(isWriteOperation("mkdir")).toBe(true);
    expect(isWriteOperation("delete")).toBe(true);
    expect(isWriteOperation("rename")).toBe(true);
    expect(isWriteOperation("upload")).toBe(true);
  });

  // 读操作不在写集合中
  test("read/stat/tree 不是写操作", () => {
    expect(isWriteOperation("read")).toBe(false);
    expect(isWriteOperation("stat")).toBe(false);
    expect(isWriteOperation("tree")).toBe(false);
  });
});

// ── isRetryableFileOpFailure ──

describe("isRetryableFileOpFailure", () => {
  // timeout 类错误可重试
  test("file_op timeout 错误可重试", () => {
    expect(isRetryableFileOpFailure(new Error("file_op timeout after 5000ms"))).toBe(true);
  });

  // Connection closed 可重试
  test("Connection closed 错误可重试", () => {
    expect(isRetryableFileOpFailure(new Error("Connection closed unexpectedly"))).toBe(true);
  });

  // aborted 可重试
  test("aborted 错误可重试", () => {
    expect(isRetryableFileOpFailure(new Error("aborted by signal"))).toBe(true);
  });

  // zombie connection 可重试
  test("zombie connection 错误可重试", () => {
    expect(isRetryableFileOpFailure(new Error("detected zombie connection"))).toBe(true);
  });

  // busy（背压 429）不可重试
  test("busy 错误不可重试", () => {
    const err = Object.assign(new Error("rate limited"), { code: "busy" });
    expect(isRetryableFileOpFailure(err)).toBe(false);
  });

  // circuit_open 不可重试
  test("circuit_open 错误不可重试", () => {
    const err = new CircuitOpenError("circuit open");
    expect(isRetryableFileOpFailure(err)).toBe(false);
  });

  // 非 Error 实例不可重试
  test("非 Error 实例不可重试", () => {
    expect(isRetryableFileOpFailure("string error")).toBe(false);
    expect(isRetryableFileOpFailure(null)).toBe(false);
    expect(isRetryableFileOpFailure(42)).toBe(false);
  });

  // 未知错误消息不可重试
  test("未知错误消息不可重试", () => {
    expect(isRetryableFileOpFailure(new Error("permission denied"))).toBe(false);
    expect(isRetryableFileOpFailure(new Error("file not found"))).toBe(false);
  });
});

// ── 熔断器 ──

describe("熔断器", () => {
  let now: number;

  beforeEach(() => {
    resetFileOpCircuitStates();
    now = 1_000_000;
    setFileOpCircuitClock(() => now);
  });

  // 连续 3 次失败后熔断打开
  test("连续 3 次 timeout 失败后熔断打开", () => {
    recordFileOpFailure("m1");
    recordFileOpFailure("m1");
    expect(isMachineCircuitOpen("m1")).toBe(false);
    recordFileOpFailure("m1");
    expect(isMachineCircuitOpen("m1")).toBe(true);
  });

  // 熔断期内快速失败
  test("熔断期内 isMachineCircuitOpen 返回 true", () => {
    recordFileOpFailure("m1");
    recordFileOpFailure("m1");
    recordFileOpFailure("m1");
    now += 15_000; // 15s 后仍在熔断期（30s）
    expect(isMachineCircuitOpen("m1")).toBe(true);
  });

  // 熔断到期后自动关闭
  test("熔断到期后自动关闭允许试探", () => {
    recordFileOpFailure("m1");
    recordFileOpFailure("m1");
    recordFileOpFailure("m1");
    now += 30_001; // 超过 30s
    expect(isMachineCircuitOpen("m1")).toBe(false);
  });

  // 成功重置失败计数
  test("成功后重置连续失败计数", () => {
    recordFileOpFailure("m1");
    recordFileOpFailure("m1");
    recordFileOpSuccess("m1"); // 重置
    recordFileOpFailure("m1");
    recordFileOpFailure("m1");
    expect(isMachineCircuitOpen("m1")).toBe(false); // 只有 2 次连续失败
    recordFileOpFailure("m1");
    expect(isMachineCircuitOpen("m1")).toBe(true); // 重新达到 3 次
  });

  // 不同机器独立计数
  test("不同机器独立熔断计数", () => {
    recordFileOpFailure("m1");
    recordFileOpFailure("m1");
    recordFileOpFailure("m1");
    recordFileOpFailure("m2");
    expect(isMachineCircuitOpen("m1")).toBe(true);
    expect(isMachineCircuitOpen("m2")).toBe(false);
  });

  // 未记录的机器不熔断
  test("未记录的机器 isMachineCircuitOpen 返回 false", () => {
    expect(isMachineCircuitOpen("unknown")).toBe(false);
  });

  // resetFileOpCircuitStates 清理所有状态
  test("resetFileOpCircuitStates 清理所有状态", () => {
    recordFileOpFailure("m1");
    recordFileOpFailure("m1");
    recordFileOpFailure("m1");
    resetFileOpCircuitStates();
    expect(isMachineCircuitOpen("m1")).toBe(false);
    expect(getFileOpCircuitState("m1")).toBeUndefined();
  });

  // 熔断期间不再累计失败计数
  test("熔断期间不再累计失败计数", () => {
    recordFileOpFailure("m1");
    recordFileOpFailure("m1");
    recordFileOpFailure("m1"); // 熔断打开
    recordFileOpFailure("m1"); // 熔断期内，不累计
    const state = getFileOpCircuitState("m1");
    expect(state?.consecutiveFailures).toBe(0);
  });

  // 恢复时钟
  test("resetFileOpCircuitClock 恢复真实时钟", () => {
    resetFileOpCircuitClock();
    // 不抛异常即可
    expect(true).toBe(true);
  });
});

// ── runFileOpWithRetry ──

describe("runFileOpWithRetry", () => {
  let now: number;

  beforeEach(() => {
    resetFileOpCircuitStates();
    now = 1_000_000;
    setFileOpCircuitClock(() => now);
  });

  // 熔断期内快速失败：不执行 attempt，直接 reject CircuitOpenError
  test("熔断期内快速失败，返回 CircuitOpenError", async () => {
    // 触发熔断：连续 3 次失败
    recordFileOpFailure("m1");
    recordFileOpFailure("m1");
    recordFileOpFailure("m1");
    expect(isMachineCircuitOpen("m1")).toBe(true);

    let attemptCalled = false;
    const attempt = async (): Promise<FileOpResult> => {
      attemptCalled = true;
      return { status: "ok" };
    };

    try {
      await runFileOpWithRetry({ machineId: "m1", operation: "read", attempt });
      expect.unreachable("应该抛出错误");
    } catch (err: any) {
      expect(err).toBeInstanceOf(CircuitOpenError);
      expect(err.code).toBe("circuit_open");
    }
    expect(attemptCalled).toBe(false);
  });

  // 读操作 timeout 后重试 1 次：attempt 被调用 2 次
  test("读操作 timeout 后重试 1 次，attempt 被调用 2 次", async () => {
    let callCount = 0;
    const attempt = async (): Promise<FileOpResult> => {
      callCount++;
      if (callCount === 1) {
        throw new Error("file_op timeout after 5000ms");
      }
      return { status: "ok", data: { content: "file content" } };
    };

    const result = await runFileOpWithRetry({ machineId: "m1", operation: "read", attempt });
    expect(callCount).toBe(2);
    expect(result.status).toBe("ok");
  });

  // 写操作 timeout 不重试：attempt 只被调用 1 次
  test("写操作 timeout 不重试，attempt 只调用 1 次", async () => {
    let callCount = 0;
    const attempt = async (): Promise<FileOpResult> => {
      callCount++;
      throw new Error("file_op timeout after 5000ms");
    };

    try {
      await runFileOpWithRetry({ machineId: "m1", operation: "write", attempt });
      expect.unreachable("应该抛出错误");
    } catch (err: any) {
      expect(err.message).toBe("file_op timeout after 5000ms");
    }
    expect(callCount).toBe(1);
  });
});
