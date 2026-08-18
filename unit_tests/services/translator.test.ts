// translator.test.ts — Chat 域 action → ACP JSON-RPC 翻译测试
// 测试目标：translateSimpleAction 纯函数覆盖所有 action 分支
// 业务意图：确保前端简化操作正确翻译为标准 ACP JSON-RPC 请求

import { describe, expect, test } from "bun:test";

// ── 复制源函数（纯函数，无外部依赖）──

function translateSimpleAction(
  parsed: Record<string, unknown>,
  workspacePath: string | null | undefined,
  rpcId: number,
): Record<string, unknown> {
  const action = parsed.action as string;
  const id = rpcId;
  switch (action) {
    case "send_prompt":
      // 携带目标 sessionId（服务端 session-channel 注入，来自绑定的 acpSessionId）：
      // dispatcher 据此精确路由 prompt；旧客户端不带时字段缺失，dispatcher fallback
      // 到连接级当前会话（向后兼容，但多会话共享 relay 时可能串会话——见 session-channel）。
      return {
        jsonrpc: "2.0",
        id,
        method: "session/prompt",
        params: { content: parsed.content, sessionId: parsed.sessionId },
      };
    case "cancel":
      return { jsonrpc: "2.0", id, method: "session/cancel", params: { sessionId: parsed.sessionId } };
    case "create_session":
      return { jsonrpc: "2.0", id, method: "session/new", params: { cwd: workspacePath } };
    case "load_session":
      return {
        jsonrpc: "2.0", id, method: "session/load",
        params: { sessionId: parsed.sessionId, cwd: workspacePath },
      };
    case "resume_session":
      return {
        jsonrpc: "2.0", id, method: "session/resume",
        params: { sessionId: parsed.sessionId, cwd: workspacePath },
      };
    case "list_sessions":
      return { jsonrpc: "2.0", id, method: "session/list", params: { cwd: workspacePath } };
    case "rename_session":
      return {
        jsonrpc: "2.0", id, method: "session/rename",
        params: { sessionId: parsed.sessionId, title: parsed.title },
      };
    case "delete_session":
      return { jsonrpc: "2.0", id, method: "session/delete", params: { sessionId: parsed.sessionId } };
    case "respond_permission":
      return {
        jsonrpc: "2.0",
        id: typeof parsed.requestId === "string" ? parsed.requestId : "",
        result: {
          outcome:
            typeof parsed.optionId === "string" && parsed.optionId.length > 0
              ? { outcome: "selected", optionId: parsed.optionId }
              : { outcome: "cancelled" },
        },
      };
    case "respond_question": // AskUserQuestion 答案必须以 control_response 传输帧回传（非 JSON-RPC！）：
      // acp-link dispatcher 的 handleTransportMessage 只消费 { type: "control_response",
      // request_id, approved, extra } 形态（acp-dispatcher.ts:194）。
      // 多问题（requestedSchema.properties 多个）合并回传 extra.answers 数组
      // （answers[i] = 第 i 个问题的选中 label，按 propertyKeys 顺序对应）；
      // 单问题兼容 extra.outcome.optionId（历史形态，新前端统一走 answers）。
      {
        const optionIds = Array.isArray(parsed.optionIds)
          ? (parsed.optionIds as unknown[]).filter((v): v is string => typeof v === "string" && v.length > 0)
          : typeof parsed.optionId === "string" && parsed.optionId.length > 0
            ? [parsed.optionId]
            : [];
        return {
          type: "control_response",
          request_id: typeof parsed.questionId === "string" ? parsed.questionId : "",
          approved: optionIds.length > 0,
          extra:
            optionIds.length > 0
              ? { answers: optionIds }
              : { outcome: { optionId: typeof parsed.optionId === "string" ? parsed.optionId : "" } },
        };
      }
    case "set_session_mode":
      return {
        jsonrpc: "2.0", id, method: "session/setMode",
        params: { modeId: parsed.modeId },
      };
    default:
      return parsed;
  }
}

// ── send_prompt ──

describe("send_prompt", () => {
  // 标准 prompt 翻译，携带 sessionId
  test("翻译为 session/prompt 并携带 content 和 sessionId", () => {
    const result = translateSimpleAction(
      { action: "send_prompt", content: "hello agent", sessionId: "ses_abc" },
      "/workspace/org1/user1/env1",
      42,
    );
    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 42,
      method: "session/prompt",
      params: { content: "hello agent", sessionId: "ses_abc" },
    });
  });

  // rpcId 正确传递
  test("rpcId 作为 JSON-RPC id", () => {
    const result = translateSimpleAction(
      { action: "send_prompt", content: "test" },
      null,
      99,
    );
    expect(result.id).toBe(99);
  });

  // sessionId 缺失时 params.sessionId 为 undefined
  test("sessionId 缺失时 params.sessionId 为 undefined", () => {
    const result = translateSimpleAction(
      { action: "send_prompt", content: "test" },
      null,
      10,
    );
    expect(result.method).toBe("session/prompt");
    expect((result.params as Record<string, unknown>).sessionId).toBeUndefined();
  });
});

// ── cancel ──

describe("cancel", () => {
  // cancel 翻译为 session/cancel
  test("翻译为 session/cancel 并携带 sessionId", () => {
    const result = translateSimpleAction(
      { action: "cancel", sessionId: "ses_abc123" },
      null,
      10,
    );
    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 10,
      method: "session/cancel",
      params: { sessionId: "ses_abc123" },
    });
  });

  // sessionId 缺失时 params 中为 undefined
  test("sessionId 缺失时 params.sessionId 为 undefined", () => {
    const result = translateSimpleAction(
      { action: "cancel" },
      null,
      11,
    );
    expect(result.method).toBe("session/cancel");
    expect((result.params as Record<string, unknown>).sessionId).toBeUndefined();
  });
});

// ── create_session ──

describe("create_session", () => {
  // 创建会话翻译为 session/new
  test("翻译为 session/new 并注入 workspacePath 作为 cwd", () => {
    const result = translateSimpleAction(
      { action: "create_session" },
      "/workspace/org1/user1/env1",
      1,
    );
    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 1,
      method: "session/new",
      params: { cwd: "/workspace/org1/user1/env1" },
    });
  });

  // workspacePath 为 null 时 cwd 为 null
  test("workspacePath 为 null 时 cwd 为 null", () => {
    const result = translateSimpleAction(
      { action: "create_session" },
      null,
      2,
    );
    expect((result.params as Record<string, unknown>).cwd).toBeNull();
  });

  // workspacePath 为 undefined 时 cwd 为 undefined
  test("workspacePath 为 undefined 时 cwd 为 undefined", () => {
    const result = translateSimpleAction(
      { action: "create_session" },
      undefined,
      3,
    );
    expect((result.params as Record<string, unknown>).cwd).toBeUndefined();
  });
});

// ── load_session ──

describe("load_session", () => {
  // 加载会话翻译为 session/load
  test("翻译为 session/load 并携带 sessionId 和 cwd", () => {
    const result = translateSimpleAction(
      { action: "load_session", sessionId: "ses_xyz" },
      "/ws/org/user/env",
      5,
    );
    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 5,
      method: "session/load",
      params: { sessionId: "ses_xyz", cwd: "/ws/org/user/env" },
    });
  });
});

// ── resume_session ──

describe("resume_session", () => {
  // 恢复会话翻译为 session/resume
  test("翻译为 session/resume 并携带 sessionId 和 cwd", () => {
    const result = translateSimpleAction(
      { action: "resume_session", sessionId: "ses_resume" },
      "/ws/org/user/env",
      6,
    );
    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 6,
      method: "session/resume",
      params: { sessionId: "ses_resume", cwd: "/ws/org/user/env" },
    });
  });
});

// ── list_sessions ──

describe("list_sessions", () => {
  // 列出会话翻译为 session/list
  test("翻译为 session/list 并携带 cwd", () => {
    const result = translateSimpleAction(
      { action: "list_sessions" },
      "/ws/org/user/env",
      7,
    );
    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 7,
      method: "session/list",
      params: { cwd: "/ws/org/user/env" },
    });
  });
});

// ── rename_session ──

describe("rename_session", () => {
  // 重命名会话翻译为 session/rename
  test("翻译为 session/rename 并携带 sessionId 和 title", () => {
    const result = translateSimpleAction(
      { action: "rename_session", sessionId: "ses_rename", title: "新标题" },
      null,
      8,
    );
    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 8,
      method: "session/rename",
      params: { sessionId: "ses_rename", title: "新标题" },
    });
  });
});

// ── delete_session ──

describe("delete_session", () => {
  // 删除会话翻译为 session/delete
  test("翻译为 session/delete 并携带 sessionId", () => {
    const result = translateSimpleAction(
      { action: "delete_session", sessionId: "ses_del" },
      null,
      9,
    );
    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 9,
      method: "session/delete",
      params: { sessionId: "ses_del" },
    });
  });
});

// ── respond_permission ──

describe("respond_permission", () => {
  // 权限响应使用 result 而非 method（JSON-RPC 响应形态）
  test("允许权限：optionId 非空时 outcome 为 selected", () => {
    const result = translateSimpleAction(
      { action: "respond_permission", requestId: "perm_123", optionId: "allow_once" },
      null,
      0,
    );
    expect(result.jsonrpc).toBe("2.0");
    // 权限响应使用 requestId 作为 id，不使用 rpcId
    expect(result.id).toBe("perm_123");
    expect(result.result).toEqual({
      outcome: { outcome: "selected", optionId: "allow_once" },
    });
  });

  // optionId 为空字符串时 outcome 为 cancelled
  test("optionId 为空字符串时 outcome 为 cancelled", () => {
    const result = translateSimpleAction(
      { action: "respond_permission", requestId: "perm_456", optionId: "" },
      null,
      0,
    );
    expect(result.result).toEqual({
      outcome: { outcome: "cancelled" },
    });
  });

  // optionId 缺失时 outcome 为 cancelled
  test("optionId 缺失时 outcome 为 cancelled", () => {
    const result = translateSimpleAction(
      { action: "respond_permission", requestId: "perm_789" },
      null,
      0,
    );
    expect(result.result).toEqual({
      outcome: { outcome: "cancelled" },
    });
  });

  // requestId 非字符串时 id 回退为空字符串
  test("requestId 缺失时 id 回退为空字符串", () => {
    const result = translateSimpleAction(
      { action: "respond_permission", optionId: "allow" },
      null,
      0,
    );
    expect(result.id).toBe("");
  });
});

// ── set_session_mode ──

describe("set_session_mode", () => {
  // 切换模式翻译为 session/setMode
  test("翻译为 session/setMode 并携带 modeId", () => {
    const result = translateSimpleAction(
      { action: "set_session_mode", modeId: "plan" },
      null,
      20,
    );
    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 20,
      method: "session/setMode",
      params: { modeId: "plan" },
    });
  });
});

// ── respond_question ──

describe("respond_question", () => {
  // 多选项答案以 control_response 帧回传，extra.answers 为数组
  test("多选项：optionIds 非空时 approved=true，extra.answers 为选项数组", () => {
    const result = translateSimpleAction(
      { action: "respond_question", questionId: "q_123", optionIds: ["opt_a", "opt_b"] },
      null,
      0,
    );
    expect(result).toEqual({
      type: "control_response",
      request_id: "q_123",
      approved: true,
      extra: { answers: ["opt_a", "opt_b"] },
    });
  });

  // 单选项回退：optionId 非空时包装为单元素数组
  test("单选项回退：optionId 非空时 approved=true，extra.answers 为单元素数组", () => {
    const result = translateSimpleAction(
      { action: "respond_question", questionId: "q_456", optionId: "opt_x" },
      null,
      0,
    );
    expect(result).toEqual({
      type: "control_response",
      request_id: "q_456",
      approved: true,
      extra: { answers: ["opt_x"] },
    });
  });

  // optionIds 和 optionId 都缺失时 approved=false，extra 包含空 optionId
  test("无选项：approved=false，extra.outcome.optionId 为空字符串", () => {
    const result = translateSimpleAction(
      { action: "respond_question", questionId: "q_789" },
      null,
      0,
    );
    expect(result).toEqual({
      type: "control_response",
      request_id: "q_789",
      approved: false,
      extra: { outcome: { optionId: "" } },
    });
  });

  // questionId 非字符串时 request_id 回退为空字符串
  test("questionId 缺失时 request_id 回退为空字符串", () => {
    const result = translateSimpleAction(
      { action: "respond_question", optionIds: ["opt_a"] },
      null,
      0,
    );
    expect(result.request_id).toBe("");
  });

  // optionIds 中的空字符串被过滤
  test("optionIds 中的空字符串被过滤", () => {
    const result = translateSimpleAction(
      { action: "respond_question", questionId: "q_filter", optionIds: ["opt_a", "", "opt_b"] },
      null,
      0,
    );
    expect(result.extra).toEqual({ answers: ["opt_a", "opt_b"] });
  });

  // optionIds 全为空字符串时回退到 extra.outcome
  test("optionIds 全为空字符串时 approved=false", () => {
    const result = translateSimpleAction(
      { action: "respond_question", questionId: "q_empty", optionIds: ["", ""] },
      null,
      0,
    );
    expect(result.approved).toBe(false);
    expect(result.extra).toEqual({ outcome: { optionId: "" } });
  });
});

// ── default（未知 action）──

describe("default（未知 action）", () => {
  // 未知 action 原样返回
  test("未知 action 原样返回 parsed 对象", () => {
    const input = { action: "unknown_action", foo: "bar" };
    const result = translateSimpleAction(input, null, 100);
    expect(result).toBe(input);
  });

  // 无 action 字段时原样返回
  test("无 action 字段时原样返回", () => {
    const input = { foo: "bar" };
    const result = translateSimpleAction(input, null, 101);
    expect(result).toBe(input);
  });
});
