import { describe, test, expect } from "bun:test";

// --- Pure functions/types copied from source ---

interface RelayEvent { type: string; payload?: unknown; }
interface SessionUpdateEvent {
  sessionUpdate: string;
  messageId?: string;
  content?: { type: string; text: string };
  toolCallId?: string;
  title?: string;
  kind?: string;
  status?: string;
  entries?: Array<{ content: string; priority?: string; status?: string }>;
  used?: number;
  size?: number;
}

function extractJsonRpc(ev: RelayEvent): Record<string, unknown> | null {
  if ((ev as unknown as Record<string, unknown>).jsonrpc === "2.0") return ev as unknown as Record<string, unknown>;
  const payload = ev.payload as Record<string, unknown> | undefined;
  if (payload?.jsonrpc === "2.0") return payload;
  return null;
}

type ChunkKind = "reasoning" | "content";
function classifyUpdate(update: SessionUpdateEvent): ChunkKind {
  switch (update.sessionUpdate) {
    case "agent_thought_chunk":
    case "plan":
      return "reasoning";
    case "agent_message_chunk":
    case "tool_call":
    case "tool_call_update":
      return "content";
    default:
      return "reasoning";
  }
}

function formatUpdateText(update: SessionUpdateEvent): string {
  switch (update.sessionUpdate) {
    case "agent_thought_chunk":
    case "agent_message_chunk":
      return update.content?.text ?? "";
    case "tool_call":
      return `<tool_call name="${update.title ?? "unknown"}" />\n`;
    case "tool_call_update":
      return `<tool_result name="${update.title ?? "unknown"}" />\n`;
    case "plan":
      return `${(update.entries ?? []).map((e) => `- [${e.status ?? "pending"}] ${e.content}`).join("\n")}\n`;
    default:
      return "";
  }
}

function buildOpenAIError(status: number, message: string, type: string) {
  return {
    status,
    body: {
      error: { message, type, code: status === 401 ? "invalid_api_key" : undefined },
    },
  };
}

// --- Tests ---

describe("extractJsonRpc", () => {
  test("extracts from direct JSON-RPC event", () => {
    const ev = { type: "rpc", jsonrpc: "2.0", method: "test" } as unknown as RelayEvent;
    const result = extractJsonRpc(ev);
    expect(result).not.toBeNull();
    expect(result!["jsonrpc"]).toBe("2.0");
    expect(result!["method"]).toBe("test");
  });

  test("extracts from nested payload", () => {
    const ev: RelayEvent = {
      type: "message",
      payload: { jsonrpc: "2.0", method: "nested_call", id: 1 },
    };
    const result = extractJsonRpc(ev);
    expect(result).not.toBeNull();
    expect(result!["jsonrpc"]).toBe("2.0");
    expect(result!["method"]).toBe("nested_call");
  });

  test("returns null for non-JSON-RPC event", () => {
    const ev: RelayEvent = { type: "message", payload: { data: "hello" } };
    expect(extractJsonRpc(ev)).toBeNull();
  });

  test("returns null for event without payload and without jsonrpc", () => {
    const ev: RelayEvent = { type: "ping" };
    expect(extractJsonRpc(ev)).toBeNull();
  });

  test("returns null when payload has jsonrpc but not 2.0", () => {
    const ev: RelayEvent = { type: "rpc", payload: { jsonrpc: "1.0" } };
    expect(extractJsonRpc(ev)).toBeNull();
  });
});

describe("classifyUpdate", () => {
  test("agent_thought_chunk is reasoning", () => {
    expect(classifyUpdate({ sessionUpdate: "agent_thought_chunk" })).toBe("reasoning");
  });

  test("plan is reasoning", () => {
    expect(classifyUpdate({ sessionUpdate: "plan" })).toBe("reasoning");
  });

  test("agent_message_chunk is content", () => {
    expect(classifyUpdate({ sessionUpdate: "agent_message_chunk" })).toBe("content");
  });

  test("tool_call is content", () => {
    expect(classifyUpdate({ sessionUpdate: "tool_call" })).toBe("content");
  });

  test("tool_call_update is content", () => {
    expect(classifyUpdate({ sessionUpdate: "tool_call_update" })).toBe("content");
  });

  test("unknown type defaults to reasoning", () => {
    expect(classifyUpdate({ sessionUpdate: "some_new_type" })).toBe("reasoning");
  });

  test("empty string defaults to reasoning", () => {
    expect(classifyUpdate({ sessionUpdate: "" })).toBe("reasoning");
  });
});

describe("formatUpdateText", () => {
  test("agent_thought_chunk returns content text", () => {
    const update: SessionUpdateEvent = {
      sessionUpdate: "agent_thought_chunk",
      content: { type: "text", text: "thinking..." },
    };
    expect(formatUpdateText(update)).toBe("thinking...");
  });

  test("agent_message_chunk returns content text", () => {
    const update: SessionUpdateEvent = {
      sessionUpdate: "agent_message_chunk",
      content: { type: "text", text: "Hello world" },
    };
    expect(formatUpdateText(update)).toBe("Hello world");
  });

  test("agent_thought_chunk without content returns empty string", () => {
    const update: SessionUpdateEvent = { sessionUpdate: "agent_thought_chunk" };
    expect(formatUpdateText(update)).toBe("");
  });

  test("tool_call returns formatted tool call tag", () => {
    const update: SessionUpdateEvent = {
      sessionUpdate: "tool_call",
      title: "search_web",
    };
    expect(formatUpdateText(update)).toBe('<tool_call name="search_web" />\n');
  });

  test("tool_call without title uses unknown", () => {
    const update: SessionUpdateEvent = { sessionUpdate: "tool_call" };
    expect(formatUpdateText(update)).toBe('<tool_call name="unknown" />\n');
  });

  test("tool_call_update returns formatted tool result tag", () => {
    const update: SessionUpdateEvent = {
      sessionUpdate: "tool_call_update",
      title: "search_web",
    };
    expect(formatUpdateText(update)).toBe('<tool_result name="search_web" />\n');
  });

  test("tool_call_update without title uses unknown", () => {
    const update: SessionUpdateEvent = { sessionUpdate: "tool_call_update" };
    expect(formatUpdateText(update)).toBe('<tool_result name="unknown" />\n');
  });

  test("plan returns formatted entries", () => {
    const update: SessionUpdateEvent = {
      sessionUpdate: "plan",
      entries: [
        { content: "Step 1", status: "done" },
        { content: "Step 2", status: "in_progress" },
        { content: "Step 3" },
      ],
    };
    const result = formatUpdateText(update);
    expect(result).toBe("- [done] Step 1\n- [in_progress] Step 2\n- [pending] Step 3\n");
  });

  test("plan with empty entries returns just newline", () => {
    const update: SessionUpdateEvent = {
      sessionUpdate: "plan",
      entries: [],
    };
    expect(formatUpdateText(update)).toBe("\n");
  });

  test("plan without entries returns just newline", () => {
    const update: SessionUpdateEvent = { sessionUpdate: "plan" };
    expect(formatUpdateText(update)).toBe("\n");
  });

  test("unknown sessionUpdate returns empty string", () => {
    const update: SessionUpdateEvent = { sessionUpdate: "unknown_type" };
    expect(formatUpdateText(update)).toBe("");
  });
});

describe("buildOpenAIError", () => {
  test("401 error includes invalid_api_key code", () => {
    const err = buildOpenAIError(401, "Invalid API key provided", "authentication_error");
    expect(err.status).toBe(401);
    expect(err.body.error.message).toBe("Invalid API key provided");
    expect(err.body.error.type).toBe("authentication_error");
    expect(err.body.error.code).toBe("invalid_api_key");
  });

  test("500 error has undefined code", () => {
    const err = buildOpenAIError(500, "Internal server error", "server_error");
    expect(err.status).toBe(500);
    expect(err.body.error.message).toBe("Internal server error");
    expect(err.body.error.type).toBe("server_error");
    expect(err.body.error.code).toBeUndefined();
  });

  test("400 error has undefined code", () => {
    const err = buildOpenAIError(400, "Bad request", "invalid_request_error");
    expect(err.status).toBe(400);
    expect(err.body.error.code).toBeUndefined();
  });

  test("403 error has undefined code", () => {
    const err = buildOpenAIError(403, "Forbidden", "permission_error");
    expect(err.status).toBe(403);
    expect(err.body.error.code).toBeUndefined();
  });

  test("error body structure is correct", () => {
    const err = buildOpenAIError(429, "Rate limited", "rate_limit_error");
    expect(err).toEqual({
      status: 429,
      body: {
        error: {
          message: "Rate limited",
          type: "rate_limit_error",
          code: undefined,
        },
      },
    });
  });
});
