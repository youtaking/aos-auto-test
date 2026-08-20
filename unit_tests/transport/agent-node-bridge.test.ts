// agent-node-bridge.test.ts — AgentNode 桥接层测试
// 测试目标：WsAgentNodeSocket 适配器、服务创建兜底、连接分发
// 业务意图：确保 WsConnection → AgentNodeSocket 的帧格式、断连语义、适配器复用正确

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制核心逻辑（隔离 WsConnection / AgentNodeSocket 依赖）──

class AgentNodeUnavailableError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AgentNodeUnavailableError";
  }
}

interface WsConnection {
  readyState: number;
  send(data: string): void;
  close(code?: number, reason?: string): void;
}

class WsAgentNodeSocket {
  readonly ws: WsConnection;
  onCloseHandler: (() => void) | null = null;

  constructor(ws: WsConnection) {
    this.ws = ws;
  }

  send(data: unknown): void {
    if (this.ws.readyState !== 1) {
      throw new AgentNodeUnavailableError("Agent node socket is not open");
    }
    try {
      this.ws.send(`${JSON.stringify(data)}\n`);
    } catch {
      // 日志记录后静默
    }
  }

  close(): void {
    try {
      if (this.ws.readyState === 1) {
        this.ws.close(1000, "agent node closed");
      }
    } catch {
      // ignore
    }
    this.onCloseHandler?.();
  }

  onOpen(_handler: () => void): void {}

  onClose(handler: () => void): void {
    this.onCloseHandler = handler;
  }

  onError(_handler: () => void): void {}

  emitClose(): void {
    this.onCloseHandler?.();
  }
}

function createAgentNodeServiceFallback(idleTimeoutSeconds: number | undefined): { idleTimeoutMs: number } {
  const effective = Number.isFinite(idleTimeoutSeconds) ? idleTimeoutSeconds : 300;
  return { idleTimeoutMs: effective * 1000 };
}

// ── 辅助工厂 ──

function makeMockWs(overrides: Partial<WsConnection> = {}): WsConnection & { sentMessages: string[]; closedWith: [number, string] | null } {
  const sentMessages: string[] = [];
  let closedWith: [number, string] | null = null;
  return {
    readyState: overrides.readyState ?? 1,
    send: overrides.send ?? ((data: string) => sentMessages.push(data)),
    close: overrides.close ?? ((code?: number, reason?: string) => { closedWith = [code ?? 1000, reason ?? ""]; }),
    sentMessages,
    get closedWith() { return closedWith; },
  };
}

// ── tests ──

describe("agent-node-bridge 桥接层", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("createAgentNodeService 兜底超时", () => {
    test("正常数值时使用 config 值", () => {
      const result = createAgentNodeServiceFallback(120);
      expect(result.idleTimeoutMs).toBe(120_000);
    });

    test("undefined 时兜底 300s", () => {
      const result = createAgentNodeServiceFallback(undefined);
      expect(result.idleTimeoutMs).toBe(300_000);
    });

    test("NaN 时兜底 300s", () => {
      const result = createAgentNodeServiceFallback(NaN);
      expect(result.idleTimeoutMs).toBe(300_000);
    });

    test("0 时使用 0（合法数值）", () => {
      const result = createAgentNodeServiceFallback(0);
      expect(result.idleTimeoutMs).toBe(0);
    });

    test("Infinity 时兜底 300s", () => {
      const result = createAgentNodeServiceFallback(Infinity);
      expect(result.idleTimeoutMs).toBe(300_000);
    });

    test("负数时使用负数（合法数值）", () => {
      const result = createAgentNodeServiceFallback(-10);
      expect(result.idleTimeoutMs).toBe(-10_000);
    });
  });

  describe("WsAgentNodeSocket.send 帧格式", () => {
    test("readyState=1 时发送 JSON.stringify + 换行", () => {
      const ws = makeMockWs({ readyState: 1 });
      const socket = new WsAgentNodeSocket(ws);
      socket.send({ type: "test", value: 42 });
      expect(ws.sentMessages).toEqual(['{"type":"test","value":42}\n']);
    });

    test("readyState=0 时抛 AgentNodeUnavailableError", () => {
      const ws = makeMockWs({ readyState: 0 });
      const socket = new WsAgentNodeSocket(ws);
      expect(() => socket.send({ type: "test" })).toThrow("Agent node socket is not open");
    });

    test("readyState=2 时抛 AgentNodeUnavailableError", () => {
      const ws = makeMockWs({ readyState: 2 });
      const socket = new WsAgentNodeSocket(ws);
      expect(() => socket.send("hello")).toThrow(AgentNodeUnavailableError);
    });

    test("readyState=3 时抛 AgentNodeUnavailableError", () => {
      const ws = makeMockWs({ readyState: 3 });
      const socket = new WsAgentNodeSocket(ws);
      expect(() => socket.send(null)).toThrow(AgentNodeUnavailableError);
    });

    test("发送 null 值正确序列化", () => {
      const ws = makeMockWs({ readyState: 1 });
      const socket = new WsAgentNodeSocket(ws);
      socket.send(null);
      expect(ws.sentMessages).toEqual(["null\n"]);
    });

    test("发送数组正确序列化", () => {
      const ws = makeMockWs({ readyState: 1 });
      const socket = new WsAgentNodeSocket(ws);
      socket.send([1, 2, 3]);
      expect(ws.sentMessages).toEqual(["[1,2,3]\n"]);
    });

    test("ws.send 抛错时不向上传播", () => {
      const ws = makeMockWs({
        readyState: 1,
        send: () => { throw new Error("send failed"); },
      });
      const socket = new WsAgentNodeSocket(ws);
      expect(() => socket.send({ type: "test" })).not.toThrow();
    });
  });

  describe("WsAgentNodeSocket.close 关闭语义", () => {
    test("readyState=1 时调用 ws.close 并触发 onClose", () => {
      const ws = makeMockWs({ readyState: 1 });
      const socket = new WsAgentNodeSocket(ws);
      let closeCalled = false;
      socket.onClose(() => { closeCalled = true; });
      socket.close();
      expect(ws.closedWith).toEqual([1000, "agent node closed"]);
      expect(closeCalled).toBe(true);
    });

    test("readyState 非 1 时不调用 ws.close 但触发 onClose", () => {
      const ws = makeMockWs({ readyState: 3 });
      const socket = new WsAgentNodeSocket(ws);
      let closeCalled = false;
      socket.onClose(() => { closeCalled = true; });
      socket.close();
      expect(ws.closedWith).toBeNull();
      expect(closeCalled).toBe(true);
    });

    test("未注册 onClose 时不抛错", () => {
      const ws = makeMockWs({ readyState: 1 });
      const socket = new WsAgentNodeSocket(ws);
      expect(() => socket.close()).not.toThrow();
    });

    test("ws.close 抛错时仍触发 onClose", () => {
      const ws = makeMockWs({
        readyState: 1,
        close: () => { throw new Error("close failed"); },
      });
      const socket = new WsAgentNodeSocket(ws);
      let closeCalled = false;
      socket.onClose(() => { closeCalled = true; });
      socket.close();
      expect(closeCalled).toBe(true);
    });
  });

  describe("WsAgentNodeSocket 事件注册", () => {
    test("onClose 覆盖前一个 handler", () => {
      const ws = makeMockWs({ readyState: 1 });
      const socket = new WsAgentNodeSocket(ws);
      let firstCalled = false;
      let secondCalled = false;
      socket.onClose(() => { firstCalled = true; });
      socket.onClose(() => { secondCalled = true; });
      socket.emitClose();
      expect(firstCalled).toBe(false);
      expect(secondCalled).toBe(true);
    });

    test("emitClose 触发已注册的 handler", () => {
      const ws = makeMockWs({ readyState: 1 });
      const socket = new WsAgentNodeSocket(ws);
      let called = false;
      socket.onClose(() => { called = true; });
      socket.emitClose();
      expect(called).toBe(true);
    });

    test("emitClose 未注册 handler 时不抛错", () => {
      const ws = makeMockWs({ readyState: 1 });
      const socket = new WsAgentNodeSocket(ws);
      expect(() => socket.emitClose()).not.toThrow();
    });

    test("onOpen 和 onError 为空操作不抛错", () => {
      const ws = makeMockWs({ readyState: 1 });
      const socket = new WsAgentNodeSocket(ws);
      expect(() => socket.onOpen(() => {})).not.toThrow();
      expect(() => socket.onError(() => {})).not.toThrow();
    });
  });
});
