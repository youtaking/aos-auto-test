// file-ws-payload.test.ts — WS 载荷估算、大小检查与 NDJSON 解析测试
// 测试目标：estimateWsMessageBytes / checkWsMessageSize / checkParsedObjectSize / parseFileWsMessage
// 业务意图：确保 file-ws 载荷上限防护和 NDJSON 解析在各种边界条件下正确工作

import { describe, expect, test } from "bun:test";

// ── 复制纯函数（避免 @fenix/logger 依赖链）──

function estimateWsMessageBytes(data: unknown): number {
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

function checkWsMessageSize(message: string | Uint8Array, maxPayloadBytes: number): boolean {
  return estimateWsMessageBytes(message) > maxPayloadBytes;
}

function checkParsedObjectSize(data: unknown, maxPayloadBytes: number): boolean {
  if (data === null || typeof data !== "object" || data instanceof Uint8Array) return false;
  return estimateWsMessageBytes(data) > maxPayloadBytes;
}

function parseFileWsMessage(raw: string): Record<string, unknown>[] {
  const messages: Record<string, unknown>[] = [];
  for (const line of raw.split("\n")) {
    if (!line.trim()) continue;
    let parsed: unknown;
    try {
      parsed = JSON.parse(line);
    } catch {
      continue;
    }
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      continue;
    }
    messages.push(parsed as Record<string, unknown>);
  }
  return messages;
}

// ── estimateWsMessageBytes ──

describe("estimateWsMessageBytes", () => {
  // ASCII 字符串按字节计算
  test("ASCII 字符串按 UTF-8 字节计算", () => {
    expect(estimateWsMessageBytes("hello")).toBe(5);
    expect(estimateWsMessageBytes("")).toBe(0);
  });

  // 多字节 UTF-8 字符按实际字节计算（中文 3 字节/字）
  test("中文 UTF-8 字符串按实际字节计算", () => {
    expect(estimateWsMessageBytes("你好")).toBe(6); // 每个中文字 3 字节
  });

  // Uint8Array 按 byteLength
  test("Uint8Array 按 byteLength 计算", () => {
    const buf = new Uint8Array([1, 2, 3, 4, 5]);
    expect(estimateWsMessageBytes(buf)).toBe(5);
  });

  // object 按 JSON 序列化后的字节数
  test("object 按 JSON 序列化字节数计算", () => {
    const obj = { type: "test" };
    const expected = Buffer.byteLength(JSON.stringify(obj));
    expect(estimateWsMessageBytes(obj)).toBe(expected);
  });

  // null / undefined / number / boolean 返回 0
  test("非字符串非对象类型返回 0", () => {
    expect(estimateWsMessageBytes(null)).toBe(0);
    expect(estimateWsMessageBytes(undefined)).toBe(0);
    expect(estimateWsMessageBytes(42)).toBe(0);
    expect(estimateWsMessageBytes(true)).toBe(0);
  });

  // 循环引用对象返回 Infinity
  test("循环引用对象返回 Infinity", () => {
    const obj: Record<string, unknown> = {};
    obj.self = obj;
    expect(estimateWsMessageBytes(obj)).toBe(Infinity);
  });
});

// ── checkWsMessageSize ──

describe("checkWsMessageSize", () => {
  const limit = 100; // 100 bytes limit for testing

  // 未超限返回 false
  test("未超限返回 false", () => {
    expect(checkWsMessageSize("hello", limit)).toBe(false);
    expect(checkWsMessageSize(new Uint8Array(50), limit)).toBe(false);
  });

  // 恰好等于上限返回 false
  test("恰好等于上限返回 false", () => {
    expect(checkWsMessageSize("a".repeat(100), limit)).toBe(false);
  });

  // 超过上限返回 true
  test("超过上限返回 true", () => {
    expect(checkWsMessageSize("a".repeat(101), limit)).toBe(true);
  });

  // 二进制帧超限
  test("二进制帧超过上限返回 true", () => {
    expect(checkWsMessageSize(new Uint8Array(101), limit)).toBe(true);
  });
});

// ── checkParsedObjectSize ──

describe("checkParsedObjectSize", () => {
  const limit = 100;

  // null 不触发检查
  test("null 返回 false", () => {
    expect(checkParsedObjectSize(null, limit)).toBe(false);
  });

  // 非对象类型返回 false
  test("非对象类型返回 false", () => {
    expect(checkParsedObjectSize("string", limit)).toBe(false);
    expect(checkParsedObjectSize(42, limit)).toBe(false);
    expect(checkParsedObjectSize(true, limit)).toBe(false);
  });

  // Uint8Array 不触发（由 checkWsMessageSize 处理）
  test("Uint8Array 返回 false（由 checkWsMessageSize 处理）", () => {
    expect(checkParsedObjectSize(new Uint8Array(200), limit)).toBe(false);
  });

  // 小对象未超限返回 false
  test("小对象未超限返回 false", () => {
    expect(checkParsedObjectSize({ type: "test" }, limit)).toBe(false);
  });

  // 大对象超限返回 true
  test("大对象超限返回 true", () => {
    const bigObj = { data: "x".repeat(200) };
    expect(checkParsedObjectSize(bigObj, limit)).toBe(true);
  });

  // 循环引用视为超限（Infinity > any limit）
  test("循环引用对象视为超限", () => {
    const obj: Record<string, unknown> = {};
    obj.self = obj;
    expect(checkParsedObjectSize(obj, limit)).toBe(true);
  });
});

// ── parseFileWsMessage ──

describe("parseFileWsMessage", () => {
  // 单行 JSON 正确解析
  test("单行 JSON 正确解析", () => {
    const raw = '{"type":"file_changed","path":"test.txt"}';
    const msgs = parseFileWsMessage(raw);
    expect(msgs).toHaveLength(1);
    expect(msgs[0].type).toBe("file_changed");
    expect(msgs[0].path).toBe("test.txt");
  });

  // NDJSON 多行解析
  test("NDJSON 多行逐行解析", () => {
    const raw = '{"type":"a"}\n{"type":"b"}\n{"type":"c"}';
    const msgs = parseFileWsMessage(raw);
    expect(msgs).toHaveLength(3);
    expect(msgs.map((m) => m.type)).toEqual(["a", "b", "c"]);
  });

  // 空行和纯空白行忽略
  test("空行和空白行被忽略", () => {
    const raw = '{"type":"a"}\n\n  \n{"type":"b"}\n';
    const msgs = parseFileWsMessage(raw);
    expect(msgs).toHaveLength(2);
  });

  // 坏 JSON 行跳过不中断后续行
  test("坏 JSON 行跳过不中断后续行", () => {
    const raw = '{"type":"a"}\n{invalid json}\n{"type":"c"}';
    const msgs = parseFileWsMessage(raw);
    expect(msgs).toHaveLength(2);
    expect(msgs[0].type).toBe("a");
    expect(msgs[1].type).toBe("c");
  });

  // null 行被跳过
  test("null 行被跳过", () => {
    const raw = '{"type":"a"}\nnull\n{"type":"b"}';
    const msgs = parseFileWsMessage(raw);
    expect(msgs).toHaveLength(2);
  });

  // 数组行被跳过
  test("数组行被跳过", () => {
    const raw = '{"type":"a"}\n[1,2,3]\n{"type":"b"}';
    const msgs = parseFileWsMessage(raw);
    expect(msgs).toHaveLength(2);
  });

  // 原始值行被跳过
  test("原始值行被跳过", () => {
    const raw = '{"type":"a"}\n42\n"string"\n{"type":"b"}';
    const msgs = parseFileWsMessage(raw);
    expect(msgs).toHaveLength(2);
  });

  // 空字符串返回空数组
  test("空字符串返回空数组", () => {
    expect(parseFileWsMessage("")).toHaveLength(0);
    expect(parseFileWsMessage("\n\n")).toHaveLength(0);
  });
});
