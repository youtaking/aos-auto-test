import { describe, test, expect } from "bun:test";

// --- Pure functions/types copied from source ---
// 源：packages/agent-runtime/src/services/openai-response-mapper.ts（main a7f477a9e）
// 依赖：extractJsonRpc / classifyAgentTurnEvent / iterateWithSignal 以内联替身提供

interface RelayEvent { type: string; payload?: unknown; }

function extractJsonRpc(ev: RelayEvent): Record<string, unknown> | null {
  if ((ev as unknown as Record<string, unknown>).jsonrpc === "2.0") return ev as unknown as Record<string, unknown>;
  const payload = ev.payload as Record<string, unknown> | undefined;
  if (payload?.jsonrpc === "2.0") return payload;
  return null;
}

interface AgentTurnTerminal { outcome: string; stopReason?: string; }

function classifyAgentTurnEvent(event: unknown): AgentTurnTerminal | null {
  if (!event || typeof event !== "object") return null;
  const message = event as Record<string, unknown>;
  if (message.type === "relay_closed") return { outcome: "disconnected" };
  if (message.type === "error") return { outcome: "failed" };
  const rpc = extractJsonRpc(event as RelayEvent);
  if (!rpc) return null;
  if (rpc.error) return { outcome: "failed" };
  const result = rpc.result as Record<string, unknown> | undefined;
  if (!result || typeof result !== "object") return null;
  if (result.error) return { outcome: "failed" };
  const stopReason = result.stopReason;
  if (typeof stopReason !== "string") return "id" in rpc ? { outcome: "unknown" } : null;
  if (["end_turn", "max_tokens", "max_turn_requests", "refusal"].includes(stopReason)) {
    return { outcome: "succeeded", stopReason };
  }
  if (["cancelled", "canceled"].includes(stopReason)) return { outcome: "cancelled", stopReason };
  return { outcome: stopReason === "error" ? "failed" : "unknown", stopReason };
}

async function* iterateWithSignal<T>(events: AsyncIterable<T>, signal?: AbortSignal): AsyncGenerator<T> {
  const iterator = events[Symbol.asyncIterator]();
  try {
    while (true) {
      signal?.throwIfAborted();
      const event = await iterator.next();
      if (event.done) return;
      yield event.value;
    }
  } finally {
    Promise.resolve().then(() => iterator.return?.());
  }
}

function publicText(event: RelayEvent): string {
  const rpc = extractJsonRpc(event);
  if (rpc?.method !== "session/update") return "";
  const update = (rpc.params as { update?: { sessionUpdate?: string; content?: { type?: string; text?: unknown } } })
    ?.update;
  return update?.sessionUpdate === "agent_message_chunk" && typeof update.content?.text === "string"
    ? update.content.text
    : "";
}

function finishReason(event: RelayEvent): "stop" | "length" | null {
  const terminal = classifyAgentTurnEvent(event);
  if (!terminal) return null;
  if (terminal.outcome !== "succeeded") throw new Error("Agent turn did not complete successfully");
  if (terminal.stopReason === "end_turn" || terminal.stopReason === "refusal") return "stop";
  if (terminal.stopReason === "max_tokens" || terminal.stopReason === "max_turn_requests") return "length";
  throw new Error("Unrecognized Agent completion");
}

interface OpenAIChatCompletionResponse {
  id: string;
  object: "chat.completion";
  created: number;
  model: string;
  choices: Array<{ index: number; message: { role: "assistant"; content: string }; finish_reason: "stop" | "length" }>;
}

function mapToNonStreamingResponse(events: RelayEvent[], agentId: string): OpenAIChatCompletionResponse {
  let reason: "stop" | "length" | null = null;
  const content: string[] = [];
  for (const event of events) {
    content.push(publicText(event));
    const next = finishReason(event);
    if (next) {
      reason = next;
      break;
    }
  }
  if (!reason) throw new Error("Agent stream ended without confirmed completion");
  return {
    id: `chatcmpl-${crypto.randomUUID()}`,
    object: "chat.completion",
    created: Math.floor(Date.now() / 1000),
    model: agentId,
    choices: [{ index: 0, message: { role: "assistant", content: content.join("") }, finish_reason: reason }],
  };
}

async function* mapToSSEChunks(
  events: AsyncIterable<RelayEvent>,
  agentId: string,
  signal?: AbortSignal,
  onStopReason?: (reason: string) => void,
): AsyncGenerator<string, void, undefined> {
  const identity = {
    id: `chatcmpl-${crypto.randomUUID()}`,
    object: "chat.completion.chunk",
    created: Math.floor(Date.now() / 1000),
    model: agentId,
  };
  const chunk = (delta: Record<string, string>, reason: "stop" | "length" | null = null) =>
    `data: ${JSON.stringify({ ...identity, choices: [{ index: 0, delta, finish_reason: reason }] })}\n\n`;
  yield chunk({ role: "assistant" });
  for await (const event of iterateWithSignal(events, signal)) {
    const reason = finishReason(event);
    if (reason) {
      onStopReason?.(reason);
      yield chunk({}, reason);
      yield "data: [DONE]\n\n";
      return;
    }
    const text = publicText(event);
    if (text) yield chunk({ content: text });
  }
  throw new Error("Agent stream ended without confirmed completion");
}

function buildOpenAIError(status: number, message: string, type: string, code = "INTERNAL_ERROR") {
  return { status, body: { error: { message, type, param: null, code } } };
}

// --- 工具函数 ---

function updateEvent(sessionUpdate: string, content?: unknown): RelayEvent {
  return {
    type: "message",
    payload: {
      jsonrpc: "2.0",
      method: "session/update",
      params: { update: { sessionUpdate, content } },
    },
  };
}

function terminalEvent(stopReason: string): RelayEvent {
  return { type: "message", payload: { jsonrpc: "2.0", id: 1, result: { stopReason } } };
}

function parseSSE(chunk: string): Record<string, any> {
  expect(chunk.startsWith("data: ")).toBe(true);
  return JSON.parse(chunk.slice("data: ".length));
}

async function collect(gen: AsyncGenerator<string, void, undefined>): Promise<string[]> {
  const out: string[] = [];
  for await (const item of gen) out.push(item);
  return out;
}

// --- Tests ---

describe("publicText", () => {
  test("agent_message_chunk 字符串正文原样返回", () => {
    expect(publicText(updateEvent("agent_message_chunk", { type: "text", text: "Hello world" }))).toBe("Hello world");
  });

  test("agent_thought_chunk 不进入公开正文", () => {
    expect(publicText(updateEvent("agent_thought_chunk", { type: "text", text: "thinking..." }))).toBe("");
  });

  test("tool_call / plan 不再映射为文本", () => {
    expect(publicText(updateEvent("tool_call", { type: "text", text: "x" }))).toBe("");
    expect(publicText(updateEvent("plan", { type: "text", text: "x" }))).toBe("");
  });

  test("content.text 非字符串返回空串", () => {
    expect(publicText(updateEvent("agent_message_chunk", { type: "text", text: 123 }))).toBe("");
  });

  test("缺少 content 返回空串", () => {
    expect(publicText(updateEvent("agent_message_chunk"))).toBe("");
  });

  test("非 session/update 方法返回空串", () => {
    const ev: RelayEvent = { type: "message", payload: { jsonrpc: "2.0", method: "session/request" } };
    expect(publicText(ev)).toBe("");
  });

  test("非 JSON-RPC 事件返回空串", () => {
    expect(publicText({ type: "ping" })).toBe("");
  });

  test("顶层 JSON-RPC 事件同样可解析", () => {
    const ev: RelayEvent = {
      type: "message",
      jsonrpc: "2.0",
      method: "session/update",
      params: { update: { sessionUpdate: "agent_message_chunk", content: { text: "direct" } } },
    } as unknown as RelayEvent;
    expect(publicText(ev)).toBe("direct");
  });
});

describe("finishReason", () => {
  test("end_turn 映射 stop", () => {
    expect(finishReason(terminalEvent("end_turn"))).toBe("stop");
  });

  test("refusal 映射 stop", () => {
    expect(finishReason(terminalEvent("refusal"))).toBe("stop");
  });

  test("max_tokens 映射 length", () => {
    expect(finishReason(terminalEvent("max_tokens"))).toBe("length");
  });

  test("max_turn_requests 映射 length", () => {
    expect(finishReason(terminalEvent("max_turn_requests"))).toBe("length");
  });

  test("非终止事件返回 null", () => {
    expect(finishReason(updateEvent("agent_message_chunk", { text: "a" }))).toBeNull();
    expect(finishReason({ type: "ping" })).toBeNull();
  });

  test("失败终止事件抛错", () => {
    expect(() => finishReason({ type: "error" })).toThrow("Agent turn did not complete successfully");
    expect(() => finishReason({ type: "relay_closed" })).toThrow("Agent turn did not complete successfully");
    expect(() =>
      finishReason({ type: "message", payload: { jsonrpc: "2.0", id: 1, error: { code: -1 } } }),
    ).toThrow("Agent turn did not complete successfully");
  });

  test("未识别或被取消的 stopReason 抛错", () => {
    expect(() => finishReason(terminalEvent("weird_reason"))).toThrow("Agent turn did not complete successfully");
    expect(() => finishReason(terminalEvent("cancelled"))).toThrow("Agent turn did not complete successfully");
  });
});

describe("mapToNonStreamingResponse", () => {
  test("只拼接公开正文并在终止事件处停止", () => {
    const events = [
      updateEvent("agent_thought_chunk", { text: "hidden" }),
      updateEvent("tool_call", { text: "hidden" }),
      updateEvent("agent_message_chunk", { text: "Hello " }),
      updateEvent("agent_message_chunk", { text: "world" }),
      terminalEvent("end_turn"),
      updateEvent("agent_message_chunk", { text: "after-terminal" }),
    ];
    const resp = mapToNonStreamingResponse(events, "agent-1");
    expect(resp.object).toBe("chat.completion");
    expect(resp.model).toBe("agent-1");
    expect(resp.id.startsWith("chatcmpl-")).toBe(true);
    expect(resp.choices).toEqual([
      { index: 0, message: { role: "assistant", content: "Hello world" }, finish_reason: "stop" },
    ]);
  });

  test("max_tokens 终止映射 length", () => {
    const resp = mapToNonStreamingResponse(
      [updateEvent("agent_message_chunk", { text: "partial" }), terminalEvent("max_tokens")],
      "agent-2",
    );
    expect(resp.choices[0]!.finish_reason).toBe("length");
    expect(resp.choices[0]!.message.content).toBe("partial");
  });

  test("无终止事件抛错", () => {
    expect(() => mapToNonStreamingResponse([updateEvent("agent_message_chunk", { text: "a" })], "agent-3")).toThrow(
      "Agent stream ended without confirmed completion",
    );
  });

  test("空事件流抛错", () => {
    expect(() => mapToNonStreamingResponse([], "agent-4")).toThrow("Agent stream ended without confirmed completion");
  });

  test("id 每次调用唯一", () => {
    const a = mapToNonStreamingResponse([terminalEvent("end_turn")], "agent-5");
    const b = mapToNonStreamingResponse([terminalEvent("end_turn")], "agent-5");
    expect(a.id).not.toBe(b.id);
  });
});

describe("mapToSSEChunks", () => {
  test("输出 role 首帧、正文增量、终止帧与 [DONE]", async () => {
    async function* source() {
      yield updateEvent("agent_message_chunk", { text: "Hi" });
      yield updateEvent("agent_message_chunk", { text: " there" });
      yield terminalEvent("end_turn");
    }
    const chunks = await collect(mapToSSEChunks(source(), "agent-sse"));
    expect(chunks.length).toBe(5);
    const frames = chunks.slice(0, 4).map(parseSSE);
    expect(frames[0]!.choices[0]).toEqual({ index: 0, delta: { role: "assistant" }, finish_reason: null });
    expect(frames[1]!.choices[0]).toEqual({ index: 0, delta: { content: "Hi" }, finish_reason: null });
    expect(frames[2]!.choices[0]).toEqual({ index: 0, delta: { content: " there" }, finish_reason: null });
    expect(frames[3]!.choices[0]).toEqual({ index: 0, delta: {}, finish_reason: "stop" });
    expect(chunks[4]).toBe("data: [DONE]\n\n");
    // 同一流的 id / created / model 保持一致
    expect(new Set(frames.map((f) => f.id)).size).toBe(1);
    expect(frames[0]!.model).toBe("agent-sse");
  });

  test("onStopReason 收到映射后的原因", async () => {
    async function* source() {
      yield terminalEvent("max_tokens");
    }
    const seen: string[] = [];
    await collect(mapToSSEChunks(source(), "agent-sse", undefined, (r) => seen.push(r)));
    expect(seen).toEqual(["length"]);
  });

  test("流结束但无终止事件时抛错", async () => {
    async function* source() {
      yield updateEvent("agent_message_chunk", { text: "partial" });
    }
    await expect(collect(mapToSSEChunks(source(), "agent-sse"))).rejects.toThrow(
      "Agent stream ended without confirmed completion",
    );
  });

  test("已中止的 signal 在首帧后中断流", async () => {
    const controller = new AbortController();
    controller.abort(new Error("aborted by test"));
    async function* source() {
      yield updateEvent("agent_message_chunk", { text: "never-consumed" });
      yield terminalEvent("end_turn");
    }
    await expect(collect(mapToSSEChunks(source(), "agent-sse", controller.signal))).rejects.toThrow(
      "aborted by test",
    );
  });
});

describe("buildOpenAIError", () => {
  test("默认 code 为 INTERNAL_ERROR 且 param 为 null", () => {
    expect(buildOpenAIError(500, "Internal server error", "server_error")).toEqual({
      status: 500,
      body: { error: { message: "Internal server error", type: "server_error", param: null, code: "INTERNAL_ERROR" } },
    });
  });

  test("显式 code 原样透出", () => {
    const err = buildOpenAIError(401, "Invalid API key provided", "authentication_error", "invalid_api_key");
    expect(err.status).toBe(401);
    expect(err.body.error.code).toBe("invalid_api_key");
  });

  test("400 参数错误结构", () => {
    const err = buildOpenAIError(400, "Bad request", "invalid_request_error", "INVALID_REQUEST");
    expect(err.body.error).toEqual({
      message: "Bad request",
      type: "invalid_request_error",
      param: null,
      code: "INVALID_REQUEST",
    });
  });
});
