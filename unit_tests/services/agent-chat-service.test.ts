// agent-chat-service.test.ts — Agent 聊天服务纯逻辑测试
// 测试目标：isTurnMessage 消息过滤、生命周期信号合成、ACP 握手超时错误码
// 业务意图：确保共享 relay handle 的并发 run 之间消息不串扰，且运行时生命周期能中止请求

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

  describe("生命周期信号合成（onResolved 之后）", () => {
    // 复制 openAdmittedAgentSession 中 onResolved 之后的信号合并逻辑：
    // lifecycleSignal 存在时与请求 signal 合并，否则沿用原 signal。
    function composeLifecycleSignal(
      base: AbortSignal | undefined,
      lifecycle: AbortSignal | undefined,
    ): AbortSignal | undefined {
      if (!lifecycle) return base;
      return base ? AbortSignal.any([base, lifecycle]) : lifecycle;
    }

    test("没有生命周期信号时沿用请求 signal", () => {
      const controller = new AbortController();
      expect(composeLifecycleSignal(controller.signal, undefined)).toBe(controller.signal);
    });

    test("只有生命周期信号时直接使用它", () => {
      const lifecycle = new AbortController().signal;
      expect(composeLifecycleSignal(undefined, lifecycle)).toBe(lifecycle);
    });

    test("两者都存在时任一中止即可中止合成信号", () => {
      const request = new AbortController();
      const lifecycle = new AbortController();
      const merged = composeLifecycleSignal(request.signal, lifecycle.signal)!;
      expect(merged.aborted).toBe(false);
      lifecycle.abort(new Error("runtime died"));
      expect(merged.aborted).toBe(true);
      expect(merged.reason).toBeInstanceOf(Error);
    });

    test("请求中止同样中止合成信号", () => {
      const request = new AbortController();
      const lifecycle = new AbortController();
      const merged = composeLifecycleSignal(request.signal, lifecycle.signal)!;
      request.abort(new Error("client gone"));
      expect(merged.aborted).toBe(true);
    });

    test("合成后中止会让后续 throwIfAborted 抛错，避免继续打开会话", () => {
      const lifecycle = new AbortController();
      lifecycle.abort(new Error("instance stopped"));
      const merged = composeLifecycleSignal(undefined, lifecycle.signal)!;
      expect(() => merged.throwIfAborted()).toThrow("instance stopped");
    });
  });

  describe("onResolved 回调载荷", () => {
    interface ApiChatSessionOwner {
      organizationId: string;
      userId: string;
      agentConfigId: string;
      environmentId: string;
      instanceId: string;
      runtimeGeneration: number;
    }

    /** 复制 openAdmittedAgentSession 传给 onResolved 的对象构造。 */
    function buildResolvedOwner(
      input: { organizationId: string; userId: string },
      resolved: { agentConfigId: string; environmentId: string; instance: { id: string } },
      runtimeGeneration: number,
    ): ApiChatSessionOwner {
      return {
        organizationId: input.organizationId,
        userId: input.userId,
        agentConfigId: resolved.agentConfigId,
        environmentId: resolved.environmentId,
        instanceId: resolved.instance.id,
        runtimeGeneration,
      };
    }

    test("使用解析后的 Agent/环境身份，而不是请求入参", () => {
      const owner = buildResolvedOwner(
        { organizationId: "org-1", userId: "user-1" },
        { agentConfigId: "agent-resolved", environmentId: "env-resolved", instance: { id: "inst-1" } },
        7,
      );
      expect(owner).toEqual({
        organizationId: "org-1",
        userId: "user-1",
        agentConfigId: "agent-resolved",
        environmentId: "env-resolved",
        instanceId: "inst-1",
        runtimeGeneration: 7,
      });
    });
  });

  describe("ACP 握手超时错误码", () => {
    // 源：agent-prompt-turn.ts 中 ACP_HANDSHAKE_TIMEOUT
    const ACP_HANDSHAKE_TIMEOUT = "ACP_HANDSHAKE_TIMEOUT";

    function handshakeTimeoutError(): Error {
      return Object.assign(new Error("ACP session handshake timed out; session state is unconfirmed"), {
        code: ACP_HANDSHAKE_TIMEOUT,
      });
    }

    test("超时错误携带 ACP_HANDSHAKE_TIMEOUT 供调用方识别未确认状态", () => {
      const error = handshakeTimeoutError();
      expect(error.message).toContain("session state is unconfirmed");
      expect((error as Error & { code: string }).code).toBe("ACP_HANDSHAKE_TIMEOUT");
    });
  });
});
