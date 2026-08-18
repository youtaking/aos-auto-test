import { describe, test, expect } from "bun:test";

// ── Pure function copy from src/services/agent-concurrency.ts ──

/**
 * Determines if a runtime status string represents an active (non-terminal) state.
 * Only "stopped", "stopping", and "error" are considered inactive.
 */
function isActiveRuntimeStatus(status: string): boolean {
  return status !== "stopped" && status !== "stopping" && status !== "error";
}

// ── Tests ──

describe("isActiveRuntimeStatus", () => {
  test("'running' is active", () => {
    expect(isActiveRuntimeStatus("running")).toBe(true);
  });

  test("'starting' is active", () => {
    expect(isActiveRuntimeStatus("starting")).toBe(true);
  });

  test("'idle' is active", () => {
    expect(isActiveRuntimeStatus("idle")).toBe(true);
  });

  test("'stopped' is inactive", () => {
    expect(isActiveRuntimeStatus("stopped")).toBe(false);
  });

  test("'stopping' is inactive", () => {
    expect(isActiveRuntimeStatus("stopping")).toBe(false);
  });

  test("'error' is inactive", () => {
    expect(isActiveRuntimeStatus("error")).toBe(false);
  });

  test("unknown status defaults to active (only 3 listed are inactive)", () => {
    expect(isActiveRuntimeStatus("unknown")).toBe(true);
    expect(isActiveRuntimeStatus("paused")).toBe(true);
    expect(isActiveRuntimeStatus("suspended")).toBe(true);
    expect(isActiveRuntimeStatus("")).toBe(true);
  });

  test("case sensitivity: 'Stopped' is active (exact match only)", () => {
    expect(isActiveRuntimeStatus("Stopped")).toBe(true);
    expect(isActiveRuntimeStatus("STOPPED")).toBe(true);
    expect(isActiveRuntimeStatus("Error")).toBe(true);
  });

  test("whitespace variations are active (exact match only)", () => {
    expect(isActiveRuntimeStatus(" stopped")).toBe(true);
    expect(isActiveRuntimeStatus("stopped ")).toBe(true);
    expect(isActiveRuntimeStatus(" error ")).toBe(true);
  });
});
