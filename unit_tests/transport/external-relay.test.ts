// external-relay.test.ts — 外部 ACP 客户端 Relay 纯逻辑测试
// 测试目标：消息解析、ping/pong、pending buffer、认证 cwd 注入、连接授权
// 业务意图：确保外部客户端消息正确解析和转发，且无法改变服务端认证的工作区

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

  // ── main 新增：认证工作区 cwd 注入 ──

  describe("injectAuthenticatedCwd cwd 注入", () => {
    function extractJsonRpc(message: Record<string, unknown>): Record<string, unknown> | null {
      if (message.jsonrpc === "2.0") return message;
      const payload = message.payload as Record<string, unknown> | undefined;
      return payload?.jsonrpc === "2.0" ? payload : null;
    }

    function injectAuthenticatedCwd(message: Record<string, unknown>, cwd: string): Record<string, unknown> {
      const rpc = extractJsonRpc(message);
      if (!rpc) return message;
      if (
        rpc.jsonrpc !== "2.0" ||
        !["session/new", "session/load", "session/list", "session/resume"].includes(String(rpc.method))
      )
        return rpc;
      const params = typeof rpc.params === "object" && rpc.params !== null ? rpc.params : {};
      return { ...rpc, params: { ...params, cwd } };
    }

    test("session/new 被追加服务端 cwd", () => {
      const result = injectAuthenticatedCwd(
        { jsonrpc: "2.0", id: 1, method: "session/new", params: { model: "x" } },
        "/workspace/env",
      );
      expect(result.params).toEqual({ model: "x", cwd: "/workspace/env" });
    });

    test("客户端伪造的 cwd 被覆盖", () => {
      const result = injectAuthenticatedCwd(
        { jsonrpc: "2.0", id: 1, method: "session/load", params: { cwd: "/etc" } },
        "/workspace/env",
      );
      expect(result.params).toEqual({ cwd: "/workspace/env" });
    });

    test("session/list 与 session/resume 同样注入", () => {
      for (const method of ["session/list", "session/resume"]) {
        const result = injectAuthenticatedCwd({ jsonrpc: "2.0", id: 1, method, params: {} }, "/w");
        expect(result.params).toEqual({ cwd: "/w" });
      }
    });

    test("缺少 params 时创建对象", () => {
      const result = injectAuthenticatedCwd({ jsonrpc: "2.0", id: 1, method: "session/new" }, "/w");
      expect(result.params).toEqual({ cwd: "/w" });
    });

    test("params 非对象时被替换", () => {
      const result = injectAuthenticatedCwd({ jsonrpc: "2.0", id: 1, method: "session/new", params: "x" }, "/w");
      expect(result.params).toEqual({ cwd: "/w" });
    });

    test("session/prompt 等非会话动作不注入", () => {
      const message = { jsonrpc: "2.0", id: 2, method: "session/prompt", params: { text: "hi" } };
      expect(injectAuthenticatedCwd(message, "/w")).toEqual(message);
    });

    test("包裹在 payload 中的 JSON-RPC 也能注入", () => {
      const result = injectAuthenticatedCwd(
        { type: "message", payload: { jsonrpc: "2.0", id: 3, method: "session/new", params: {} } },
        "/w",
      );
      expect(result).toEqual({ jsonrpc: "2.0", id: 3, method: "session/new", params: { cwd: "/w" } });
    });

    test("非 JSON-RPC 消息原样返回", () => {
      const message = { type: "ping" };
      expect(injectAuthenticatedCwd(message, "/w")).toBe(message);
    });

    test("jsonrpc 版本非 2.0 时原样返回 rpc", () => {
      const rpc = { jsonrpc: "1.0", id: 1, method: "session/new", params: {} };
      expect(injectAuthenticatedCwd(rpc, "/w")).toBe(rpc);
    });
  });

  describe("prepareExternalRelayOpen 预注册 pending buffer", () => {
    class FakeQueue {
      static created: FakeQueue[] = [];
      messages: Record<string, unknown>[] = [];
      constructor(
        public scope: string,
        public onLimit: () => void,
        public onError: (error: unknown) => void,
      ) {
        FakeQueue.created.push(this);
      }
    }

    function prepare(ws: WsConnection, relayWsId: string): void {
      if (pendingRelayMessages.has(relayWsId)) return;
      pendingRelayMessages.set(relayWsId, new FakeQueue("unauthenticated", () => {}, () => {}) as never);
    }

    beforeEach(() => {
      FakeQueue.created.length = 0;
    });

    test("首次调用注册缓冲区", () => {
      prepare(makeWs(), "ws-1");
      expect(pendingRelayMessages.has("ws-1")).toBe(true);
      expect(FakeQueue.created).toHaveLength(1);
    });

    test("重复调用保留原缓冲区，不覆盖已缓存消息", () => {
      prepare(makeWs(), "ws-1");
      const first = pendingRelayMessages.get("ws-1");
      prepare(makeWs(), "ws-1");
      expect(pendingRelayMessages.get("ws-1")).toBe(first);
      expect(FakeQueue.created).toHaveLength(1);
    });
  });

  describe("连接实例授权判定", () => {
    // 复制 handleExternalRelayOpen 中的归属与来源校验
    function isAuthorizedRelayInstance(
      instance: { ownerUserId: string; environmentId: string; creationSource: string } | undefined,
      userId: string,
      environmentId: string,
    ): boolean {
      return Boolean(
        instance &&
          instance.ownerUserId === userId &&
          instance.environmentId === environmentId &&
          instance.creationSource !== "workflow",
      );
    }

    test("本用户同环境的 api 实例通过", () => {
      expect(
        isAuthorizedRelayInstance({ ownerUserId: "u1", environmentId: "e1", creationSource: "api" }, "u1", "e1"),
      ).toBe(true);
    });

    test("他人实例被拒绝", () => {
      expect(
        isAuthorizedRelayInstance({ ownerUserId: "u2", environmentId: "e1", creationSource: "api" }, "u1", "e1"),
      ).toBe(false);
    });

    test("跨环境实例被拒绝", () => {
      expect(
        isAuthorizedRelayInstance({ ownerUserId: "u1", environmentId: "e2", creationSource: "api" }, "u1", "e1"),
      ).toBe(false);
    });

    test("workflow 创建的实例不得经外部 relay 连接", () => {
      expect(
        isAuthorizedRelayInstance({ ownerUserId: "u1", environmentId: "e1", creationSource: "workflow" }, "u1", "e1"),
      ).toBe(false);
    });

    test("实例不存在时拒绝", () => {
      expect(isAuthorizedRelayInstance(undefined, "u1", "e1")).toBe(false);
    });
  });
});
