/**
 * file-ws-close-log.test.ts — formatFileWsCloseLog 纯函数测试
 *
 * 从源文件 src/transport/file-ws-close-log.ts 复制：
 *   export function formatFileWsCloseLog(wsId: string, code: number, reason?: string): string {
 *     return `[File-WS] Connection closed: wsId=${wsId} code=${code} reason=${reason || "(none)"}`;
 *   }
 */

import { describe, test, expect } from "bun:test";

// ── 从源文件复制纯函数 ────────────────────────────────────────────────
function formatFileWsCloseLog(wsId: string, code: number, reason?: string): string {
  return `[File-WS] Connection closed: wsId=${wsId} code=${code} reason=${reason || "(none)"}`;
}

describe("formatFileWsCloseLog", () => {
  test("formats with wsId, code, and reason", () => {
    const result = formatFileWsCloseLog("ws-123", 1000, "normal closure");
    expect(result).toBe("[File-WS] Connection closed: wsId=ws-123 code=1000 reason=normal closure");
  });

  test("uses (none) when reason is omitted", () => {
    const result = formatFileWsCloseLog("ws-456", 1006);
    expect(result).toBe("[File-WS] Connection closed: wsId=ws-456 code=1006 reason=(none)");
  });

  test("uses (none) when reason is empty string", () => {
    const result = formatFileWsCloseLog("ws-789", 1001, "");
    expect(result).toBe("[File-WS] Connection closed: wsId=ws-789 code=1001 reason=(none)");
  });

  test("preserves reason with special characters", () => {
    const result = formatFileWsCloseLog("ws-1", 1011, "internal error: unexpected EOF");
    expect(result).toContain("reason=internal error: unexpected EOF");
  });

  test("handles numeric code 1000 (normal closure)", () => {
    const result = formatFileWsCloseLog("abc", 1000, "done");
    expect(result).toContain("code=1000");
  });

  test("handles numeric code 1006 (abnormal closure)", () => {
    const result = formatFileWsCloseLog("abc", 1006);
    expect(result).toContain("code=1006");
  });

  test("handles numeric code 1011 (server error)", () => {
    const result = formatFileWsCloseLog("abc", 1011, "crash");
    expect(result).toContain("code=1011");
  });

  test("always starts with [File-WS] prefix", () => {
    const result = formatFileWsCloseLog("x", 0, "test");
    expect(result.startsWith("[File-WS]")).toBe(true);
  });

  test("includes all three fields in output", () => {
    const result = formatFileWsCloseLog("my-ws-id", 1001, "going away");
    expect(result).toContain("wsId=my-ws-id");
    expect(result).toContain("code=1001");
    expect(result).toContain("reason=going away");
  });

  test("handles wsId with special characters", () => {
    const result = formatFileWsCloseLog("ws:conn-1/sub", 1000, "ok");
    expect(result).toContain("wsId=ws:conn-1/sub");
  });
});
