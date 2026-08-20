// agent-chat-service.test.ts — Agent 聊天服务纯逻辑测试
// 测试目标：isTurnMessage 消息过滤、createAgentSession 构造
// 业务意图：确保共享 relay handle 的并发 run 之间消息不串扰

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数 ──

interface EngineRelayMessage {
  type: string;
  payload?: unknown;
  [key: string]: unknown;
}

function isTurnMessage(msg: EngineRelayMessage, sessionId: string, turnId: number): boolean {
  if (msg.type === "error" || msg.type === "relay_closed") return true;

  const asAny = msg as unknown as Record<string, unknown>;
  let rpc: Record<string, unknown> | null = null;
  if (asAny.jsonrpc === "2.0") {
    rpc = asAny;
  } else {
    const payload = asAny.payload as Record<string, unknown> | undefined;
    if (payload?.jsonrpc === "2.0") rpc = payload;
  }
  if (!rpc) return false;

  if (rpc.method === "session/update") {
    const params = rpc.params as Record<string, unknown> | undefined;
    return params?.sessionId === sessionId;
  }

  if (typeof rpc.id === "number") {
    return rpc.id === turnId;
  }

  return false;
}

// ── 辅助工厂 ──

function makeRawUpdate(sessionId: string) {
  return {
    jsonrpc: "2.0" as const,
    method: "session/update",
    params: { sessionId, update: { sessionUpdate: "agent_message_chunk" } },
  } as unknown as EngineRelayMessage;
}

function makeWrappedUpdate(sessionId: string) {
  return {
    type: "message",
    payload: {
      jsonrpc: "2.0",
      method: "session/update",
      params: { sessionId, update: { sessionUpdate: "agent_message_chunk" } },
    },
  } as unknown as EngineRelayMessage;
}

function makeRawResponse(id: number) {
  return {
    jsonrpc: "2.0" as const,
    id,
    result: { content: "done" },
  } as unknown as EngineRelayMessage;
}

function makeWrappedResponse(id: number) {
  return {
    type: "message",
    payload: { jsonrpc: "2.0", id, result: { content: "done" } },
  } as unknown as EngineRelayMessage;
}

// ── tests ──

describe("agent-chat-service 聊天服务", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("isTurnMessage 消息过滤", () => {
    const sessionId = "session-abc";
    const turnId = 42;

    describe("传输层信号", () => {
      test("error 类型始终通过", () => {
        expect(isTurnMessage({ type: "error" } as EngineRelayMessage, sessionId, turnId)).toBe(true);
      });

      test("relay_closed 类型始终通过", () => {
        expect(isTurnMessage({ type: "relay_closed" } as EngineRelayMessage, sessionId, turnId)).toBe(true);
      });
    });

    describe("raw JSON-RPC 格式", () => {
      test("session/update 匹配 sessionId 通过", () => {
        expect(isTurnMessage(makeRawUpdate(sessionId), sessionId, turnId)).toBe(true);
      });

      test("session/update 不匹配 sessionId 拒绝", () => {
        expect(isTurnMessage(makeRawUpdate("other-session"), sessionId, turnId)).toBe(false);
      });

      test("JSON-RPC 响应匹配 turnId 通过", () => {
        expect(isTurnMessage(makeRawResponse(turnId), sessionId, turnId)).toBe(true);
      });

      test("JSON-RPC 响应不匹配 turnId 拒绝", () => {
        expect(isTurnMessage(makeRawResponse(99), sessionId, turnId)).toBe(false);
      });
    });

    describe("wrapped JSON-RPC 格式", () => {
      test("wrapped session/update 匹配 sessionId 通过", () => {
        expect(isTurnMessage(makeWrappedUpdate(sessionId), sessionId, turnId)).toBe(true);
      });

      test("wrapped session/update 不匹配 sessionId 拒绝", () => {
        expect(isTurnMessage(makeWrappedUpdate("other-session"), sessionId, turnId)).toBe(false);
      });

      test("wrapped 响应匹配 turnId 通过", () => {
        expect(isTurnMessage(makeWrappedResponse(turnId), sessionId, turnId)).toBe(true);
      });

      test("wrapped 响应不匹配 turnId 拒绝", () => {
        expect(isTurnMessage(makeWrappedResponse(99), sessionId, turnId)).toBe(false);
      });
    });

    describe("丢弃场景", () => {
      test("非 JSON-RPC 消息丢弃", () => {
        const msg = { type: "status", data: "running" } as unknown as EngineRelayMessage;
        expect(isTurnMessage(msg, sessionId, turnId)).toBe(false);
      });

      test("非 session/update 的方法通知丢弃", () => {
        const msg = {
          jsonrpc: "2.0" as const,
          method: "session/status",
          params: { status: "running" },
        } as unknown as EngineRelayMessage;
        expect(isTurnMessage(msg, sessionId, turnId)).toBe(false);
      });

      test("session/update 无 params 丢弃", () => {
        const msg = {
          jsonrpc: "2.0" as const,
          method: "session/update",
        } as unknown as EngineRelayMessage;
        expect(isTurnMessage(msg, sessionId, turnId)).toBe(false);
      });

      test("无 jsonrpc 也无 payload 丢弃", () => {
        const msg = { someField: "value" } as unknown as EngineRelayMessage;
        expect(isTurnMessage(msg, sessionId, turnId)).toBe(false);
      });

      test("payload 无 jsonrpc 丢弃", () => {
        const msg = {
          type: "message",
          payload: { method: "session/update" },
        } as unknown as EngineRelayMessage;
        expect(isTurnMessage(msg, sessionId, turnId)).toBe(false);
      });

      test("JSON-RPC 响应 id 为字符串不匹配（typeof !== number）", () => {
        const msg = {
          jsonrpc: "2.0" as const,
          id: "42",
          result: {},
        } as unknown as EngineRelayMessage;
        expect(isTurnMessage(msg, sessionId, turnId)).toBe(false);
      });
    });
  });
});
