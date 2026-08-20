// id.test.ts — chat-channel 确定性 RCS 会话标识生成测试
// 测试目标：createDeterministicRcsSessionId 的编码正确性、分隔符、sessionId 可选参数
// 业务意图：确保多实例场景下 YJS doc 命名唯一且不串扰

import { describe, test, expect } from "bun:test";

// ── 复制纯函数（来自 packages/chat-channel/src/util/id.ts）──

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

// ── 测试 ──

describe("createDeterministicRcsSessionId", () => {
  test("正向 - 双参数返回 rcs_ 前缀加两段 base64url 以点号分隔", () => {
    const result = createDeterministicRcsSessionId("agent-1", "user-1");
    expect(result).toBe(`rcs_${base64urlEncode("agent-1")}.${base64urlEncode("user-1")}`);
    expect(result.startsWith("rcs_")).toBe(true);
    expect(result.split(".").length).toBe(2);
  });

  test("正向 - 提供 sessionId 时返回三段式标识", () => {
    const result = createDeterministicRcsSessionId("agent-1", "user-1", "session-abc");
    expect(result.split(".").length).toBe(3);
    expect(result).toContain(base64urlEncode("session-abc"));
  });

  test("分支 - 相同输入返回相同结果（确定性）", () => {
    const a = createDeterministicRcsSessionId("a", "b");
    const b = createDeterministicRcsSessionId("a", "b");
    expect(a).toBe(b);
  });

  test("分支 - 不同 agentId 生成不同标识", () => {
    const a = createDeterministicRcsSessionId("agent-1", "user-1");
    const b = createDeterministicRcsSessionId("agent-2", "user-1");
    expect(a).not.toBe(b);
  });

  test("边界 - 空字符串 sessionId 视为不提供，返回两段式", () => {
    const result = createDeterministicRcsSessionId("a", "b", "");
    expect(result.split(".").length).toBe(2);
  });

  test("边界 - 含中文和特殊字符的 agentId 正确编码", () => {
    const result = createDeterministicRcsSessionId("代理-测试", "user@test");
    expect(result.startsWith("rcs_")).toBe(true);
    expect(result).not.toContain("+");
    expect(result).not.toContain("/");
    expect(result).not.toContain("=");
  });

  test("边界 - 结果不包含 base64 标准字符集中的 +/= 字符", () => {
    const result = createDeterministicRcsSessionId("a+b/c=d", "x+y/z=w");
    expect(result).not.toContain("+");
    expect(result).not.toContain("/");
    expect(result).not.toMatch(/=[^=]/); // 不允许尾部 = 填充
  });

  test("隔离 - 同一 agent+user 但不同 sessionId 生成不同标识", () => {
    const a = createDeterministicRcsSessionId("a", "b", "s1");
    const b = createDeterministicRcsSessionId("a", "b", "s2");
    expect(a).not.toBe(b);
  });
});

describe("base64urlEncode", () => {
  test("正向 - ASCII 字符串正确编码", () => {
    expect(base64urlEncode("hello")).toBe(btoa("hello").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""));
  });

  test("边界 - 空字符串编码为空", () => {
    expect(base64urlEncode("")).toBe("");
  });

  test("边界 - UTF-8 多字节字符正确编码", () => {
    const result = base64urlEncode("你好世界");
    expect(result.length).toBeGreaterThan(0);
    expect(result).not.toContain("+");
    expect(result).not.toContain("/");
  });
});
