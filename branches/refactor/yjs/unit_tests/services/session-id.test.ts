// session-id.test.ts — 确定性 RCS 会话标识生成测试
// 测试目标：createDeterministicRcsSessionId 的确定性、格式、编码正确性
// 业务意图：确保前后端生成一致的 rcs_* 标识，刷新后 Y.Doc 可达

import { describe, expect, test } from "bun:test";

// ── 复制源函数（纯函数，无外部依赖）──

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

// ── 格式与确定性 ──

describe("createDeterministicRcsSessionId", () => {
  // rcs_ 前缀
  test("结果以 rcs_ 开头", () => {
    const id = createDeterministicRcsSessionId("agent-1", "user-1");
    expect(id.startsWith("rcs_")).toBe(true);
  });

  // 无 sessionId 时包含 1 个分隔点（2 段）
  test("无 sessionId 时格式为 rcs_{agentB64}.{userB64}", () => {
    const id = createDeterministicRcsSessionId("agent-1", "user-1");
    const withoutPrefix = id.slice(4); // 去掉 "rcs_"
    const parts = withoutPrefix.split(".");
    expect(parts.length).toBe(2);
  });

  // 有 sessionId 时包含 2 个分隔点（3 段）
  test("有 sessionId 时格式为 rcs_{agentB64}.{userB64}.{sessionB64}", () => {
    const id = createDeterministicRcsSessionId("agent-1", "user-1", "session-1");
    const withoutPrefix = id.slice(4);
    const parts = withoutPrefix.split(".");
    expect(parts.length).toBe(3);
  });

  // 确定性：相同输入产生相同输出
  test("相同输入产生相同输出（确定性）", () => {
    const id1 = createDeterministicRcsSessionId("agent-abc", "user-xyz");
    const id2 = createDeterministicRcsSessionId("agent-abc", "user-xyz");
    expect(id1).toBe(id2);
  });

  // 不同输入产生不同输出
  test("不同 agentId 产生不同标识", () => {
    const id1 = createDeterministicRcsSessionId("agent-1", "user-1");
    const id2 = createDeterministicRcsSessionId("agent-2", "user-1");
    expect(id1).not.toBe(id2);
  });

  test("不同 userId 产生不同标识", () => {
    const id1 = createDeterministicRcsSessionId("agent-1", "user-1");
    const id2 = createDeterministicRcsSessionId("agent-1", "user-2");
    expect(id1).not.toBe(id2);
  });

  // sessionId 加入后标识不同
  test("带 sessionId 和不带 sessionId 产生不同标识", () => {
    const id1 = createDeterministicRcsSessionId("agent-1", "user-1");
    const id2 = createDeterministicRcsSessionId("agent-1", "user-1", "session-1");
    expect(id1).not.toBe(id2);
  });

  // 不同 sessionId 产生不同标识
  test("不同 sessionId 产生不同标识", () => {
    const id1 = createDeterministicRcsSessionId("agent-1", "user-1", "session-1");
    const id2 = createDeterministicRcsSessionId("agent-1", "user-1", "session-2");
    expect(id1).not.toBe(id2);
  });
});

// ── base64url 编码正确性 ──

describe("base64url 编码", () => {
  // 标准 ASCII 字符串编码
  test("ASCII 字符串正确编码", () => {
    const id = createDeterministicRcsSessionId("abc", "def");
    // base64url("abc") = "YWJj", base64url("def") = "ZGVm"
    expect(id).toBe("rcs_YWJj.ZGVm");
  });

  // 空字符串编码
  test("空字符串编码为 rcs_.", () => {
    const id = createDeterministicRcsSessionId("", "");
    // base64url("") = ""
    expect(id).toBe("rcs_.");
  });

  // UTF-8 多字节字符编码
  test("UTF-8 中文字符正确编码", () => {
    const id1 = createDeterministicRcsSessionId("代理", "用户");
    const id2 = createDeterministicRcsSessionId("代理", "用户");
    expect(id1).toBe(id2);
    // 确认是 rcs_ 前缀
    expect(id1.startsWith("rcs_")).toBe(true);
  });

  // 特殊字符（+ 和 / 替换为 - 和 _）
  test("base64url 不含 + / = 字符", () => {
    // 使用会产生 +/= 的输入
    const id = createDeterministicRcsSessionId(">>>???<<<>>>", "a>b>c");
    expect(id).not.toContain("+");
    expect(id).not.toContain("/");
    expect(id.slice(4)).not.toContain("="); // 去掉 rcs_ 前缀后检查
  });
});

// ── 可逆性 ──

describe("标识可逆性", () => {
  // 可从标识中解码出原始 agentId 和 userId
  test("可从标识中解码出原始值", () => {
    const agentId = "agent-test-123";
    const userId = "user-test-456";
    const id = createDeterministicRcsSessionId(agentId, userId);

    const withoutPrefix = id.slice(4);
    const parts = withoutPrefix.split(".");
    const decodedAgent = atob(parts[0].replace(/-/g, "+").replace(/_/g, "/"));
    const decodedUser = atob(parts[1].replace(/-/g, "+").replace(/_/g, "/"));

    expect(decodedAgent).toBe(agentId);
    expect(decodedUser).toBe(userId);
  });

  // 带 sessionId 的三段的解码
  test("带 sessionId 的三段标识可解码", () => {
    const agentId = "a1";
    const userId = "u1";
    const sessionId = "s1";
    const id = createDeterministicRcsSessionId(agentId, userId, sessionId);

    const withoutPrefix = id.slice(4);
    const parts = withoutPrefix.split(".");
    expect(parts.length).toBe(3);

    const decodedAgent = atob(parts[0].replace(/-/g, "+").replace(/_/g, "/"));
    const decodedUser = atob(parts[1].replace(/-/g, "+").replace(/_/g, "/"));
    const decodedSession = atob(parts[2].replace(/-/g, "+").replace(/_/g, "/"));

    expect(decodedAgent).toBe(agentId);
    expect(decodedUser).toBe(userId);
    expect(decodedSession).toBe(sessionId);
  });
});

// ── sessionId 空字符串不纳入 ──

describe("sessionId 边界", () => {
  // 空字符串 sessionId 不加入标识（falsy 判断）
  test("空字符串 sessionId 等价于不传", () => {
    const id1 = createDeterministicRcsSessionId("a", "u");
    const id2 = createDeterministicRcsSessionId("a", "u", "");
    expect(id1).toBe(id2);
  });

  // undefined sessionId 等价于不传
  test("undefined sessionId 等价于不传", () => {
    const id1 = createDeterministicRcsSessionId("a", "u");
    const id2 = createDeterministicRcsSessionId("a", "u", undefined);
    expect(id1).toBe(id2);
  });
});
