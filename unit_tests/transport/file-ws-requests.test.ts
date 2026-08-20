// file-ws-requests.test.ts — file-ws 请求发送域测试
// 测试目标：BusyError、pending 管理、sendToWs、背压计数
// 业务意图：确保 pending 登记/清理/背压计数一致性，sendToWs 帧格式正确

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制核心逻辑 ──

class BusyError extends Error {
  readonly code = "busy";
  constructor(message: string) {
    super(message);
    this.name = "BusyError";
  }
}

interface WsConnection {
  readyState: number;
  send(data: string): void;
  close(code?: number, reason?: string): void;
}

function sendToWs(ws: WsConnection, msg: object): boolean {
  if (ws.readyState !== 1) return false;
  try {
    ws.send(`${JSON.stringify(msg)}\n`);
    return true;
  } catch {
    return false;
  }
}

// ── pending 管理（纯内存版） ──

interface PendingRequest {
  resolve: (result: { status: string; data?: unknown; error?: string }) => void;
  reject: (err: Error) => void;
  timer: ReturnType<typeof setTimeout>;
  wsId: string;
}

class PendingManager {
  pendingRequests = new Map<string, PendingRequest>();
  pendingPerWsId = new Map<string, number>();

  incrementPendingCount(wsId: string): void {
    this.pendingPerWsId.set(wsId, (this.pendingPerWsId.get(wsId) ?? 0) + 1);
  }

  decrementPendingCount(wsId: string): void {
    const count = this.pendingPerWsId.get(wsId);
    if (count === undefined) return;
    if (count <= 1) {
      this.pendingPerWsId.delete(wsId);
    } else {
      this.pendingPerWsId.set(wsId, count - 1);
    }
  }

  removePending(requestId: string): PendingRequest | undefined {
    const pending = this.pendingRequests.get(requestId);
    if (!pending) return undefined;
    clearTimeout(pending.timer);
    this.pendingRequests.delete(requestId);
    this.decrementPendingCount(pending.wsId);
    return pending;
  }

  rejectPendingForWsId(wsId: string, err: Error): void {
    for (const [requestId, pending] of this.pendingRequests) {
      if (pending.wsId !== wsId) continue;
      this.removePending(requestId);
      pending.reject(err);
    }
  }

  rejectAllPendingRequests(err: Error): void {
    for (const [requestId] of this.pendingRequests) {
      const pending = this.removePending(requestId);
      if (pending) {
        pending.reject(err);
      }
    }
    this.pendingPerWsId.clear();
  }

  addPending(requestId: string, wsId: string, resolve: any, reject: any): void {
    const timer = setTimeout(() => {}, 60000);
    this.pendingRequests.set(requestId, { resolve, reject, timer, wsId });
    this.incrementPendingCount(wsId);
  }
}

// ── 辅助工厂 ──

function makeMockWs(readyState = 1): WsConnection & { sentMessages: string[] } {
  const sentMessages: string[] = [];
  return {
    readyState,
    send: (data: string) => sentMessages.push(data),
    close: () => {},
    sentMessages,
  };
}

// ── tests ──

describe("file-ws-requests 请求发送域", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("BusyError", () => {
    test("code 属性为 'busy'", () => {
      const err = new BusyError("test");
      expect(err.code).toBe("busy");
    });

    test("name 属性为 'BusyError'", () => {
      const err = new BusyError("test");
      expect(err.name).toBe("BusyError");
    });

    test("message 正确传递", () => {
      const err = new BusyError("per-connection limit reached");
      expect(err.message).toBe("per-connection limit reached");
    });

    test("instanceof Error 为 true", () => {
      const err = new BusyError("test");
      expect(err instanceof Error).toBe(true);
    });

    test("instanceof BusyError 为 true", () => {
      const err = new BusyError("test");
      expect(err instanceof BusyError).toBe(true);
    });
  });

  describe("sendToWs 帧发送", () => {
    test("readyState=1 时发送 JSON + 换行", () => {
      const ws = makeMockWs(1);
      const result = sendToWs(ws, { type: "registered" });
      expect(result).toBe(true);
      expect(ws.sentMessages).toEqual(['{"type":"registered"}\n']);
    });

    test("readyState=0 时静默丢弃", () => {
      const ws = makeMockWs(0);
      const result = sendToWs(ws, { type: "test" });
      expect(result).toBe(false);
      expect(ws.sentMessages).toEqual([]);
    });

    test("readyState=2 时静默丢弃", () => {
      const ws = makeMockWs(2);
      const result = sendToWs(ws, { type: "test" });
      expect(result).toBe(false);
    });

    test("readyState=3 时静默丢弃", () => {
      const ws = makeMockWs(3);
      const result = sendToWs(ws, { type: "test" });
      expect(result).toBe(false);
    });

    test("ws.send 抛错时不传播", () => {
      const ws: WsConnection = {
        readyState: 1,
        send: () => { throw new Error("send error"); },
        close: () => {},
      };
      expect(() => sendToWs(ws, { type: "test" })).not.toThrow();
    });

    test("复杂对象正确序列化", () => {
      const ws = makeMockWs(1);
      sendToWs(ws, { type: "file_op", request_id: "req_1", params: { path: "/test" } });
      expect(ws.sentMessages[0]).toBe('{"type":"file_op","request_id":"req_1","params":{"path":"/test"}}\n');
    });
  });

  describe("PendingManager 背压管理", () => {
    let pm: PendingManager;

    beforeEach(() => {
      pm = new PendingManager();
    });

    test("addPending 后 pendingRequests 增加", () => {
      pm.addPending("req-1", "ws-1", () => {}, () => {});
      expect(pm.pendingRequests.size).toBe(1);
    });

    test("addPending 后 pendingPerWsId 计数递增", () => {
      pm.addPending("req-1", "ws-1", () => {}, () => {});
      pm.addPending("req-2", "ws-1", () => {}, () => {});
      expect(pm.pendingPerWsId.get("ws-1")).toBe(2);
    });

    test("不同 wsId 独立计数", () => {
      pm.addPending("req-1", "ws-1", () => {}, () => {});
      pm.addPending("req-2", "ws-2", () => {}, () => {});
      expect(pm.pendingPerWsId.get("ws-1")).toBe(1);
      expect(pm.pendingPerWsId.get("ws-2")).toBe(1);
    });

    test("removePending 清理定时器并递减计数", () => {
      pm.addPending("req-1", "ws-1", () => {}, () => {});
      pm.addPending("req-2", "ws-1", () => {}, () => {});
      pm.removePending("req-1");
      expect(pm.pendingRequests.size).toBe(1);
      expect(pm.pendingPerWsId.get("ws-1")).toBe(1);
    });

    test("removePending 计数归零时删除 wsId 键", () => {
      pm.addPending("req-1", "ws-1", () => {}, () => {});
      pm.removePending("req-1");
      expect(pm.pendingPerWsId.has("ws-1")).toBe(false);
    });

    test("removePending 不存在的 requestId 返回 undefined", () => {
      expect(pm.removePending("nonexistent")).toBeUndefined();
    });

    test("rejectPendingForWsId 只 reject 指定 wsId 的 pending", () => {
      const errors: Error[] = [];
      pm.addPending("req-1", "ws-1", () => {}, (err: Error) => errors.push(err));
      pm.addPending("req-2", "ws-2", () => {}, (err: Error) => errors.push(err));
      pm.addPending("req-3", "ws-1", () => {}, (err: Error) => errors.push(err));

      pm.rejectPendingForWsId("ws-1", new Error("disconnected"));
      expect(errors.length).toBe(2);
      expect(pm.pendingRequests.size).toBe(1);
      expect(pm.pendingRequests.has("req-2")).toBe(true);
    });

    test("rejectAllPendingRequests reject 全部并清理计数", () => {
      const errors: Error[] = [];
      pm.addPending("req-1", "ws-1", () => {}, (err: Error) => errors.push(err));
      pm.addPending("req-2", "ws-2", () => {}, (err: Error) => errors.push(err));
      pm.addPending("req-3", "ws-1", () => {}, (err: Error) => errors.push(err));

      pm.rejectAllPendingRequests(new Error("shutdown"));
      expect(errors.length).toBe(3);
      expect(pm.pendingRequests.size).toBe(0);
      expect(pm.pendingPerWsId.size).toBe(0);
    });

    test("decrementPendingCount 不存在的 wsId 不抛错", () => {
      expect(() => pm.decrementPendingCount("nonexistent")).not.toThrow();
    });
  });
});
