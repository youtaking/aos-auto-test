import { describe, expect, test } from "bun:test";

// 测试 timeout 检测使用 instanceof Error 而非 DOMException（兼容 Node.js/Bun）

describe("timeout detection instanceof Error", () => {
  function isTimeoutError(err: unknown): boolean {
    return err instanceof Error && (err.name === "AbortError" || err.name === "TimeoutError");
  }

  test("detects DOMException TimeoutError (Bun runtime)", () => {
    const err = new DOMException("The operation was aborted due to timeout", "TimeoutError");
    expect(isTimeoutError(err)).toBe(true);
  });

  test("detects DOMException AbortError", () => {
    const err = new DOMException("The operation was aborted", "AbortError");
    expect(isTimeoutError(err)).toBe(true);
  });

  test("detects plain Error with name TimeoutError (Node.js runtime)", () => {
    const err = new Error("Timeout");
    err.name = "TimeoutError";
    expect(isTimeoutError(err)).toBe(true);
  });

  test("detects plain Error with name AbortError", () => {
    const err = new Error("Aborted");
    err.name = "AbortError";
    expect(isTimeoutError(err)).toBe(true);
  });

  test("non-Error objects are not detected as timeout", () => {
    expect(isTimeoutError("string error")).toBe(false);
    expect(isTimeoutError(42)).toBe(false);
    expect(isTimeoutError(null)).toBe(false);
    expect(isTimeoutError(undefined)).toBe(false);
  });

  test("generic Error is not detected as timeout", () => {
    const err = new Error("Network error");
    expect(isTimeoutError(err)).toBe(false);
  });

  test("TypeError is not detected as timeout", () => {
    const err = new TypeError("fetch failed");
    expect(isTimeoutError(err)).toBe(false);
  });
});
