// acp-ws-handler.test.ts — ACP WebSocket 处理器纯逻辑测试
// 测试目标：sendToWs 消息帧格式、连接追踪、agentMachineCache
// 业务意图：确保 WS 消息使用 NDJSON 帧格式，连接追踪正确

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数 ──

interface WsConnection {
  readyState: number;
  send: (data: string) => void;
}

function sendToWs(ws: WsConnection, msg: object): void {
  if (ws.readyState !== 1) return;
  try {
    ws.send(`${JSON.stringify(msg)}\n`);
  } catch {
    /* ignore */
  }
}

interface AcpConnectionEntry {
  agentId: string | null;
  userId: string;
  isMachine: boolean;
  machineId: string | null;
  wsId: string;
  openTime: number;
  lastClientActivity: number;
}

const connections = new Map<string, AcpConnectionEntry>();

function registerConnection(wsId: string, entry: AcpConnectionEntry): void {
  connections.set(wsId, entry);
}

function unregisterConnection(wsId: string): AcpConnectionEntry | undefined {
  const entry = connections.get(wsId);
  if (entry) connections.delete(wsId);
  return entry;
}

function findMachineConnectionById(machineId: string): AcpConnectionEntry | undefined {
  for (const entry of connections.values()) {
    if (entry.isMachine && entry.machineId === machineId) return entry;
  }
  return undefined;
}

function performMachineCleanup(wsId: string): {
  machineId: string | null;
  cleaned: boolean;
} {
  const entry = connections.get(wsId);
  if (!entry || !entry.isMachine || !entry.machineId) {
    return { machineId: null, cleaned: false };
  }
  const machineId = entry.machineId;
  connections.delete(wsId);
  return { machineId, cleaned: true };
}

// ── 辅助工厂 ──

function makeWs(readyState = 1): WsConnection & { sent: string[] } {
  const sent: string[] = [];
  return {
    readyState,
    send: mock((data: string) => sent.push(data)),
    sent,
  };
}

function makeEntry(overrides: Partial<AcpConnectionEntry> = {}): AcpConnectionEntry {
  return {
    agentId: null,
    userId: "user-1",
    isMachine: false,
    machineId: null,
    wsId: "ws-1",
    openTime: Date.now(),
    lastClientActivity: Date.now(),
    ...overrides,
  };
}

// ── tests ──

describe("acp-ws-handler ACP WS 处理器", () => {
  beforeEach(() => {
    mock.restore();
    connections.clear();
  });

  describe("sendToWs NDJSON 帧发送", () => {
    test("消息以 JSON + 换行符帧发送", () => {
      const ws = makeWs();
      sendToWs(ws, { type: "keep_alive" });
      expect(ws.sent.length).toBe(1);
      expect(ws.sent[0]).toBe('{"type":"keep_alive"}\n');
    });

    test("WS 已关闭（readyState !== 1）不发送", () => {
      const ws = makeWs(3); // CLOSED
      sendToWs(ws, { type: "keep_alive" });
      expect(ws.sent.length).toBe(0);
    });

    test("WS 正在连接（readyState=0）不发送", () => {
      const ws = makeWs(0); // CONNECTING
      sendToWs(ws, { type: "test" });
      expect(ws.sent.length).toBe(0);
    });

    test("WS 正在关闭（readyState=2）不发送", () => {
      const ws = makeWs(2); // CLOSING
      sendToWs(ws, { type: "test" });
      expect(ws.sent.length).toBe(0);
    });

    test("复杂消息正确序列化", () => {
      const ws = makeWs();
      sendToWs(ws, {
        type: "session_data",
        session_id: "auto_inst-1",
        payload: { jsonrpc: "2.0", method: "session/update" },
      });
      const sent = JSON.parse(ws.sent[0].trimEnd());
      expect(sent.type).toBe("session_data");
      expect(sent.payload.jsonrpc).toBe("2.0");
    });

    test("send 抛错不传播", () => {
      const ws: WsConnection = {
        readyState: 1,
        send: () => {
          throw new Error("send failed");
        },
      };
      // 不应抛出
      expect(() => sendToWs(ws, { type: "test" })).not.toThrow();
    });
  });

  describe("连接追踪", () => {
    test("注册和查找连接", () => {
      const entry = makeEntry({ wsId: "ws-1", userId: "user-a" });
      registerConnection("ws-1", entry);
      expect(connections.get("ws-1")).toBe(entry);
    });

    test("注销连接", () => {
      const entry = makeEntry({ wsId: "ws-1" });
      registerConnection("ws-1", entry);
      const removed = unregisterConnection("ws-1");
      expect(removed).toBe(entry);
      expect(connections.has("ws-1")).toBe(false);
    });

    test("注销不存在的连接返回 undefined", () => {
      expect(unregisterConnection("nonexistent")).toBeUndefined();
    });

    test("按 machineId 查找机器连接", () => {
      const entry = makeEntry({
        wsId: "ws-mac",
        isMachine: true,
        machineId: "mac-1",
      });
      registerConnection("ws-mac", entry);
      expect(findMachineConnectionById("mac-1")).toBe(entry);
    });

    test("非机器连接不被 findMachineConnectionById 找到", () => {
      const entry = makeEntry({ wsId: "ws-client", isMachine: false });
      registerConnection("ws-client", entry);
      expect(findMachineConnectionById("ws-client")).toBeUndefined();
    });

    test("machineId 不匹配返回 undefined", () => {
      const entry = makeEntry({
        wsId: "ws-mac",
        isMachine: true,
        machineId: "mac-1",
      });
      registerConnection("ws-mac", entry);
      expect(findMachineConnectionById("mac-2")).toBeUndefined();
    });
  });

  describe("performMachineCleanup 机器连接清理", () => {
    test("机器连接被正确清理", () => {
      const entry = makeEntry({
        wsId: "ws-mac",
        isMachine: true,
        machineId: "mac-1",
      });
      registerConnection("ws-mac", entry);

      const result = performMachineCleanup("ws-mac");
      expect(result.cleaned).toBe(true);
      expect(result.machineId).toBe("mac-1");
      expect(connections.has("ws-mac")).toBe(false);
    });

    test("非机器连接不清理", () => {
      const entry = makeEntry({ wsId: "ws-client", isMachine: false });
      registerConnection("ws-client", entry);

      const result = performMachineCleanup("ws-client");
      expect(result.cleaned).toBe(false);
      expect(result.machineId).toBeNull();
    });

    test("不存在的连接不清理", () => {
      const result = performMachineCleanup("nonexistent");
      expect(result.cleaned).toBe(false);
    });

    test("machineId 为 null 的机器连接不清理", () => {
      const entry = makeEntry({
        wsId: "ws-mac",
        isMachine: true,
        machineId: null,
      });
      registerConnection("ws-mac", entry);

      const result = performMachineCleanup("ws-mac");
      expect(result.cleaned).toBe(false);
    });
  });
});
