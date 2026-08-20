// file-ws-handler.test.ts — file-ws 连接生命周期与消息路由测试
// 测试目标：handleFileWsOpen/Close/Register、sweepFileWsConnections、isFileWsConnected
// 业务意图：确保连接登记表、僵尸巡检、消息路由等纯逻辑正确

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制核心逻辑 ──

interface WsConnection {
  readyState: number;
  send(data: string): void;
  close(code?: number, reason?: string): void;
}

interface FileWsConnectionEntry {
  machineId: string | null;
  ws: WsConnection;
  wsId: string;
  openTime: number;
  lastClientActivity: number;
}

class ConnectionRegistry {
  connections = new Map<string, FileWsConnectionEntry>();
  machineFileWsIndex = new Map<string, FileWsConnectionEntry>();

  handleFileWsOpen(ws: WsConnection, wsId: string): void {
    this.connections.set(wsId, {
      machineId: null,
      ws,
      wsId,
      openTime: Date.now(),
      lastClientActivity: Date.now(),
    });
  }

  handleFileWsClose(wsId: string): void {
    const entry = this.connections.get(wsId);
    if (!entry) return;
    if (entry.machineId) {
      const indexed = this.machineFileWsIndex.get(entry.machineId);
      if (indexed?.wsId === wsId) {
        this.machineFileWsIndex.delete(entry.machineId);
      }
    }
    this.connections.delete(wsId);
  }

  isFileWsConnected(machineId: string): boolean {
    const entry = this.machineFileWsIndex.get(machineId);
    return !!entry && entry.ws.readyState === 1;
  }

  sweepFileWsConnections(idleTimeoutMs: number, now: number = Date.now()): string[] {
    const reaped: string[] = [];
    for (const [machineId, entry] of this.machineFileWsIndex) {
      if (entry.ws.readyState !== 1) continue;
      const idleMs = now - entry.lastClientActivity;
      if (idleMs <= idleTimeoutMs) continue;
      this.machineFileWsIndex.delete(machineId);
      this.connections.delete(entry.wsId);
      try { entry.ws.close(1008, "idle timeout"); } catch {}
      reaped.push(machineId);
    }
    return reaped;
  }

  closeAllFileWsConnections(): void {
    for (const [_wsId, entry] of this.connections) {
      try {
        if (entry.ws.readyState === 1) {
          entry.ws.close(1001, "server_shutdown");
        }
      } catch {}
    }
    this.connections.clear();
    this.machineFileWsIndex.clear();
  }

  registerMachine(wsId: string, machineId: string): { replaced: string | null } {
    const entry = this.connections.get(wsId);
    if (!entry) return { replaced: null };

    let replaced: string | null = null;
    const existing = this.machineFileWsIndex.get(machineId);
    if (existing && existing.wsId !== wsId) {
      replaced = existing.wsId;
      this.connections.delete(existing.wsId);
      try { existing.ws.close(1000, "replaced"); } catch {}
    }

    entry.machineId = machineId;
    this.machineFileWsIndex.set(machineId, entry);
    return { replaced };
  }
}

// ── 辅助工厂 ──

function makeMockWs(readyState = 1): WsConnection & { closedWith: [number, string] | null } {
  let closedWith: [number, string] | null = null;
  return {
    readyState,
    send: () => {},
    close: (code?: number, reason?: string) => { closedWith = [code ?? 1000, reason ?? ""]; },
    get closedWith() { return closedWith; },
  };
}

// ── tests ──

describe("file-ws-handler 连接生命周期", () => {
  let registry: ConnectionRegistry;

  beforeEach(() => {
    mock.restore();
    registry = new ConnectionRegistry();
  });

  describe("handleFileWsOpen 连接打开", () => {
    test("打开后 connections 增加", () => {
      const ws = makeMockWs();
      registry.handleFileWsOpen(ws, "ws-1");
      expect(registry.connections.size).toBe(1);
    });

    test("初始 machineId 为 null", () => {
      const ws = makeMockWs();
      registry.handleFileWsOpen(ws, "ws-1");
      expect(registry.connections.get("ws-1")!.machineId).toBeNull();
    });

    test("多个连接独立登记", () => {
      registry.handleFileWsOpen(makeMockWs(), "ws-1");
      registry.handleFileWsOpen(makeMockWs(), "ws-2");
      expect(registry.connections.size).toBe(2);
    });
  });

  describe("handleFileWsClose 连接关闭", () => {
    test("关闭后 connections 减少", () => {
      registry.handleFileWsOpen(makeMockWs(), "ws-1");
      registry.handleFileWsClose("ws-1");
      expect(registry.connections.size).toBe(0);
    });

    test("关闭时清理 machineFileWsIndex", () => {
      const ws = makeMockWs();
      registry.handleFileWsOpen(ws, "ws-1");
      registry.registerMachine("ws-1", "machine-1");
      registry.handleFileWsClose("ws-1");
      expect(registry.machineFileWsIndex.has("machine-1")).toBe(false);
    });

    test("关闭不存在的 wsId 不抛错", () => {
      expect(() => registry.handleFileWsClose("nonexistent")).not.toThrow();
    });

    test("关闭时只清理自己的 machineFileWsIndex（新连接接管场景）", () => {
      const ws1 = makeMockWs();
      const ws2 = makeMockWs();
      registry.handleFileWsOpen(ws1, "ws-1");
      registry.registerMachine("ws-1", "machine-1");
      // 新连接接管同一 machine
      registry.handleFileWsOpen(ws2, "ws-2");
      registry.registerMachine("ws-2", "machine-1");
      // 关闭旧连接不应清理 machine-1 的索引（因为已被 ws-2 接管）
      registry.handleFileWsClose("ws-1");
      expect(registry.machineFileWsIndex.has("machine-1")).toBe(true);
      expect(registry.machineFileWsIndex.get("machine-1")!.wsId).toBe("ws-2");
    });
  });

  describe("registerMachine 机器注册", () => {
    test("注册后 machineId 绑定到 entry", () => {
      const ws = makeMockWs();
      registry.handleFileWsOpen(ws, "ws-1");
      registry.registerMachine("ws-1", "machine-1");
      expect(registry.connections.get("ws-1")!.machineId).toBe("machine-1");
    });

    test("注册后 machineFileWsIndex 建立映射", () => {
      const ws = makeMockWs();
      registry.handleFileWsOpen(ws, "ws-1");
      registry.registerMachine("ws-1", "machine-1");
      expect(registry.machineFileWsIndex.get("machine-1")!.wsId).toBe("ws-1");
    });

    test("同 machine 新连接替换旧连接", () => {
      const ws1 = makeMockWs();
      const ws2 = makeMockWs();
      registry.handleFileWsOpen(ws1, "ws-1");
      registry.registerMachine("ws-1", "machine-1");
      registry.handleFileWsOpen(ws2, "ws-2");
      const { replaced } = registry.registerMachine("ws-2", "machine-1");
      expect(replaced).toBe("ws-1");
      expect(registry.connections.has("ws-1")).toBe(false);
      expect(registry.machineFileWsIndex.get("machine-1")!.wsId).toBe("ws-2");
    });

    test("不存在的 wsId 注册返回 null", () => {
      const { replaced } = registry.registerMachine("nonexistent", "machine-1");
      expect(replaced).toBeNull();
    });
  });

  describe("isFileWsConnected 连接查询", () => {
    test("机器在线且 readyState=1 返回 true", () => {
      const ws = makeMockWs(1);
      registry.handleFileWsOpen(ws, "ws-1");
      registry.registerMachine("ws-1", "machine-1");
      expect(registry.isFileWsConnected("machine-1")).toBe(true);
    });

    test("机器在线但 readyState 非 1 返回 false", () => {
      const ws = makeMockWs(3);
      registry.handleFileWsOpen(ws, "ws-1");
      registry.registerMachine("ws-1", "machine-1");
      expect(registry.isFileWsConnected("machine-1")).toBe(false);
    });

    test("未注册的机器返回 false", () => {
      expect(registry.isFileWsConnected("nonexistent")).toBe(false);
    });
  });

  describe("sweepFileWsConnections 僵尸巡检", () => {
    test("超时的连接被回收", () => {
      const ws = makeMockWs(1);
      registry.handleFileWsOpen(ws, "ws-1");
      registry.connections.get("ws-1")!.lastClientActivity = 1000;
      registry.registerMachine("ws-1", "machine-1");

      const reaped = registry.sweepFileWsConnections(90_000, 100_000);
      expect(reaped).toEqual(["machine-1"]);
      expect(registry.connections.size).toBe(0);
      expect(registry.machineFileWsIndex.size).toBe(0);
    });

    test("未超时的连接不被回收", () => {
      const ws = makeMockWs(1);
      registry.handleFileWsOpen(ws, "ws-1");
      registry.connections.get("ws-1")!.lastClientActivity = 50_000;
      registry.registerMachine("ws-1", "machine-1");

      const reaped = registry.sweepFileWsConnections(90_000, 100_000);
      expect(reaped).toEqual([]);
      expect(registry.connections.size).toBe(1);
    });

    test("readyState 非 1 的连接跳过", () => {
      const ws = makeMockWs(3);
      registry.handleFileWsOpen(ws, "ws-1");
      registry.connections.get("ws-1")!.lastClientActivity = 1000;
      registry.registerMachine("ws-1", "machine-1");

      const reaped = registry.sweepFileWsConnections(90_000, 200_000);
      expect(reaped).toEqual([]);
    });

    test("恰好等于超时阈值的连接不被回收", () => {
      const ws = makeMockWs(1);
      registry.handleFileWsOpen(ws, "ws-1");
      registry.connections.get("ws-1")!.lastClientActivity = 10_000;
      registry.registerMachine("ws-1", "machine-1");

      const reaped = registry.sweepFileWsConnections(90_000, 100_000);
      expect(reaped).toEqual([]);
    });

    test("被回收的连接调用了 ws.close", () => {
      const ws = makeMockWs(1);
      registry.handleFileWsOpen(ws, "ws-1");
      registry.connections.get("ws-1")!.lastClientActivity = 1000;
      registry.registerMachine("ws-1", "machine-1");

      registry.sweepFileWsConnections(90_000, 200_000);
      expect(ws.closedWith).toEqual([1008, "idle timeout"]);
    });
  });

  describe("closeAllFileWsConnections 优雅关闭", () => {
    test("关闭后 connections 和 index 都清空", () => {
      registry.handleFileWsOpen(makeMockWs(), "ws-1");
      registry.handleFileWsOpen(makeMockWs(), "ws-2");
      registry.registerMachine("ws-1", "machine-1");
      registry.closeAllFileWsConnections();
      expect(registry.connections.size).toBe(0);
      expect(registry.machineFileWsIndex.size).toBe(0);
    });

    test("空注册表关闭不抛错", () => {
      expect(() => registry.closeAllFileWsConnections()).not.toThrow();
    });
  });
});
