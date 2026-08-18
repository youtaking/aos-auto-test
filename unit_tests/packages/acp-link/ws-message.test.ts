import { describe, test, expect } from "bun:test";

// ========== Pure function copies from packages/acp-link/src/ws-message.ts ==========

const MAX_CLIENT_WS_PAYLOAD_BYTES = 10 * 1024 * 1024;

class WsPayloadTooLargeError extends Error {
  constructor(byteLength: number) {
    super(`WebSocket message too large: ${byteLength} bytes`);
    this.name = "WsPayloadTooLargeError";
  }
}

function decodeWsText(data: unknown): string {
  if (typeof data === "string") {
    if (Buffer.byteLength(data, "utf8") > MAX_CLIENT_WS_PAYLOAD_BYTES)
      throw new WsPayloadTooLargeError(Buffer.byteLength(data, "utf8"));
    return data;
  }
  if (data instanceof ArrayBuffer) {
    if (data.byteLength > MAX_CLIENT_WS_PAYLOAD_BYTES) throw new WsPayloadTooLargeError(data.byteLength);
    return new TextDecoder().decode(new Uint8Array(data));
  }
  if (ArrayBuffer.isView(data)) {
    if (data.byteLength > MAX_CLIENT_WS_PAYLOAD_BYTES) throw new WsPayloadTooLargeError(data.byteLength);
    return new TextDecoder().decode(new Uint8Array(data.buffer, data.byteOffset, data.byteLength));
  }
  if (Array.isArray(data) && data.every(Buffer.isBuffer)) {
    const byteLength = data.reduce((total: number, chunk: Buffer) => total + chunk.byteLength, 0);
    if (byteLength > MAX_CLIENT_WS_PAYLOAD_BYTES) throw new WsPayloadTooLargeError(byteLength);
    return Buffer.concat(data, byteLength).toString("utf8");
  }
  throw new Error("Unsupported WebSocket message payload");
}

function decodeJsonWsMessage(data: unknown): Record<string, unknown> {
  const text = decodeWsText(data);
  const parsed = JSON.parse(text) as unknown;
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed))
    throw new Error("Invalid WebSocket message payload");
  return parsed as Record<string, unknown>;
}

// ========== Tests ==========

describe("decodeWsText", () => {
  test("decodes a plain string", () => {
    expect(decodeWsText("hello world")).toBe("hello world");
  });

  test("decodes an empty string", () => {
    expect(decodeWsText("")).toBe("");
  });

  test("decodes a UTF-8 string with special characters", () => {
    expect(decodeWsText("你好世界")).toBe("你好世界");
  });

  test("decodes from ArrayBuffer", () => {
    const encoder = new TextEncoder();
    const buf = encoder.encode("hello from buffer");
    const arrayBuffer = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
    expect(decodeWsText(arrayBuffer)).toBe("hello from buffer");
  });

  test("decodes from Uint8Array", () => {
    const encoder = new TextEncoder();
    const uint8 = encoder.encode("uint8 message");
    expect(decodeWsText(uint8)).toBe("uint8 message");
  });

  test("decodes from Buffer array", () => {
    const buf1 = Buffer.from("hello ", "utf8");
    const buf2 = Buffer.from("world", "utf8");
    expect(decodeWsText([buf1, buf2])).toBe("hello world");
  });

  test("decodes from single Buffer in array", () => {
    const buf = Buffer.from("single buffer", "utf8");
    expect(decodeWsText([buf])).toBe("single buffer");
  });

  test("throws for unsupported type (number)", () => {
    expect(() => decodeWsText(42)).toThrow("Unsupported WebSocket message payload");
  });

  test("throws for unsupported type (boolean)", () => {
    expect(() => decodeWsText(true)).toThrow("Unsupported WebSocket message payload");
  });

  test("throws for unsupported type (null)", () => {
    expect(() => decodeWsText(null)).toThrow("Unsupported WebSocket message payload");
  });

  test("throws for unsupported type (plain object)", () => {
    expect(() => decodeWsText({ text: "hello" })).toThrow("Unsupported WebSocket message payload");
  });

  test("throws WsPayloadTooLargeError for oversized string", () => {
    // Create a string that exceeds 10MB
    const bigString = "x".repeat(MAX_CLIENT_WS_PAYLOAD_BYTES + 1);
    expect(() => decodeWsText(bigString)).toThrow(WsPayloadTooLargeError);
  });

  test("throws WsPayloadTooLargeError for oversized ArrayBuffer", () => {
    const buf = new ArrayBuffer(MAX_CLIENT_WS_PAYLOAD_BYTES + 1);
    expect(() => decodeWsText(buf)).toThrow(WsPayloadTooLargeError);
  });

  test("throws WsPayloadTooLargeError for oversized Uint8Array", () => {
    const uint8 = new Uint8Array(MAX_CLIENT_WS_PAYLOAD_BYTES + 1);
    expect(() => decodeWsText(uint8)).toThrow(WsPayloadTooLargeError);
  });

  test("WsPayloadTooLargeError has correct name", () => {
    const err = new WsPayloadTooLargeError(12345);
    expect(err.name).toBe("WsPayloadTooLargeError");
    expect(err.message).toContain("12345");
  });
});

describe("decodeJsonWsMessage", () => {
  test("decodes a valid JSON object from string", () => {
    const result = decodeJsonWsMessage('{"type":"ping","data":42}');
    expect(result).toEqual({ type: "ping", data: 42 });
  });

  test("decodes a valid JSON object from Buffer", () => {
    const buf = Buffer.from('{"key":"value"}', "utf8");
    const result = decodeJsonWsMessage(buf);
    expect(result).toEqual({ key: "value" });
  });

  test("decodes a valid JSON object from ArrayBuffer", () => {
    const encoder = new TextEncoder();
    const encoded = encoder.encode('{"hello":"world"}');
    const ab = encoded.buffer.slice(encoded.byteOffset, encoded.byteOffset + encoded.byteLength);
    const result = decodeJsonWsMessage(ab);
    expect(result).toEqual({ hello: "world" });
  });

  test("throws for JSON array", () => {
    expect(() => decodeJsonWsMessage("[1,2,3]")).toThrow("Invalid WebSocket message payload");
  });

  test("throws for JSON null", () => {
    expect(() => decodeJsonWsMessage("null")).toThrow("Invalid WebSocket message payload");
  });

  test("throws for JSON string primitive", () => {
    expect(() => decodeJsonWsMessage('"hello"')).toThrow("Invalid WebSocket message payload");
  });

  test("throws for JSON number primitive", () => {
    expect(() => decodeJsonWsMessage("42")).toThrow("Invalid WebSocket message payload");
  });

  test("throws for invalid JSON", () => {
    expect(() => decodeJsonWsMessage("{invalid json}")).toThrow();
  });

  test("handles nested objects", () => {
    const result = decodeJsonWsMessage('{"a":{"b":{"c":1}}}');
    expect(result).toEqual({ a: { b: { c: 1 } } });
  });

  test("handles empty object", () => {
    const result = decodeJsonWsMessage("{}");
    expect(result).toEqual({});
  });
});
