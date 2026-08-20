// external-relay.test.ts — 外部 ACP 客户端 Relay 纯逻辑测试
// 测试目标：handleExternalRelayMessage 消息解析、ping/pong 处理、pending buffer
// 业务意图：确保外部客户端消息正确解析和转发，非法消息被忽略

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数（从 external-relay.ts 提取） ──

interface WsConnection {
  readyState: number;
  send: (data: string) => void;
  close: (code?: number, reason?: string) => void;
}

const pendingRelayMessages = new Map<string, Array<Record<string, unknown>>>();

interface ExternalRelayEntry {
  ws: WsConnection;
  relayHandle: {
    send: (msg: { type: string; payload?: unknown }) => void;
  };
  instanceId: string;
}

const entries = new Map<string, ExternalRelayEntry>();

function sendToRelayWs(ws: WsConnection, message: Record<string, unknown>): void {
  if (ws.readyState !== 1) return;
  try {
    ws.send(JSON.stringify(message));
  } catch {
    /* ignore */
  }
}

interface ParsedMessage {
  type?: string;
  [key: string]: unknown;
}

function parseRelayMessage(
  data: string | Record<string, unknown>,
): { ok: true; parsed: ParsedMessage } | { ok: false } {
  let parsed: ParsedMessage;
  if (typeof data === "string") {
    try {
      parsed = JSON.parse(data) as ParsedMessage;
    } catch {
      return { ok: false };
    }
    if (typeof parsed !== "object" || parsed === null) return { ok: false };
  } else {
    parsed = data;
  }
  return { ok: true, parsed };
}

function handlePing(parsed: ParsedMessage, ws: WsConnection): boolean {
  if (parsed.type === "ping") {
    sendToRelayWs(ws, { type: "pong" });
    return true;
  }
  return false;
}

function handleConnect(parsed: ParsedMessage): boolean {
  return parsed.type === "connect";
}

function routeToPending(relayWsId: string, parsed: ParsedMessage): boolean {
  if (pendingRelayMessages.has(relayWsId)) {
    pendingRelayMessages.get(relayWsId)!.push(parsed);
    return true;
  }
  return false;
}

function routeToRelay(relayWsId: string, parsed: ParsedMessage): { sent: boolean } {
  const entry = entries.get(relayWsId);
  if (!entry) return { sent: false };
  try {
    entry.relayHandle.send(parsed as { type: string; payload?: unknown });
    return { sent: true };
  } catch {
    return { sent: false };
  }
}

// ── 辅助工厂 ──

function makeWs(readyState = 1): WsConnection & { sent: string[] } {
  const sent: string[] = [];
  return {
    readyState,
    send: mock((data: string) => sent.push(data)),
    close: mock(() => {}),
    sent,
  };
}

function makeRelayHandle(): { send: ReturnType<typeof mock>; sentMessages: Array<Record<string, unknown>> } {
  const sentMessages: Array<Record<string, unknown>> = [];
  return {
    send: mock((msg: Record<string, unknown>) => sentMessages.push(msg)),
    sentMessages,
  };
}

// ── tests ──

describe("external-relay 外部 Relay", () => {
  beforeEach(() => {
    mock.restore();
    pendingRelayMessages.clear();
    entries.clear();
  });

  describe("parseRelayMessage 消息解析", () => {
    test("合法 JSON 字符串解析成功", () => {
      const result = parseRelayMessage('{"type":"prompt","text":"hello"}');
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.parsed.type).toBe("prompt");
    });

    test("对象直接透传", () => {
      const obj = { type: "prompt", text: "hello" };
      const result = parseRelayMessage(obj);
      expect(result.ok).toBe(true);
      if (result.ok) expect(result.parsed).toBe(obj);
    });

    test("非法 JSON 字符串解析失败", () => {
      const result = parseRelayMessage("not-json{{{");
      expect(result.ok).toBe(false);
    });

    test("空字符串解析失败", () => {
      const result = parseRelayMessage("");
      expect(result.ok).toBe(false);
    });

    test("JSON 原始值（数字）被拒绝", () => {
      const result = parseRelayMessage("42");
      expect(result.ok).toBe(false);
    });

    test("JSON 原始值（字符串）被拒绝", () => {
      const result = parseRelayMessage('"just a string"');
      expect(result.ok).toBe(false);
    });

    test("JSON null 被拒绝", () => {
      const result = parseRelayMessage("null");
      expect(result.ok).toBe(false);
    });
  });

  describe("handlePing 心跳处理", () => {
    test("ping 消息回复 pong", () => {
      const ws = makeWs();
      const handled = handlePing({ type: "ping" }, ws);
      expect(handled).toBe(true);
      expect(ws.sent.length).toBe(1);
      const pong = JSON.parse(ws.sent[0]);
      expect(pong.type).toBe("pong");
    });

    test("非 ping 消息不处理", () => {
      const ws = makeWs();
      expect(handlePing({ type: "prompt" }, ws)).toBe(false);
      expect(ws.sent.length).toBe(0);
    });

    test("WS 已关闭时不发送 pong", () => {
      const ws = makeWs(3); // CLOSED
      handlePing({ type: "ping" }, ws);
      expect(ws.sent.length).toBe(0);
    });
  });

  describe("handleConnect connect 消息丢弃", () => {
    test("connect 类型返回 true（需丢弃）", () => {
      expect(handleConnect({ type: "connect" })).toBe(true);
    });

    test("非 connect 类型返回 false", () => {
      expect(handleConnect({ type: "prompt" })).toBe(false);
    });

    test("无 type 返回 false", () => {
      expect(handleConnect({})).toBe(false);
    });
  });

  describe("routeToPending pending 消息缓存", () => {
    test("有 pending buffer 时消息被缓存", () => {
      pendingRelayMessages.set("ws-1", []);
      const msg = { type: "prompt", text: "hello" };
      const result = routeToPending("ws-1", msg);
      expect(result).toBe(true);
      expect(pendingRelayMessages.get("ws-1")).toEqual([msg]);
    });

    test("无 pending buffer 时返回 false", () => {
      const result = routeToPending("ws-2", { type: "prompt" });
      expect(result).toBe(false);
    });

    test("多条消息按序缓存", () => {
      pendingRelayMessages.set("ws-1", []);
      routeToPending("ws-1", { type: "a" });
      routeToPending("ws-1", { type: "b" });
      routeToPending("ws-1", { type: "c" });
      expect(pendingRelayMessages.get("ws-1")!.length).toBe(3);
    });
  });

  describe("routeToRelay 消息转发", () => {
    test("连接存在时消息被转发", () => {
      const ws = makeWs();
      const relay = makeRelayHandle();
      entries.set("ws-1", { ws, relayHandle: relay, instanceId: "inst-1" });

      const msg = { type: "prompt", text: "hello" };
      const result = routeToRelay("ws-1", msg);
      expect(result.sent).toBe(true);
      expect(relay.sentMessages).toEqual([msg]);
    });

    test("连接不存在时返回 false", () => {
      const result = routeToRelay("nonexistent", { type: "prompt" });
      expect(result.sent).toBe(false);
    });
  });

  describe("flush pending 消息回放", () => {
    test("pending 消息回放跳过 connect 类型", () => {
      const ws = makeWs();
      const relay = makeRelayHandle();

      const pending = [
        { type: "connect" },
        { type: "prompt", text: "hello" },
        { type: "connect" },
        { type: "data", value: 42 },
      ];

      // 模拟 flush 逻辑
      for (const msg of pending) {
        if (msg.type === "connect") continue;
        relay.send(msg as { type: string; payload?: unknown });
      }

      expect(relay.sentMessages.length).toBe(2);
      expect(relay.sentMessages[0].type).toBe("prompt");
      expect(relay.sentMessages[1].type).toBe("data");
    });

    test("空 pending 列表不发送任何消息", () => {
      const relay = makeRelayHandle();
      const pending: Array<Record<string, unknown>> = [];
      for (const msg of pending) {
        if (msg.type === "connect") continue;
        relay.send(msg as { type: string; payload?: unknown });
      }
      expect(relay.sentMessages.length).toBe(0);
    });

    test("全是 connect 消息时不发送", () => {
      const relay = makeRelayHandle();
      const pending = [{ type: "connect" }, { type: "connect" }];
      for (const msg of pending) {
        if (msg.type === "connect") continue;
        relay.send(msg as { type: string; payload?: unknown });
      }
      expect(relay.sentMessages.length).toBe(0);
    });
  });
});
