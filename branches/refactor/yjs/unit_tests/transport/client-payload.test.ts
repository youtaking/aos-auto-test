import { describe, expect, test } from "bun:test";

// toClientPayload 纯函数复制（原函数位于 transport/client-payload.ts）

interface SessionEvent {
  id: string;
  sessionId: string;
  type: string;
  payload: unknown;
  direction: "inbound" | "outbound";
  seqNum: number;
  createdAt: number;
}

function toClientPayload(event: SessionEvent): Record<string, unknown> {
  const payload = event.payload as Record<string, unknown> | null;
  const messageUuid = typeof payload?.uuid === "string" && payload.uuid ? payload.uuid : event.id;

  if (event.type === "user" || event.type === "user_message") {
    return {
      type: "user",
      uuid: messageUuid,
      session_id: event.sessionId,
      ...(payload?.isSynthetic === true ? { isSynthetic: true } : {}),
      message: {
        role: "user",
        content: payload?.content ?? payload?.message ?? "",
      },
    };
  }

  if (event.type === "permission_response" || event.type === "control_response") {
    const approved = payload?.approved === true;
    const existingResponse = payload?.response;
    if (existingResponse) {
      return { type: "control_response", response: existingResponse };
    }
    return {
      type: "control_response",
      response: approved
        ? {
            subtype: "success",
            request_id: payload?.request_id,
            response: {
              behavior: "allow",
              ...(payload?.updated_input ? { updatedInput: payload.updated_input } : {}),
              ...(payload?.updated_permissions ? { updatedPermissions: payload.updated_permissions } : {}),
            },
          }
        : {
            subtype: "error",
            request_id: payload?.request_id,
            error: "Permission denied by user",
            ...(payload?.message ? { message: payload.message } : {}),
            response: { behavior: "deny" },
          },
    };
  }

  if (event.type === "interrupt") {
    return {
      type: "control_request",
      request_id: event.id,
      request: { subtype: "interrupt" },
    };
  }

  if (event.type === "control_request") {
    return {
      type: "control_request",
      request_id: (payload?.request_id as string) ?? event.id,
      request: (payload?.request as Record<string, unknown>) ?? payload ?? {},
    };
  }

  return {
    type: event.type,
    uuid: messageUuid,
    session_id: event.sessionId,
    message: payload ?? {},
  };
}

function makeEvent(overrides: Partial<SessionEvent> & Pick<SessionEvent, "type" | "sessionId">): SessionEvent {
  return {
    id: "evt-1",
    payload: null,
    direction: "inbound",
    seqNum: 1,
    createdAt: Date.now(),
    ...overrides,
  };
}

// ── user / user_message ──

describe("toClientPayload — user message", () => {
  test("maps user type with content", () => {
    const event = makeEvent({ type: "user", sessionId: "sess-1", payload: { content: "hello" } });
    const result = toClientPayload(event);
    expect(result.type).toBe("user");
    expect(result.session_id).toBe("sess-1");
    expect((result as any).message.role).toBe("user");
    expect((result as any).message.content).toBe("hello");
  });

  test("maps user_message type same as user", () => {
    const event = makeEvent({ type: "user_message", sessionId: "sess-2", payload: { content: "world" } });
    const result = toClientPayload(event);
    expect(result.type).toBe("user");
    expect(result.session_id).toBe("sess-2");
  });

  test("falls back to message field when content is missing", () => {
    const event = makeEvent({ type: "user", sessionId: "sess-3", payload: { message: "fallback msg" } });
    const result = toClientPayload(event);
    expect((result as any).message.content).toBe("fallback msg");
  });

  test("falls back to empty string when both content and message missing", () => {
    const event = makeEvent({ type: "user", sessionId: "sess-4", payload: {} });
    const result = toClientPayload(event);
    expect((result as any).message.content).toBe("");
  });

  test("includes isSynthetic when true", () => {
    const event = makeEvent({ type: "user", sessionId: "sess-5", payload: { content: "auto", isSynthetic: true } });
    expect((toClientPayload(event) as any).isSynthetic).toBe(true);
  });

  test("does not include isSynthetic when false", () => {
    const event = makeEvent({ type: "user", sessionId: "sess-6", payload: { content: "manual", isSynthetic: false } });
    expect((toClientPayload(event) as any).isSynthetic).toBeUndefined();
  });

  test("uses payload.uuid when present", () => {
    const event = makeEvent({ type: "user", sessionId: "sess-7", payload: { content: "hi", uuid: "custom-uuid" } });
    expect(toClientPayload(event).uuid).toBe("custom-uuid");
  });

  test("falls back to event.id when payload.uuid is missing", () => {
    const event = makeEvent({ type: "user", sessionId: "sess-8", payload: { content: "hi" } });
    expect(toClientPayload(event).uuid).toBe("evt-1");
  });
});

// ── permission_response / control_response ──

describe("toClientPayload — permission response", () => {
  test("approved=true maps to allow behavior", () => {
    const event = makeEvent({ type: "permission_response", sessionId: "sess-1", payload: { approved: true, request_id: "req-1" } });
    const result = toClientPayload(event);
    expect(result.type).toBe("control_response");
    const resp = (result as any).response;
    expect(resp.subtype).toBe("success");
    expect(resp.request_id).toBe("req-1");
    expect(resp.response.behavior).toBe("allow");
  });

  test("approved=false maps to deny behavior with error", () => {
    const event = makeEvent({ type: "permission_response", sessionId: "sess-2", payload: { approved: false, request_id: "req-2" } });
    const result = toClientPayload(event);
    expect(result.type).toBe("control_response");
    const resp = (result as any).response;
    expect(resp.subtype).toBe("error");
    expect(resp.error).toBe("Permission denied by user");
    expect(resp.response.behavior).toBe("deny");
  });

  test("approved=false includes feedback message when provided", () => {
    const event = makeEvent({ type: "permission_response", sessionId: "sess-3", payload: { approved: false, request_id: "req-3", message: "please revise" } });
    const result = toClientPayload(event);
    expect((result as any).response.message).toBe("please revise");
  });

  test("passes through existing response directly", () => {
    const existingResponse = { subtype: "success", custom: true };
    const event = makeEvent({ type: "control_response", sessionId: "sess-4", payload: { approved: true, response: existingResponse } });
    const result = toClientPayload(event);
    expect(result.type).toBe("control_response");
    expect((result as any).response).toBe(existingResponse);
  });

  test("includes updatedInput when approved with updated_input", () => {
    const updatedInput = { file_path: "/new/path" };
    const event = makeEvent({ type: "permission_response", sessionId: "sess-5", payload: { approved: true, request_id: "req-5", updated_input: updatedInput } });
    const result = toClientPayload(event);
    expect((result as any).response.response.updatedInput).toEqual(updatedInput);
  });

  test("includes updatedPermissions when approved with updated_permissions", () => {
    const perms = [{ type: "allow", tool: "bash" }];
    const event = makeEvent({ type: "permission_response", sessionId: "sess-6", payload: { approved: true, request_id: "req-6", updated_permissions: perms } });
    const result = toClientPayload(event);
    expect((result as any).response.response.updatedPermissions).toEqual(perms);
  });
});

// ── interrupt ──

describe("toClientPayload — interrupt", () => {
  test("maps interrupt to control_request with subtype interrupt", () => {
    const event = makeEvent({ type: "interrupt", sessionId: "sess-1" });
    const result = toClientPayload(event);
    expect(result.type).toBe("control_request");
    expect((result as any).request_id).toBe("evt-1");
    expect((result as any).request.subtype).toBe("interrupt");
  });
});

// ── control_request ──

describe("toClientPayload — control_request", () => {
  test("passes through request_id and request from payload", () => {
    const event = makeEvent({ type: "control_request", sessionId: "sess-1", payload: { request_id: "req-99", request: { subtype: "permission", tool: "bash" } } });
    const result = toClientPayload(event);
    expect(result.type).toBe("control_request");
    expect((result as any).request_id).toBe("req-99");
    expect((result as any).request.subtype).toBe("permission");
  });

  test("falls back request to payload when no request field", () => {
    const event = makeEvent({ type: "control_request", sessionId: "sess-2", payload: { request_id: "req-10", custom: "data" } });
    const result = toClientPayload(event);
    expect((result as any).request).toEqual({ request_id: "req-10", custom: "data" });
  });

  test("falls back request_id to event.id when missing", () => {
    const event = makeEvent({ type: "control_request", sessionId: "sess-3", payload: { request: { subtype: "test" } } });
    const result = toClientPayload(event);
    expect((result as any).request_id).toBe("evt-1");
  });
});

// ── default types ──

describe("toClientPayload — default types", () => {
  test("passes through unknown type with type/uuid/session_id/message", () => {
    const event = makeEvent({ type: "assistant", sessionId: "sess-1", payload: { uuid: "u-1", content: "response text" } });
    const result = toClientPayload(event);
    expect(result.type).toBe("assistant");
    expect(result.uuid).toBe("u-1");
    expect(result.session_id).toBe("sess-1");
    expect(result.message).toEqual({ uuid: "u-1", content: "response text" });
  });
});
