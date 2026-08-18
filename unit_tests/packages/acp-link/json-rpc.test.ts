import { describe, test, expect, beforeEach } from "bun:test";

// ========== Pure function copies from packages/acp-link/src/json-rpc.ts ==========

interface JsonRpcRequest {
  jsonrpc: "2.0";
  id: number | string;
  method: string;
  params?: unknown;
}

interface JsonRpcNotification {
  jsonrpc: "2.0";
  method: string;
  params?: unknown;
}

interface JsonRpcSuccessResponse {
  jsonrpc: "2.0";
  id: number | string;
  result: unknown;
}

interface JsonRpcErrorResponse {
  jsonrpc: "2.0";
  id: number | string | null;
  error: { code: number; message: string; data?: unknown };
}

type JsonRpcResponse = JsonRpcSuccessResponse | JsonRpcErrorResponse;
type JsonRpcMessage = JsonRpcRequest | JsonRpcNotification | JsonRpcResponse;

const ACP_METHOD = {
  SESSION_NEW: "session/new",
  SESSION_LOAD: "session/load",
  SESSION_RESUME: "session/resume",
  SESSION_LIST: "session/list",
  SESSION_PROMPT: "session/prompt",
  SESSION_CANCEL: "session/cancel",
  SESSION_SET_MODEL: "session/setModel",
  SESSION_SET_MODE: "session/setMode",
  SESSION_UPDATE: "session/update",
  SESSION_MODEL_CHANGED: "session/modelChanged",
  SESSION_MODE_CHANGED: "session/modeChanged",
  SESSION_DELETE: "session/delete",
  SESSION_RENAME: "session/rename",
  REQUEST_PERMISSION: "requestPermission",
} as const;

const TRANSPORT_TYPES = [
  "connect",
  "disconnect",
  "status",
  "error",
  "ping",
  "pong",
  "keep_alive",
  "control_response",
  "permission_response",
  "permission_request",
  "interactive_question",
  "cancel_pending_permissions",
] as const;

// Mutable counter — reset in beforeEach
let _nextId = 0;
function nextRpcId(): number {
  _nextId += 1;
  return _nextId;
}

function createRequest(method: string, params?: unknown): JsonRpcRequest {
  return { jsonrpc: "2.0", id: nextRpcId(), method, params: params ?? {} };
}

function createNotification(method: string, params?: unknown): JsonRpcNotification {
  return { jsonrpc: "2.0", method, params };
}

function createSuccessResponse(id: number | string, result: unknown): JsonRpcSuccessResponse {
  return { jsonrpc: "2.0", id, result };
}

function createErrorResponse(
  id: number | string | null,
  code: number,
  message: string,
): JsonRpcErrorResponse {
  return { jsonrpc: "2.0", id, error: { code, message } };
}

function isJsonRpcMessage(msg: unknown): msg is JsonRpcMessage {
  return typeof msg === "object" && msg !== null && (msg as Record<string, unknown>).jsonrpc === "2.0";
}

function isJsonRpcRequest(msg: JsonRpcMessage): msg is JsonRpcRequest {
  return "method" in msg && "id" in msg;
}

function isJsonRpcNotification(msg: JsonRpcMessage): msg is JsonRpcNotification {
  return "method" in msg && !("id" in msg);
}

function isJsonRpcResponse(msg: JsonRpcMessage): msg is JsonRpcResponse {
  return "id" in msg && ("result" in msg || "error" in msg);
}

function isTransportMessage(msg: unknown): boolean {
  if (typeof msg !== "object" || msg === null) return false;
  const type = (msg as Record<string, unknown>).type;
  return typeof type === "string" && (TRANSPORT_TYPES as readonly string[]).includes(type);
}

// ========== Tests ==========

beforeEach(() => {
  _nextId = 0;
});

describe("ACP_METHOD constants", () => {
  test("has correct method values", () => {
    expect(ACP_METHOD.SESSION_NEW).toBe("session/new");
    expect(ACP_METHOD.SESSION_LOAD).toBe("session/load");
    expect(ACP_METHOD.SESSION_RESUME).toBe("session/resume");
    expect(ACP_METHOD.SESSION_LIST).toBe("session/list");
    expect(ACP_METHOD.SESSION_PROMPT).toBe("session/prompt");
    expect(ACP_METHOD.SESSION_CANCEL).toBe("session/cancel");
    expect(ACP_METHOD.SESSION_SET_MODEL).toBe("session/setModel");
    expect(ACP_METHOD.SESSION_SET_MODE).toBe("session/setMode");
    expect(ACP_METHOD.SESSION_UPDATE).toBe("session/update");
    expect(ACP_METHOD.SESSION_MODEL_CHANGED).toBe("session/modelChanged");
    expect(ACP_METHOD.SESSION_MODE_CHANGED).toBe("session/modeChanged");
    expect(ACP_METHOD.SESSION_DELETE).toBe("session/delete");
    expect(ACP_METHOD.SESSION_RENAME).toBe("session/rename");
    expect(ACP_METHOD.REQUEST_PERMISSION).toBe("requestPermission");
  });

  test("has all 14 methods", () => {
    expect(Object.keys(ACP_METHOD).length).toBe(14);
  });
});

describe("nextRpcId", () => {
  test("increments sequentially starting from 1", () => {
    expect(nextRpcId()).toBe(1);
    expect(nextRpcId()).toBe(2);
    expect(nextRpcId()).toBe(3);
  });

  test("always returns a number greater than previous", () => {
    const a = nextRpcId();
    const b = nextRpcId();
    expect(b).toBeGreaterThan(a);
  });
});

describe("createRequest", () => {
  test("creates a valid JSON-RPC request with default empty params", () => {
    const req = createRequest("session/new");
    expect(req.jsonrpc).toBe("2.0");
    expect(req.id).toBe(1);
    expect(req.method).toBe("session/new");
    expect(req.params).toEqual({});
  });

  test("creates a request with explicit params", () => {
    const req = createRequest("session/prompt", { text: "hello" });
    expect(req.jsonrpc).toBe("2.0");
    expect(req.id).toBe(1);
    expect(req.method).toBe("session/prompt");
    expect(req.params).toEqual({ text: "hello" });
  });

  test("uses nextRpcId for id", () => {
    const req1 = createRequest("a");
    const req2 = createRequest("b");
    expect(req1.id).toBe(1);
    expect(req2.id).toBe(2);
  });

  test("params undefined defaults to empty object", () => {
    const req = createRequest("test");
    expect(req.params).toEqual({});
  });
});

describe("createNotification", () => {
  test("creates a notification without id", () => {
    const notif = createNotification("session/update");
    expect(notif.jsonrpc).toBe("2.0");
    expect(notif.method).toBe("session/update");
    expect(notif.params).toBeUndefined();
    expect("id" in notif).toBe(false);
  });

  test("creates a notification with params", () => {
    const notif = createNotification("session/update", { data: 42 });
    expect(notif.params).toEqual({ data: 42 });
  });
});

describe("createSuccessResponse", () => {
  test("creates a success response", () => {
    const resp = createSuccessResponse(1, { ok: true });
    expect(resp.jsonrpc).toBe("2.0");
    expect(resp.id).toBe(1);
    expect(resp.result).toEqual({ ok: true });
  });

  test("accepts string id", () => {
    const resp = createSuccessResponse("abc", null);
    expect(resp.id).toBe("abc");
  });
});

describe("createErrorResponse", () => {
  test("creates an error response", () => {
    const resp = createErrorResponse(1, -32600, "Invalid Request");
    expect(resp.jsonrpc).toBe("2.0");
    expect(resp.id).toBe(1);
    expect(resp.error.code).toBe(-32600);
    expect(resp.error.message).toBe("Invalid Request");
  });

  test("accepts null id", () => {
    const resp = createErrorResponse(null, -32700, "Parse error");
    expect(resp.id).toBeNull();
  });
});

describe("isJsonRpcMessage", () => {
  test("returns true for a request", () => {
    const req = createRequest("test");
    expect(isJsonRpcMessage(req)).toBe(true);
  });

  test("returns true for a notification", () => {
    const notif = createNotification("test");
    expect(isJsonRpcMessage(notif)).toBe(true);
  });

  test("returns true for a success response", () => {
    const resp = createSuccessResponse(1, {});
    expect(isJsonRpcMessage(resp)).toBe(true);
  });

  test("returns true for an error response", () => {
    const resp = createErrorResponse(1, -1, "error");
    expect(isJsonRpcMessage(resp)).toBe(true);
  });

  test("returns false for null", () => {
    expect(isJsonRpcMessage(null)).toBe(false);
  });

  test("returns false for a string", () => {
    expect(isJsonRpcMessage("hello")).toBe(false);
  });

  test("returns false for object without jsonrpc field", () => {
    expect(isJsonRpcMessage({ method: "test" })).toBe(false);
  });

  test("returns false for object with wrong jsonrpc version", () => {
    expect(isJsonRpcMessage({ jsonrpc: "1.0", method: "test" })).toBe(false);
  });

  test("returns false for a number", () => {
    expect(isJsonRpcMessage(42)).toBe(false);
  });
});

describe("isJsonRpcRequest", () => {
  test("returns true for a request (has method and id)", () => {
    const req = createRequest("test");
    expect(isJsonRpcRequest(req)).toBe(true);
  });

  test("returns false for a notification (no id)", () => {
    const notif = createNotification("test");
    expect(isJsonRpcRequest(notif)).toBe(false);
  });

  test("returns false for a success response (no method)", () => {
    const resp = createSuccessResponse(1, {});
    expect(isJsonRpcRequest(resp)).toBe(false);
  });
});

describe("isJsonRpcNotification", () => {
  test("returns true for a notification", () => {
    const notif = createNotification("test");
    expect(isJsonRpcNotification(notif)).toBe(true);
  });

  test("returns false for a request (has id)", () => {
    const req = createRequest("test");
    expect(isJsonRpcNotification(req)).toBe(false);
  });

  test("returns false for a response", () => {
    const resp = createSuccessResponse(1, {});
    expect(isJsonRpcNotification(resp)).toBe(false);
  });
});

describe("isJsonRpcResponse", () => {
  test("returns true for a success response", () => {
    const resp = createSuccessResponse(1, { data: "ok" });
    expect(isJsonRpcResponse(resp)).toBe(true);
  });

  test("returns true for an error response", () => {
    const resp = createErrorResponse(1, -1, "fail");
    expect(isJsonRpcResponse(resp)).toBe(true);
  });

  test("returns false for a request (no result or error)", () => {
    const req = createRequest("test");
    expect(isJsonRpcResponse(req)).toBe(false);
  });

  test("returns false for a notification", () => {
    const notif = createNotification("test");
    expect(isJsonRpcNotification(notif)).toBe(true);
    expect(isJsonRpcResponse(notif)).toBe(false);
  });
});

describe("isTransportMessage", () => {
  test("returns true for all valid transport types", () => {
    for (const type of TRANSPORT_TYPES) {
      expect(isTransportMessage({ type })).toBe(true);
    }
  });

  test("returns false for invalid type string", () => {
    expect(isTransportMessage({ type: "invalid_type" })).toBe(false);
  });

  test("returns false for empty type", () => {
    expect(isTransportMessage({ type: "" })).toBe(false);
  });

  test("returns false for null", () => {
    expect(isTransportMessage(null)).toBe(false);
  });

  test("returns false for undefined", () => {
    expect(isTransportMessage(undefined)).toBe(false);
  });

  test("returns false for a string", () => {
    expect(isTransportMessage("connect")).toBe(false);
  });

  test("returns false for object without type field", () => {
    expect(isTransportMessage({ data: "hello" })).toBe(false);
  });

  test("returns false when type is a number", () => {
    expect(isTransportMessage({ type: 42 })).toBe(false);
  });
});
