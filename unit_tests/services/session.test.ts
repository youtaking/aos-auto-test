// session.test.ts — EventBus 会话状态管理测试
// 测试目标：updateSessionStatus / archiveSession / getSession / resolveExistingSessionId
// 业务意图：验证 RCS 侧 SSE/EventBus 的最小会话接口正确性
// 方法：使用 session.ts 自带的 DI 注入点（_setEventService / _setUuid）避免 mock.module 路径歧义

import { describe, expect, test, beforeEach, mock } from "bun:test";

import {
  updateSessionStatus,
  archiveSession,
  getSession,
  resolveExistingSessionId,
  _setEventService,
  _setUuid,
} from "@fenix/services/session";

// ── 测试替身 ──

let uuidCounter = 0;
function fakeUuid(): string {
  return `mock-uuid-${++uuidCounter}`;
}

let mockBuses: Map<string, { publish: ReturnType<typeof mock> }>;
let mockRemoveBus: ReturnType<typeof mock>;

function createMockBus(): { publish: ReturnType<typeof mock> } {
  return { publish: mock(() => {}) };
}

describe("session 管理", () => {
  beforeEach(() => {
    mock.restore();
    uuidCounter = 0;
    mockBuses = new Map();
    mockRemoveBus = mock((sessionId: string) => {
      mockBuses.delete(sessionId);
    });

    _setUuid(fakeUuid);
    _setEventService({
      getAllBuses: () => mockBuses,
      removeBus: mockRemoveBus,
    } as any);
  });

  // ── updateSessionStatus ──

  describe("updateSessionStatus", () => {
    test("向活跃会话的 bus 发布 session_status 事件", () => {
      const bus = createMockBus();
      mockBuses.set("session-1", bus);

      updateSessionStatus("session-1", "running");

      expect(bus.publish).toHaveBeenCalledTimes(1);
      const event = bus.publish.mock.calls[0][0];
      expect(event.sessionId).toBe("session-1");
      expect(event.type).toBe("session_status");
      expect(event.payload.status).toBe("running");
      expect(event.direction).toBe("inbound");
      expect(event.id).toBe("mock-uuid-1");
    });

    test("会话无 bus 时静默返回不抛异常", () => {
      expect(() => updateSessionStatus("nonexistent", "running")).not.toThrow();
    });

    test("事件 id 由注入的 uuid 函数生成", () => {
      const bus = createMockBus();
      mockBuses.set("s-x", bus);
      updateSessionStatus("s-x", "idle");
      expect(bus.publish.mock.calls[0][0].id).toBe("mock-uuid-1");
    });
  });

  // ── archiveSession ──

  describe("archiveSession", () => {
    test("发布 archived 状态事件", () => {
      const bus = createMockBus();
      mockBuses.set("session-2", bus);

      archiveSession("session-2");

      expect(bus.publish).toHaveBeenCalledTimes(1);
      const event = bus.publish.mock.calls[0][0];
      expect(event.payload.status).toBe("archived");
      expect(event.sessionId).toBe("session-2");
      expect(event.type).toBe("session_status");
    });

    test("归档后移除 bus", () => {
      const bus = createMockBus();
      mockBuses.set("session-2", bus);

      archiveSession("session-2");

      expect(mockRemoveBus).toHaveBeenCalledWith("session-2");
      expect(mockBuses.has("session-2")).toBe(false);
    });

    test("归档不存在的会话不抛异常", () => {
      expect(() => archiveSession("nonexistent")).not.toThrow();
      expect(mockRemoveBus).toHaveBeenCalledWith("nonexistent");
    });
  });

  // ── getSession ──

  describe("getSession", () => {
    test("活跃 bus 返回 id + active 状态", async () => {
      mockBuses.set("session-3", createMockBus());

      const result = await getSession("session-3");
      expect(result).toEqual({ id: "session-3", status: "active" });
    });

    test("无 bus 时返回 null", async () => {
      const result = await getSession("nonexistent");
      expect(result).toBeNull();
    });
  });

  // ── resolveExistingSessionId ──

  describe("resolveExistingSessionId", () => {
    test("活跃 bus 返回 sessionId", async () => {
      mockBuses.set("session-4", createMockBus());

      const result = await resolveExistingSessionId("session-4");
      expect(result).toBe("session-4");
    });

    test("无 bus 时返回 null", async () => {
      const result = await resolveExistingSessionId("nonexistent");
      expect(result).toBeNull();
    });
  });
});
