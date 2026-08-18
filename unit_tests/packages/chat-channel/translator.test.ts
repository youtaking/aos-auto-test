import { describe, test, expect } from "bun:test";

// ========== Pure function copies from packages/chat-channel/src/protocol/translator.ts ==========

function translateSimpleAction(
  parsed: Record<string, unknown>,
  workspacePath: string | null | undefined,
  rpcId: number,
): Record<string, unknown> {
  const action = parsed.action as string;
  const id = rpcId;
  switch (action) {
    case "send_prompt":
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
        jsonrpc: "2.0",
        id,
        method: "session/load",
        params: { sessionId: parsed.sessionId, cwd: workspacePath },
      };
    case "resume_session":
      return {
        jsonrpc: "2.0",
        id,
        method: "session/resume",
        params: { sessionId: parsed.sessionId, cwd: workspacePath },
      };
    case "list_sessions":
      return { jsonrpc: "2.0", id, method: "session/list", params: { cwd: workspacePath } };
    case "rename_session":
      return {
        jsonrpc: "2.0",
        id,
        method: "session/rename",
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
    case "respond_question":
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
        jsonrpc: "2.0",
        id,
        method: "session/setMode",
        params: { modeId: parsed.modeId },
      };
    default:
      return parsed;
  }
}

// ========== Tests ==========

describe("translateSimpleAction - send_prompt", () => {
  test("translates send_prompt action", () => {
    const result = translateSimpleAction(
      { action: "send_prompt", content: "Hello", sessionId: "sess-123" },
      "/workspace",
      1,
    );

    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 1,
      method: "session/prompt",
      params: { content: "Hello", sessionId: "sess-123" },
    });
  });

  test("handles missing sessionId in send_prompt", () => {
    const result = translateSimpleAction({ action: "send_prompt", content: "Test" }, null, 2);

    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 2,
      method: "session/prompt",
      params: { content: "Test", sessionId: undefined },
    });
  });
});

describe("translateSimpleAction - cancel", () => {
  test("translates cancel action", () => {
    const result = translateSimpleAction({ action: "cancel", sessionId: "sess-456" }, null, 3);

    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 3,
      method: "session/cancel",
      params: { sessionId: "sess-456" },
    });
  });
});

describe("translateSimpleAction - create_session", () => {
  test("translates create_session with workspace path", () => {
    const result = translateSimpleAction({ action: "create_session" }, "/home/user/project", 4);

    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 4,
      method: "session/new",
      params: { cwd: "/home/user/project" },
    });
  });

  test("handles null workspace path", () => {
    const result = translateSimpleAction({ action: "create_session" }, null, 5);

    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 5,
      method: "session/new",
      params: { cwd: null },
    });
  });
});

describe("translateSimpleAction - load_session", () => {
  test("translates load_session", () => {
    const result = translateSimpleAction(
      { action: "load_session", sessionId: "sess-789" },
      "/workspace",
      6,
    );

    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 6,
      method: "session/load",
      params: { sessionId: "sess-789", cwd: "/workspace" },
    });
  });
});

describe("translateSimpleAction - resume_session", () => {
  test("translates resume_session", () => {
    const result = translateSimpleAction(
      { action: "resume_session", sessionId: "sess-abc" },
      "/workspace",
      7,
    );

    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 7,
      method: "session/resume",
      params: { sessionId: "sess-abc", cwd: "/workspace" },
    });
  });
});

describe("translateSimpleAction - list_sessions", () => {
  test("translates list_sessions", () => {
    const result = translateSimpleAction({ action: "list_sessions" }, "/workspace", 8);

    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 8,
      method: "session/list",
      params: { cwd: "/workspace" },
    });
  });
});

describe("translateSimpleAction - rename_session", () => {
  test("translates rename_session", () => {
    const result = translateSimpleAction(
      { action: "rename_session", sessionId: "sess-xyz", title: "New Title" },
      null,
      9,
    );

    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 9,
      method: "session/rename",
      params: { sessionId: "sess-xyz", title: "New Title" },
    });
  });
});

describe("translateSimpleAction - delete_session", () => {
  test("translates delete_session", () => {
    const result = translateSimpleAction({ action: "delete_session", sessionId: "sess-del" }, null, 10);

    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 10,
      method: "session/delete",
      params: { sessionId: "sess-del" },
    });
  });
});

describe("translateSimpleAction - respond_permission", () => {
  test("translates respond_permission with optionId", () => {
    const result = translateSimpleAction(
      { action: "respond_permission", requestId: "perm-123", optionId: "allow_once" },
      null,
      11,
    );

    expect(result).toEqual({
      jsonrpc: "2.0",
      id: "perm-123",
      result: {
        outcome: { outcome: "selected", optionId: "allow_once" },
      },
    });
  });

  test("returns cancelled outcome when optionId is empty", () => {
    const result = translateSimpleAction(
      { action: "respond_permission", requestId: "perm-456", optionId: "" },
      null,
      12,
    );

    expect(result).toEqual({
      jsonrpc: "2.0",
      id: "perm-456",
      result: {
        outcome: { outcome: "cancelled" },
      },
    });
  });

  test("returns cancelled outcome when optionId is missing", () => {
    const result = translateSimpleAction(
      { action: "respond_permission", requestId: "perm-789" },
      null,
      13,
    );

    expect(result).toEqual({
      jsonrpc: "2.0",
      id: "perm-789",
      result: {
        outcome: { outcome: "cancelled" },
      },
    });
  });

  test("uses empty string when requestId is not a string", () => {
    const result = translateSimpleAction(
      { action: "respond_permission", requestId: 123, optionId: "allow" },
      null,
      14,
    );

    expect(result).toEqual({
      jsonrpc: "2.0",
      id: "",
      result: {
        outcome: { outcome: "selected", optionId: "allow" },
      },
    });
  });
});

describe("translateSimpleAction - respond_question", () => {
  test("translates respond_question with optionIds array", () => {
    const result = translateSimpleAction(
      { action: "respond_question", questionId: "q-123", optionIds: ["Option A", "Option B"] },
      null,
      15,
    );

    expect(result).toEqual({
      type: "control_response",
      request_id: "q-123",
      approved: true,
      extra: { answers: ["Option A", "Option B"] },
    });
  });

  test("falls back to single optionId when optionIds is not an array", () => {
    const result = translateSimpleAction(
      { action: "respond_question", questionId: "q-456", optionId: "Single Option" },
      null,
      16,
    );

    expect(result).toEqual({
      type: "control_response",
      request_id: "q-456",
      approved: true,
      extra: { answers: ["Single Option"] },
    });
  });

  test("returns not approved when no options provided", () => {
    const result = translateSimpleAction({ action: "respond_question", questionId: "q-789" }, null, 17);

    expect(result).toEqual({
      type: "control_response",
      request_id: "q-789",
      approved: false,
      extra: { outcome: { optionId: "" } },
    });
  });

  test("filters out empty strings from optionIds array", () => {
    const result = translateSimpleAction(
      { action: "respond_question", questionId: "q-abc", optionIds: ["Valid", "", "Also Valid"] },
      null,
      18,
    );

    expect(result).toEqual({
      type: "control_response",
      request_id: "q-abc",
      approved: true,
      extra: { answers: ["Valid", "Also Valid"] },
    });
  });

  test("uses empty string when questionId is not a string", () => {
    const result = translateSimpleAction(
      { action: "respond_question", questionId: 999, optionIds: ["A"] },
      null,
      19,
    );

    expect(result).toEqual({
      type: "control_response",
      request_id: "",
      approved: true,
      extra: { answers: ["A"] },
    });
  });

  test("respond_question optionIds 为空数组时 approved 为 false", () => {
    // 源码逻辑：Array.isArray([]) → true → filter 结果空数组 → approved = false
    // 不会 fallback 到 single optionId 分支
    const result = translateSimpleAction(
      { action: "respond_question", questionId: "q-empty", optionIds: [], optionId: "should-not-use" },
      null,
      50,
    );

    expect(result).toEqual({
      type: "control_response",
      request_id: "q-empty",
      approved: false,
      extra: { outcome: { optionId: "should-not-use" } },
    });
  });

  test("respond_question optionIds 含非 string 元素时被过滤", () => {
    // 源码逻辑：filter((v): v is string => typeof v === "string" && v.length > 0)
    // [123, null, "Valid"] → 123 和 null 被过滤，只保留 "Valid"
    const result = translateSimpleAction(
      { action: "respond_question", questionId: "q-mixed", optionIds: [123, null, "Valid"] },
      null,
      51,
    );

    expect(result).toEqual({
      type: "control_response",
      request_id: "q-mixed",
      approved: true,
      extra: { answers: ["Valid"] },
    });
  });
});

describe("translateSimpleAction - set_session_mode", () => {
  test("translates set_session_mode", () => {
    const result = translateSimpleAction({ action: "set_session_mode", modeId: "agent" }, null, 20);

    expect(result).toEqual({
      jsonrpc: "2.0",
      id: 20,
      method: "session/setMode",
      params: { modeId: "agent" },
    });
  });
});

describe("translateSimpleAction - default case", () => {
  test("returns parsed object unchanged for unknown action", () => {
    const parsed = { action: "unknown_action", foo: "bar" };
    const result = translateSimpleAction(parsed, "/workspace", 21);

    expect(result).toEqual(parsed);
  });

  test("returns parsed object when action is missing", () => {
    const parsed = { foo: "bar" };
    const result = translateSimpleAction(parsed, null, 22);

    expect(result).toEqual(parsed);
  });
});

describe("translateSimpleAction - rpcId handling", () => {
  test("uses provided rpcId", () => {
    const result1 = translateSimpleAction({ action: "list_sessions" }, null, 100);
    const result2 = translateSimpleAction({ action: "list_sessions" }, null, 200);

    expect(result1.id).toBe(100);
    expect(result2.id).toBe(200);
  });

  test("handles zero rpcId", () => {
    const result = translateSimpleAction({ action: "list_sessions" }, null, 0);
    expect(result.id).toBe(0);
  });

  test("handles negative rpcId", () => {
    const result = translateSimpleAction({ action: "list_sessions" }, null, -1);
    expect(result.id).toBe(-1);
  });
});
