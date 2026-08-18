import { describe, test, expect } from "bun:test";

// ========== Pure function copies from packages/chat-channel/src/util/id.ts ==========

function base64urlEncode(str: string): string {
  const bytes = new TextEncoder().encode(str);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function createDeterministicRcsSessionId(agentId: string, userId: string, sessionId?: string): string {
  const parts = [base64urlEncode(agentId), base64urlEncode(userId)];
  if (sessionId) {
    parts.push(base64urlEncode(sessionId));
  }
  return `rcs_${parts.join(".")}`;
}

// ========== Tests ==========

describe("base64urlEncode", () => {
  test("encodes ASCII string", () => {
    const result = base64urlEncode("hello");
    expect(result).toBe("aGVsbG8");
  });

  test("encodes empty string", () => {
    const result = base64urlEncode("");
    expect(result).toBe("");
  });

  test("uses URL-safe characters (no + / =)", () => {
    // Characters that would produce + / = in standard base64
    const result = base64urlEncode("subjects?_d");
    expect(result).not.toContain("+");
    expect(result).not.toContain("/");
    expect(result).not.toContain("=");
  });

  test("encodes unicode string", () => {
    const result = base64urlEncode("你好");
    // Should not throw and should produce a non-empty string
    expect(result.length).toBeGreaterThan(0);
    expect(result).not.toContain("+");
    expect(result).not.toContain("/");
    expect(result).not.toContain("=");
  });
});

describe("createDeterministicRcsSessionId", () => {
  test("is deterministic - same inputs produce same output", () => {
    const id1 = createDeterministicRcsSessionId("agent-1", "user-1");
    const id2 = createDeterministicRcsSessionId("agent-1", "user-1");
    expect(id1).toBe(id2);
  });

  test("starts with 'rcs_' prefix", () => {
    const id = createDeterministicRcsSessionId("agent", "user");
    expect(id.startsWith("rcs_")).toBe(true);
  });

  test("has two parts without sessionId", () => {
    const id = createDeterministicRcsSessionId("agent", "user");
    const withoutPrefix = id.slice(4); // remove "rcs_"
    const parts = withoutPrefix.split(".");
    expect(parts.length).toBe(2);
  });

  test("has three parts with sessionId", () => {
    const id = createDeterministicRcsSessionId("agent", "user", "session-123");
    const withoutPrefix = id.slice(4);
    const parts = withoutPrefix.split(".");
    expect(parts.length).toBe(3);
  });

  test("different agentId produces different ID", () => {
    const id1 = createDeterministicRcsSessionId("agent-a", "user");
    const id2 = createDeterministicRcsSessionId("agent-b", "user");
    expect(id1).not.toBe(id2);
  });

  test("different userId produces different ID", () => {
    const id1 = createDeterministicRcsSessionId("agent", "user-a");
    const id2 = createDeterministicRcsSessionId("agent", "user-b");
    expect(id1).not.toBe(id2);
  });

  test("different sessionId produces different ID", () => {
    const id1 = createDeterministicRcsSessionId("agent", "user", "s1");
    const id2 = createDeterministicRcsSessionId("agent", "user", "s2");
    expect(id1).not.toBe(id2);
  });

  test("handles unicode and special characters", () => {
    const id = createDeterministicRcsSessionId("智能体-1", "用户@test.com", "会话/123");
    expect(id.startsWith("rcs_")).toBe(true);
    const withoutPrefix = id.slice(4);
    const parts = withoutPrefix.split(".");
    expect(parts.length).toBe(3);
    // Each part should be valid base64url
    for (const part of parts) {
      expect(part).not.toContain("+");
      expect(part).not.toContain("/");
      expect(part).not.toContain("=");
    }
  });

  test("empty sessionId is treated as not provided", () => {
    const id1 = createDeterministicRcsSessionId("agent", "user");
    const id2 = createDeterministicRcsSessionId("agent", "user", "");
    expect(id1).toBe(id2);
  });

  test("produces URL-safe output", () => {
    const id = createDeterministicRcsSessionId(
      "agent+special/chars=test",
      "user+special/chars=test",
      "session+special/chars=test",
    );
    // The entire ID should only contain URL-safe chars (plus rcs_ prefix and dots)
    expect(id).toMatch(/^rcs_[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/);
  });

  test("encodes known values correctly", () => {
    // "agent" -> base64url: "YWdlbnQ"
    // "user" -> base64url: "dXNlcg"
    const id = createDeterministicRcsSessionId("agent", "user");
    expect(id).toBe("rcs_YWdlbnQ.dXNlcg");
  });
});
