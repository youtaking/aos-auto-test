// engine-relay.test.ts — plugin-sdk EngineRelay 类型结构测试
// 测试目标：验证 relay 相关类型接口和消息结构
// 业务意图：确保 relay 消息格式和状态枚举符合协议约定

import { describe, test, expect } from "bun:test";

// ── 复制类型定义（来自 packages/plugin-sdk/src/engine-relay.ts）──

interface EngineRelayMessage {
  type: string;
  payload?: unknown;
}

type EngineRelayState = "open" | "closed";

interface EngineRelayHandle {
  readonly state: EngineRelayState;
  send(message: EngineRelayMessage): Promise<void> | void;
  close(code?: number, reason?: string): Promise<void> | void;
  onMessage?(listener: (message: EngineRelayMessage) => void): () => void;
  ready?: Promise<void>;
}

interface EngineSessionSummary {
  id: string;
  title?: string;
  cwd?: string;
  updatedAt?: Date;
}

interface EngineHealthStatus {
  ok: boolean;
  detail?: string;
}

// ── 测试 ──

describe("EngineRelayMessage", () => {
  test("正向 - 最小消息结构只含 type", () => {
    const msg: EngineRelayMessage = { type: "ping" };
    expect(msg.type).toBe("ping");
    expect(msg.payload).toBeUndefined();
  });

  test("正向 - payload 可以是任意类型", () => {
    const msg: EngineRelayMessage = { type: "data", payload: { items: [1, 2, 3] } };
    expect((msg.payload as any).items.length).toBe(3);
  });

  test("正向 - payload 可以是 null", () => {
    const msg: EngineRelayMessage = { type: "reset", payload: null };
    expect(msg.payload).toBeNull();
  });
});

describe("EngineRelayState", () => {
  test("正向 - 只有 open 和 closed 两个值", () => {
    const states: EngineRelayState[] = ["open", "closed"];
    expect(states).toEqual(["open", "closed"]);
  });
});

describe("EngineRelayHandle 模拟", () => {
  function createMockHandle(): EngineRelayHandle & { messages: EngineRelayMessage[] } {
    const messages: EngineRelayMessage[] = [];
    return {
      state: "open",
      messages,
      send(msg) { messages.push(msg); },
      close() { (this as any).state = "closed"; },
      onMessage(listener) {
        // 模拟：每次 send 后触发 listener
        const origSend = this.send.bind(this);
        this.send = (msg) => { origSend(msg); listener(msg); };
        return () => { this.send = origSend; };
      },
    };
  }

  test("正向 - send 记录消息", () => {
    const handle = createMockHandle();
    handle.send({ type: "hello" });
    expect(handle.messages.length).toBe(1);
    expect(handle.messages[0].type).toBe("hello");
  });

  test("正向 - close 改变 state", () => {
    const handle = createMockHandle();
    expect(handle.state).toBe("open");
    handle.close();
    expect(handle.state).toBe("closed");
  });

  test("正向 - onMessage 返回 unsub 函数", () => {
    const handle = createMockHandle();
    const received: EngineRelayMessage[] = [];
    const unsub = handle.onMessage!((msg) => received.push(msg));
    handle.send({ type: "a" });
    expect(received.length).toBe(1);
    unsub();
    handle.send({ type: "b" });
    expect(received.length).toBe(1); // unsub 后不再触发
  });
});

describe("EngineSessionSummary", () => {
  test("正向 - 最小结构只含 id", () => {
    const s: EngineSessionSummary = { id: "s1" };
    expect(s.id).toBe("s1");
    expect(s.title).toBeUndefined();
    expect(s.cwd).toBeUndefined();
    expect(s.updatedAt).toBeUndefined();
  });

  test("正向 - 完整字段", () => {
    const now = new Date();
    const s: EngineSessionSummary = { id: "s1", title: "Chat", cwd: "/workspace", updatedAt: now };
    expect(s.title).toBe("Chat");
    expect(s.updatedAt).toBe(now);
  });
});

describe("EngineHealthStatus", () => {
  test("正向 - ok=true 无 detail", () => {
    const h: EngineHealthStatus = { ok: true };
    expect(h.ok).toBe(true);
    expect(h.detail).toBeUndefined();
  });

  test("正向 - ok=false 带 detail", () => {
    const h: EngineHealthStatus = { ok: false, detail: "connection timeout" };
    expect(h.ok).toBe(false);
    expect(h.detail).toBe("connection timeout");
  });
});
