import { describe, expect, test } from "bun:test";

// normalizePayload 纯函数复制（原函数位于 services/transport.ts，因 DB 依赖无法直接 import）

function extractContent(payload: unknown): string {
  if (!payload || typeof payload !== "object") {
    return typeof payload === "string" ? payload : "";
  }
  const p = payload as Record<string, unknown>;
  if (typeof p.content === "string" && p.content) return p.content;
  const msg = p.message;
  if (msg && typeof msg === "object") {
    const mc = (msg as Record<string, unknown>).content;
    if (typeof mc === "string") return mc;
    if (Array.isArray(mc)) {
      return mc
        .filter((b: unknown) => typeof b === "object" && b !== null && (b as Record<string, unknown>).type === "text")
        .map((b: Record<string, unknown>) => (b as Record<string, unknown>).text || "")
        .join("");
    }
  }
  return "";
}

function normalizePayload(type: string, payload: unknown): Record<string, unknown> {
  if (!payload || typeof payload !== "object") {
    return { content: typeof payload === "string" ? payload : "", raw: payload };
  }
  const p = payload as Record<string, unknown>;
  const content = extractContent(payload);
  const normalized: Record<string, unknown> = { content, raw: payload };
  if (typeof p.uuid === "string" && p.uuid) normalized.uuid = p.uuid;
  if (typeof p.isSynthetic === "boolean") normalized.isSynthetic = p.isSynthetic;
  if (typeof p.status === "string") normalized.status = p.status;
  if (typeof p.subtype === "string") normalized.subtype = p.subtype;
  if (p.tool_name) normalized.tool_name = p.tool_name;
  if (p.name) normalized.tool_name = p.name;
  if (p.tool_input) normalized.tool_input = p.tool_input;
  if (p.input) normalized.tool_input = p.input;
  if (p.request_id) normalized.request_id = p.request_id;
  if (p.request) normalized.request = p.request;
  if (p.approved !== undefined) normalized.approved = p.approved;
  if (p.updated_input) normalized.updated_input = p.updated_input;
  if (p.message) normalized.message = p.message;
  if (type === "task_state") {
    if (typeof p.task_list_id === "string") normalized.task_list_id = p.task_list_id;
    if (typeof p.taskListId === "string") normalized.taskListId = p.taskListId;
    if (Array.isArray(p.tasks)) normalized.tasks = p.tasks;
  }
  return normalized;
}

// ── extractContent (via normalizePayload) ──

describe("extractContent", () => {
  test("returns empty string for null payload", () => {
    expect(normalizePayload("assistant", null).content).toBe("");
  });

  test("returns empty string for undefined payload", () => {
    expect(normalizePayload("assistant", undefined).content).toBe("");
  });

  test("returns the string for string payload", () => {
    expect(normalizePayload("assistant", "hello world").content).toBe("hello world");
  });

  test("extracts content field from object payload", () => {
    expect(normalizePayload("assistant", { content: "direct content" }).content).toBe("direct content");
  });

  test("extracts message.content string from object payload", () => {
    expect(normalizePayload("assistant", { message: { content: "msg content" } }).content).toBe("msg content");
  });

  test("extracts text blocks from message.content array", () => {
    const payload = {
      message: {
        content: [
          { type: "text", text: "Hello " },
          { type: "text", text: "World" },
        ],
      },
    };
    expect(normalizePayload("assistant", payload).content).toBe("Hello World");
  });

  test("ignores non-text blocks in message.content array", () => {
    const payload = {
      message: {
        content: [
          { type: "image", url: "http://example.com/img.png" },
          { type: "text", text: "only this" },
        ],
      },
    };
    expect(normalizePayload("assistant", payload).content).toBe("only this");
  });

  test("returns empty string when no extractable content", () => {
    expect(normalizePayload("assistant", { foo: "bar" }).content).toBe("");
  });

  test("prefers direct content over message.content", () => {
    expect(normalizePayload("assistant", { content: "direct", message: { content: "nested" } }).content).toBe("direct");
  });
});

// ── normalizePayload field preservation ──

describe("normalizePayload — field preservation", () => {
  test("preserves raw payload", () => {
    const payload = { content: "test", extra: true };
    expect(normalizePayload("assistant", payload).raw).toBe(payload);
  });

  test("preserves uuid field", () => {
    expect(normalizePayload("assistant", { uuid: "u-123" }).uuid).toBe("u-123");
  });

  test("does not preserve uuid when empty string", () => {
    expect(normalizePayload("assistant", { uuid: "" }).uuid).toBeUndefined();
  });

  test("preserves isSynthetic boolean", () => {
    expect(normalizePayload("assistant", { isSynthetic: true }).isSynthetic).toBe(true);
  });

  test("preserves status string", () => {
    expect(normalizePayload("assistant", { status: "running" }).status).toBe("running");
  });

  test("preserves subtype string", () => {
    expect(normalizePayload("assistant", { subtype: "progress" }).subtype).toBe("progress");
  });

  test("preserves tool_name from tool_name field", () => {
    expect(normalizePayload("tool", { tool_name: "bash" }).tool_name).toBe("bash");
  });

  test("preserves tool_name from name field", () => {
    expect(normalizePayload("tool", { name: "read" }).tool_name).toBe("read");
  });

  test("preserves tool_input from tool_input field", () => {
    const input = { command: "ls" };
    expect(normalizePayload("tool", { tool_input: input }).tool_input).toEqual(input);
  });

  test("preserves tool_input from input field", () => {
    const input = { path: "/tmp" };
    expect(normalizePayload("tool", { input }).tool_input).toEqual(input);
  });

  test("preserves request_id", () => {
    expect(normalizePayload("permission", { request_id: "req-1" }).request_id).toBe("req-1");
  });

  test("preserves request object", () => {
    const req = { subtype: "permission" };
    expect(normalizePayload("permission", { request: req }).request).toEqual(req);
  });

  test("preserves approved field", () => {
    expect(normalizePayload("permission", { approved: true }).approved).toBe(true);
  });

  test("preserves updated_input", () => {
    const input = { command: "rm -rf" };
    expect(normalizePayload("permission", { updated_input: input }).updated_input).toEqual(input);
  });

  test("preserves message field for backward compat", () => {
    const msg = { role: "user", content: "hi" };
    expect(normalizePayload("assistant", { message: msg }).message).toEqual(msg);
  });
});

// ── normalizePayload task_state type ──

describe("normalizePayload — task_state type", () => {
  test("preserves task_list_id (snake_case)", () => {
    expect(normalizePayload("task_state", { task_list_id: "tl-1" }).task_list_id).toBe("tl-1");
  });

  test("preserves taskListId (camelCase)", () => {
    expect(normalizePayload("task_state", { taskListId: "tl-2" }).taskListId).toBe("tl-2");
  });

  test("preserves tasks array", () => {
    const tasks = [{ id: "t1", title: "Task 1" }];
    expect(normalizePayload("task_state", { tasks }).tasks).toEqual(tasks);
  });

  test("does not preserve task fields for non-task_state type", () => {
    const result = normalizePayload("assistant", { task_list_id: "tl-1", taskListId: "tl-2", tasks: [] });
    expect(result.task_list_id).toBeUndefined();
    expect(result.taskListId).toBeUndefined();
    expect(result.tasks).toBeUndefined();
  });
});
