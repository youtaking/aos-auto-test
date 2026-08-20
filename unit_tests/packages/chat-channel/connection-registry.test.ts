// connection-registry.test.ts — 连接注册表测试
// 测试目标：ConnectionRegistry 的 pending/active 连接管理、配额检查、rcsSessionId 隔离遍历
// 业务意图：确保 WebSocket 连接生命周期管理正确，广播隔离到同一 rcsSessionId

import { describe, test, expect, beforeEach } from "bun:test";

// ── 复制核心逻辑（简化自 packages/chat-channel/src/channel/connection-registry.ts）──

interface ClientConnection {
  wsId: string;
  agentId: string;
  instanceId: string;
  userId: string;
  rcsSessionId: string;
  acpSessionId: string | null;
  agentStatusReceived: boolean;
  relayReady: boolean;
  pendingMessages: string[];
  ws: { close(code?: number, reason?: string): void };
  relayHandle?: { close?(code?: number, reason?: string): void } | null;
  keepalive: ReturnType<typeof setInterval>;
}

interface SharedRelay {
  instanceId: string;
  userId: string;
  rcsSessionId: string;
  refCount: number;
}

class ConnectionRegistry {
  private readonly clients = new Map<string, ClientConnection>();
  private readonly pendingBuffers = new Map<string, string[]>();
  private readonly sharedRelays = new Map<string, SharedRelay>();

  get clientCount(): number { return this.clients.size; }

  createPending(wsId: string): void { this.pendingBuffers.set(wsId, []); }

  tryCreatePending(wsId: string, maxClients: number): boolean {
    if (this.clients.size + this.pendingBuffers.size >= maxClients) return false;
    this.createPending(wsId);
    return true;
  }

  canPromotePending(wsId: string, maxClients: number): boolean {
    return this.pendingBuffers.has(wsId) && this.clients.size < maxClients;
  }

  bufferPending(wsId: string, message: string): void {
    const pending = this.pendingBuffers.get(wsId);
    if (pending) { pending.push(message); return; }
    const client = this.clients.get(wsId);
    if (client && !client.relayReady) client.pendingMessages.push(message);
  }

  consumePending(wsId: string): string[] | undefined {
    const client = this.clients.get(wsId);
    if (client) {
      if (client.pendingMessages.length === 0) return;
      return client.pendingMessages.splice(0);
    }
    const pending = this.pendingBuffers.get(wsId);
    this.pendingBuffers.delete(wsId);
    return pending;
  }

  addClient(wsId: string, client: ClientConnection): void {
    const pending = this.consumePending(wsId);
    if (pending?.length) client.pendingMessages.push(...pending);
    this.clients.set(wsId, client);
  }

  getClient(wsId: string): ClientConnection | undefined { return this.clients.get(wsId); }
  removeClient(wsId: string): ClientConnection | undefined {
    const c = this.clients.get(wsId); this.clients.delete(wsId); return c;
  }

  forEachByRcsSession(rcsSessionId: string, cb: (c: ClientConnection) => void): void {
    for (const c of this.clients.values()) { if (c.rcsSessionId === rcsSessionId) cb(c); }
  }

  findActiveSessionIdByRcsSession(rcsSessionId: string): string | undefined {
    for (const c of this.clients.values()) { if (c.rcsSessionId === rcsSessionId) return c.acpSessionId ?? undefined; }
    return;
  }

  private makeRelayKey(instanceId: string, userId: string, rcsSessionId: string): string {
    return `${instanceId}:${userId}:${rcsSessionId}`;
  }

  addShared(shared: SharedRelay): void {
    this.sharedRelays.set(this.makeRelayKey(shared.instanceId, shared.userId, shared.rcsSessionId), shared);
  }

  release(instanceId: string, userId: string, rcsSessionId: string): SharedRelay | undefined {
    const key = this.makeRelayKey(instanceId, userId, rcsSessionId);
    const shared = this.sharedRelays.get(key);
    if (!shared) return;
    shared.refCount--;
    if (shared.refCount > 0) return;
    this.sharedRelays.delete(key);
    return shared;
  }

  closeAll(code?: number, reason?: string): void {
    for (const [, client] of this.clients) {
      try { client.relayHandle?.close?.(code ?? 1001, reason ?? "server_shutdown"); } catch { /* ignore */ }
      clearInterval(client.keepalive);
    }
    this.clients.clear();
  }
}

function makeClient(overrides?: Partial<ClientConnection>): ClientConnection {
  return {
    wsId: "ws-1",
    agentId: "agent-1",
    instanceId: "i-1",
    userId: "u-1",
    rcsSessionId: "rcs-1",
    acpSessionId: null,
    agentStatusReceived: false,
    relayReady: true,
    pendingMessages: [],
    ws: { close() {} },
    keepalive: setInterval(() => {}, 60000),
    ...overrides,
  };
}

// ── 测试 ──

describe("ConnectionRegistry", () => {
  let registry: ConnectionRegistry;

  beforeEach(() => {
    registry = new ConnectionRegistry();
  });

  describe("clientCount / addClient / removeClient", () => {
    test("正向 - 空注册表 count=0", () => {
      expect(registry.clientCount).toBe(0);
    });

    test("正向 - addClient 后 count+1", () => {
      registry.addClient("ws-1", makeClient());
      expect(registry.clientCount).toBe(1);
    });

    test("正向 - removeClient 后 count-1", () => {
      registry.addClient("ws-1", makeClient());
      registry.removeClient("ws-1");
      expect(registry.clientCount).toBe(0);
    });

    test("正向 - getClient 返回已添加的连接", () => {
      const client = makeClient();
      registry.addClient("ws-1", client);
      expect(registry.getClient("ws-1")).toBe(client);
    });
  });

  describe("tryCreatePending / 配额", () => {
    test("正向 - 未达上限时返回 true", () => {
      expect(registry.tryCreatePending("ws-1", 10)).toBe(true);
    });

    test("分支 - 达上限时返回 false", () => {
      registry.addClient("ws-1", makeClient());
      expect(registry.tryCreatePending("ws-2", 1)).toBe(false);
    });
  });

  describe("bufferPending / consumePending", () => {
    test("正向 - pending 阶段缓冲消息", () => {
      registry.createPending("ws-1");
      registry.bufferPending("ws-1", "hello");
      registry.bufferPending("ws-1", "world");
      const msgs = registry.consumePending("ws-1");
      expect(msgs).toEqual(["hello", "world"]);
    });

    test("正向 - addClient 时转移 pending 消息", () => {
      registry.createPending("ws-1");
      registry.bufferPending("ws-1", "msg-1");
      const client = makeClient();
      registry.addClient("ws-1", client);
      expect(client.pendingMessages).toEqual(["msg-1"]);
    });

    test("正向 - active 阶段缓冲到 pendingMessages（relayReady=false）", () => {
      const client = makeClient({ relayReady: false });
      registry.addClient("ws-1", client);
      registry.bufferPending("ws-1", "buffered");
      expect(client.pendingMessages).toEqual(["buffered"]);
    });
  });

  describe("forEachByRcsSession", () => {
    test("正向 - 只遍历同一 rcsSessionId 的连接", () => {
      registry.addClient("ws-1", makeClient({ wsId: "ws-1", rcsSessionId: "rcs-1" }));
      registry.addClient("ws-2", makeClient({ wsId: "ws-2", rcsSessionId: "rcs-2" }));
      registry.addClient("ws-3", makeClient({ wsId: "ws-3", rcsSessionId: "rcs-1" }));

      const found: string[] = [];
      registry.forEachByRcsSession("rcs-1", (c) => found.push(c.wsId));
      expect(found.sort()).toEqual(["ws-1", "ws-3"]);
    });
  });

  describe("findActiveSessionIdByRcsSession", () => {
    test("正向 - 返回第一个匹配的 acpSessionId", () => {
      registry.addClient("ws-1", makeClient({ rcsSessionId: "rcs-1", acpSessionId: "acp-s1" }));
      expect(registry.findActiveSessionIdByRcsSession("rcs-1")).toBe("acp-s1");
    });

    test("分支 - 无匹配返回 undefined", () => {
      expect(registry.findActiveSessionIdByRcsSession("missing")).toBeUndefined();
    });
  });

  describe("SharedRelay 引用计数", () => {
    test("正向 - release 到 0 时返回 shared", () => {
      const shared: SharedRelay = { instanceId: "i", userId: "u", rcsSessionId: "r", refCount: 1 };
      registry.addShared(shared);
      const released = registry.release("i", "u", "r");
      expect(released).toBeDefined();
      expect(released!.refCount).toBe(0);
    });

    test("分支 - refCount > 0 时 release 返回 undefined", () => {
      const shared: SharedRelay = { instanceId: "i", userId: "u", rcsSessionId: "r", refCount: 2 };
      registry.addShared(shared);
      expect(registry.release("i", "u", "r")).toBeUndefined();
      expect(shared.refCount).toBe(1);
    });

    test("分支 - 不存在的 relay release 返回 undefined", () => {
      expect(registry.release("missing", "u", "r")).toBeUndefined();
    });
  });

  describe("closeAll", () => {
    test("正向 - 清空所有连接", () => {
      registry.addClient("ws-1", makeClient({ wsId: "ws-1" }));
      registry.addClient("ws-2", makeClient({ wsId: "ws-2" }));
      registry.closeAll();
      expect(registry.clientCount).toBe(0);
    });
  });
});
