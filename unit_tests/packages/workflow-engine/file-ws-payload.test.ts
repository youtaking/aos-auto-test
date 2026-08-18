import { describe, test, expect } from "bun:test";

// ── Pure function copies from src/transport/file-ws-payload.ts ──
// Source version: FenixAgent/src/transport/file-ws-payload.ts (commit f5ac00e, 2025-08)
//
// Test adaptation: logError (@fenix/logger) calls in parseFileWsMessage are replaced
// with console.error — the test doesn't need the structured logger, and the log output
// is not asserted (only the parse behavior is tested).

const DEFAULT_FILE_WS_MAX_PAYLOAD_MB = 32;

/**
 * Estimates byte size of any WS message payload.
 * - Strings: UTF-8 byte count via Buffer.byteLength
 * - Uint8Array: byteLength
 * - Objects: re-serialized JSON byte count
 * - Unserializable (circular refs etc.): Infinity
 * - Other primitives: 0
 */
function estimateWSMessageBytes(data: unknown): number {
  if (typeof data === "string") return Buffer.byteLength(data);
  if (data instanceof Uint8Array) return data.byteLength;
  if (data !== null && typeof data === "object") {
    try {
      return Buffer.byteLength(JSON.stringify(data));
    } catch {
      return Infinity;
    }
  }
  return 0;
}

/**
 * Pre-parse payload size check: returns true if message exceeds limit.
 */
function checkWSMessageSize(message: string | Uint8Array, maxPayloadBytes: number): boolean {
  return estimateWSMessageBytes(message) > maxPayloadBytes;
}

/**
 * Post-parse object size check: returns true if parsed object exceeds limit.
 */
function checkParsedObjectSize(data: unknown, maxPayloadBytes: number): boolean {
  if (data === null || typeof data !== "object" || data instanceof Uint8Array) return false;
  return estimateWSMessageBytes(data) > maxPayloadBytes;
}

/**
 * Parse file-ws raw NDJSON message (split by \n, JSON.parse each line).
 * Empty/whitespace lines are skipped. Parse errors are logged and skipped.
 * Non-object parsed results (null, arrays, primitives) are skipped.
 *
 * Test adaptation: logError replaced with console.error (no @fenix/logger dependency).
 */
function parseFileWsMessage(raw: string): Record<string, unknown>[] {
  const messages: Record<string, unknown>[] = [];
  for (const line of raw.split("\n")) {
    if (!line.trim()) continue;
    let parsed: unknown;
    try {
      parsed = JSON.parse(line);
    } catch {
      // logError omitted — test doesn't need structured logger
      console.error("file-ws parse error:", line.length > 500 ? `${line.slice(0, 500)}... (truncated)` : line);
      continue;
    }
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      // logError omitted — test doesn't need structured logger
      console.error("file-ws parse error: non-object line skipped", line.length > 500 ? `${line.slice(0, 500)}... (truncated)` : line);
      continue;
    }
    messages.push(parsed as Record<string, unknown>);
  }
  return messages;
}

// ── Tests ──

describe("estimateWSMessageBytes", () => {
  test("ASCII string returns byte count equal to length", () => {
    expect(estimateWSMessageBytes("hello")).toBe(5);
  });

  test("empty string returns 0", () => {
    expect(estimateWSMessageBytes("")).toBe(0);
  });

  test("multi-byte UTF-8 string returns correct byte count", () => {
    // "你好" = 6 bytes in UTF-8 (3 bytes per CJK character)
    expect(estimateWSMessageBytes("你好")).toBe(6);
  });

  test("Uint8Array returns byteLength", () => {
    const data = new Uint8Array([1, 2, 3, 4, 5]);
    expect(estimateWSMessageBytes(data)).toBe(5);
  });

  test("empty Uint8Array returns 0", () => {
    expect(estimateWSMessageBytes(new Uint8Array(0))).toBe(0);
  });

  test("object is re-serialized and measured", () => {
    const obj = { type: "ping" };
    // JSON.stringify({ type: "ping" }) = '{"type":"ping"}' = 15 bytes
    expect(estimateWSMessageBytes(obj)).toBe(Buffer.byteLength('{"type":"ping"}'));
  });

  test("null returns 0", () => {
    expect(estimateWSMessageBytes(null)).toBe(0);
  });

  test("undefined returns 0", () => {
    expect(estimateWSMessageBytes(undefined)).toBe(0);
  });

  test("number returns 0", () => {
    expect(estimateWSMessageBytes(42)).toBe(0);
  });

  test("boolean returns 0", () => {
    expect(estimateWSMessageBytes(true)).toBe(0);
  });

  test("circular reference returns Infinity", () => {
    const obj: Record<string, unknown> = {};
    obj.self = obj;
    expect(estimateWSMessageBytes(obj)).toBe(Infinity);
  });

  test("array is treated as object (JSON.stringify)", () => {
    // Arrays pass the typeof === "object" check
    const arr = [1, 2, 3];
    expect(estimateWSMessageBytes(arr)).toBe(Buffer.byteLength("[1,2,3]"));
  });
});

describe("checkWSMessageSize", () => {
  const limit = 10; // 10 bytes

  test("returns false when message is within limit", () => {
    expect(checkWSMessageSize("hello", limit)).toBe(false);
  });

  test("returns true when message exceeds limit", () => {
    expect(checkWSMessageSize("this is a long message", limit)).toBe(true);
  });

  test("returns false when message is exactly at limit", () => {
    // "1234567890" = 10 bytes, 10 > 10 is false
    expect(checkWSMessageSize("1234567890", limit)).toBe(false);
  });

  test("returns true when message is 1 byte over limit", () => {
    // "12345678901" = 11 bytes, 11 > 10 is true
    expect(checkWSMessageSize("12345678901", limit)).toBe(true);
  });

  test("works with Uint8Array", () => {
    const small = new Uint8Array(5);
    const large = new Uint8Array(15);
    expect(checkWSMessageSize(small, limit)).toBe(false);
    expect(checkWSMessageSize(large, limit)).toBe(true);
  });

  test("empty string is within any positive limit", () => {
    expect(checkWSMessageSize("", limit)).toBe(false);
  });
});

describe("checkParsedObjectSize", () => {
  const limit = 20;

  test("returns false for non-object (string)", () => {
    expect(checkParsedObjectSize("hello", limit)).toBe(false);
  });

  test("returns false for null", () => {
    expect(checkParsedObjectSize(null, limit)).toBe(false);
  });

  test("returns false for number", () => {
    expect(checkParsedObjectSize(42, limit)).toBe(false);
  });

  test("returns false for Uint8Array (handled by checkWSMessageSize)", () => {
    expect(checkParsedObjectSize(new Uint8Array(100), limit)).toBe(false);
  });

  test("returns false for small object", () => {
    expect(checkParsedObjectSize({ type: "ping" }, limit)).toBe(false);
  });

  test("returns true for oversized object", () => {
    const bigObj = { data: "x".repeat(100) };
    expect(checkParsedObjectSize(bigObj, limit)).toBe(true);
  });

  test("returns false for empty object", () => {
    // {} serializes to "{}" = 2 bytes
    expect(checkParsedObjectSize({}, limit)).toBe(false);
  });

  test("returns true for circular reference (Infinity > limit)", () => {
    const circular: Record<string, unknown> = {};
    circular.self = circular;
    expect(checkParsedObjectSize(circular, limit)).toBe(true);
  });
});

describe("parseFileWsMessage", () => {
  test("parses single-line JSON", () => {
    const raw = '{"type":"ping","id":1}';
    const result = parseFileWsMessage(raw);
    expect(result).toEqual([{ type: "ping", id: 1 }]);
  });

  test("parses multi-line NDJSON", () => {
    const raw = '{"type":"a"}\n{"type":"b"}\n{"type":"c"}';
    const result = parseFileWsMessage(raw);
    expect(result).toHaveLength(3);
    expect(result[0].type).toBe("a");
    expect(result[1].type).toBe("b");
    expect(result[2].type).toBe("c");
  });

  test("skips empty lines", () => {
    const raw = '{"type":"a"}\n\n{"type":"b"}\n';
    const result = parseFileWsMessage(raw);
    expect(result).toHaveLength(2);
  });

  test("skips whitespace-only lines", () => {
    const raw = '{"type":"a"}\n   \n{"type":"b"}';
    const result = parseFileWsMessage(raw);
    expect(result).toHaveLength(2);
  });

  test("skips invalid JSON lines without crashing", () => {
    const raw = '{"type":"good"}\n{invalid json}\n{"type":"also-good"}';
    const result = parseFileWsMessage(raw);
    expect(result).toHaveLength(2);
    expect(result[0].type).toBe("good");
    expect(result[1].type).toBe("also-good");
  });

  test("skips null parsed values", () => {
    const raw = '{"type":"a"}\nnull\n{"type":"b"}';
    const result = parseFileWsMessage(raw);
    expect(result).toHaveLength(2);
  });

  test("skips array parsed values", () => {
    const raw = '{"type":"a"}\n[1,2,3]\n{"type":"b"}';
    const result = parseFileWsMessage(raw);
    expect(result).toHaveLength(2);
  });

  test("skips primitive parsed values (number)", () => {
    const raw = '{"type":"a"}\n42\n{"type":"b"}';
    const result = parseFileWsMessage(raw);
    expect(result).toHaveLength(2);
  });

  test("skips primitive parsed values (string)", () => {
    const raw = '{"type":"a"}\n"just a string"\n{"type":"b"}';
    const result = parseFileWsMessage(raw);
    expect(result).toHaveLength(2);
  });

  test("returns empty array for empty input", () => {
    expect(parseFileWsMessage("")).toEqual([]);
  });

  test("returns empty array for whitespace-only input", () => {
    expect(parseFileWsMessage("   \n  \n  ")).toEqual([]);
  });

  test("handles single valid object among many bad lines", () => {
    const raw = 'bad\nnull\n42\n{"type":"only-good"}\n[1]\nalso-bad';
    const result = parseFileWsMessage(raw);
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("only-good");
  });

  // ── Boundary tests ──

  test("handles all-invalid input gracefully", () => {
    const raw = "not-json\nalso-not-json\n{broken";
    const result = parseFileWsMessage(raw);
    expect(result).toEqual([]);
  });

  test("handles object with extra properties", () => {
    const raw = '{"type":"upload","fileId":"f1","name":"test.txt","size":1024}';
    const result = parseFileWsMessage(raw);
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("upload");
    expect(result[0].fileId).toBe("f1");
    expect(result[0].name).toBe("test.txt");
    expect(result[0].size).toBe(1024);
  });
});

describe("DEFAULT_FILE_WS_MAX_PAYLOAD_MB", () => {
  test("is 32 MB", () => {
    expect(DEFAULT_FILE_WS_MAX_PAYLOAD_MB).toBe(32);
  });
});
