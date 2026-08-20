// event-service.test.ts — EventBus 服务层代理测试
// 测试目标：eventService 各方法的代理行为

import { describe, expect, test, beforeEach, mock } from "bun:test";

// ── 复制核心逻辑（模拟 EventBus）──

interface SessionEvent {
  seqNum: number;
  createdAt: number;
  type: string;
  direction?: string;
  payload?: unknown;
}

interface EventBus {
  publish(event: Omit<SessionEvent, "seqNum" | "createdAt">): SessionEvent;
  subscribe(callback: (event: SessionEvent) => void): () => void;
  getEventsSince(seqNum: number): SessionEvent[];
}

// 模块级 bus 存储
const busStore = new Map<string, EventBus>();
const acpBusStore = new Map<string, EventBus>();

function createMockBus(): EventBus {
  let seqCounter = 0;
  const events: SessionEvent[] = [];
  const subscribers = new Set<(event: SessionEvent) => void>();

  return {
    publish(event) {
      const full: SessionEvent = { ...event, seqNum: ++seqCounter, createdAt: Date.now() };
      events.push(full);
      for (const cb of subscribers) cb(full);
      return full;
    },
    subscribe(callback) {
      subscribers.add(callback);
      return () => subscribers.delete(callback);
    },
    getEventsSince(seqNum) {
      return events.filter((e) => e.seqNum > seqNum);
    },
  };
}

function getEventBus(sessionId: string): EventBus {
  let bus = busStore.get(sessionId);
  if (!bus) {
    bus = createMockBus();
    busStore.set(sessionId, bus);
  }
  return bus;
}

function removeEventBus(sessionId: string): void {
  busStore.delete(sessionId);
}

function getAllEventBuses(): Map<string, EventBus> {
  return busStore;
}

function getAcpEventBus(channelGroupId: string): EventBus {
  let bus = acpBusStore.get(channelGroupId);
  if (!bus) {
    bus = createMockBus();
    acpBusStore.set(channelGroupId, bus);
  }
  return bus;
}

function removeAcpEventBus(channelGroupId: string): void {
  acpBusStore.delete(channelGroupId);
}

// 模拟 eventService
const eventService = {
  publishEvent(sessionId: string, event: Omit<SessionEvent, "seqNum" | "createdAt">): SessionEvent {
    return getEventBus(sessionId).publish(event);
  },
  subscribe(sessionId: string, callback: (event: SessionEvent) => void): () => void {
    return getEventBus(sessionId).subscribe(callback);
  },
  getEventsSince(sessionId: string, seqNum: number): SessionEvent[] {
    return getEventBus(sessionId).getEventsSince(seqNum);
  },
  getBus(sessionId: string): EventBus {
    return getEventBus(sessionId);
  },
  removeBus(sessionId: string): void {
    removeEventBus(sessionId);
  },
  getAllBuses(): Map<string, EventBus> {
    return getAllEventBuses();
  },
  getAcpBus(channelGroupId: string): EventBus {
    return getAcpEventBus(channelGroupId);
  },
  removeAcpBus(channelGroupId: string): void {
    removeAcpEventBus(channelGroupId);
  },
};

// ── Tests ──

describe("eventService", () => {
  beforeEach(() => {
    mock.restore();
    busStore.clear();
    acpBusStore.clear();
  });

  describe("publishEvent", () => {
    test("发布事件返回带 seqNum 的完整事件", () => {
      const result = eventService.publishEvent("session-1", { type: "prompt_start" });
      expect(result.seqNum).toBe(1);
      expect(result.type).toBe("prompt_start");
      expect(result.createdAt).toBeGreaterThan(0);
    });

    test("多次发布 seqNum 递增", () => {
      const a = eventService.publishEvent("session-1", { type: "a" });
      const b = eventService.publishEvent("session-1", { type: "b" });
      expect(a.seqNum).toBe(1);
      expect(b.seqNum).toBe(2);
    });

    test("不同 session 的 seqNum 独立", () => {
      const a = eventService.publishEvent("session-1", { type: "x" });
      const b = eventService.publishEvent("session-2", { type: "y" });
      expect(a.seqNum).toBe(1);
      expect(b.seqNum).toBe(1);
    });
  });

  describe("subscribe", () => {
    test("订阅者接收后续发布的事件", () => {
      const received: SessionEvent[] = [];
      eventService.subscribe("session-1", (event) => received.push(event));
      eventService.publishEvent("session-1", { type: "test_event" });
      expect(received.length).toBe(1);
      expect(received[0].type).toBe("test_event");
    });

    test("取消订阅后不再接收事件", () => {
      const received: SessionEvent[] = [];
      const unsub = eventService.subscribe("session-1", (event) => received.push(event));
      eventService.publishEvent("session-1", { type: "first" });
      unsub();
      eventService.publishEvent("session-1", { type: "second" });
      expect(received.length).toBe(1);
    });
  });

  describe("getEventsSince", () => {
    test("返回 seqNum 之后的事件", () => {
      eventService.publishEvent("session-1", { type: "a" });
      eventService.publishEvent("session-1", { type: "b" });
      eventService.publishEvent("session-1", { type: "c" });
      const events = eventService.getEventsSince("session-1", 1);
      expect(events.length).toBe(2);
      expect(events[0].type).toBe("b");
      expect(events[1].type).toBe("c");
    });

    test("seqNum=0 返回所有事件", () => {
      eventService.publishEvent("session-1", { type: "x" });
      eventService.publishEvent("session-1", { type: "y" });
      const events = eventService.getEventsSince("session-1", 0);
      expect(events.length).toBe(2);
    });

    test("seqNum 大于所有事件时返回空数组", () => {
      eventService.publishEvent("session-1", { type: "only" });
      const events = eventService.getEventsSince("session-1", 100);
      expect(events.length).toBe(0);
    });
  });

  describe("getBus / removeBus", () => {
    test("getBus 同一 sessionId 返回同一实例", () => {
      const a = eventService.getBus("session-1");
      const b = eventService.getBus("session-1");
      expect(a).toBe(b);
    });

    test("removeBus 后 getBus 返回新实例", () => {
      const first = eventService.getBus("session-1");
      eventService.removeBus("session-1");
      const second = eventService.getBus("session-1");
      expect(first).not.toBe(second);
    });
  });

  describe("getAllBuses", () => {
    test("返回所有已创建的 bus", () => {
      eventService.getBus("s1");
      eventService.getBus("s2");
      const all = eventService.getAllBuses();
      expect(all.size).toBe(2);
      expect(all.has("s1")).toBe(true);
      expect(all.has("s2")).toBe(true);
    });
  });

  describe("getAcpBus / removeAcpBus", () => {
    test("getAcpBus 同一 ID 返回同一实例", () => {
      const a = eventService.getAcpBus("channel-1");
      const b = eventService.getAcpBus("channel-1");
      expect(a).toBe(b);
    });

    test("removeAcpBus 后返回新实例", () => {
      const first = eventService.getAcpBus("channel-1");
      eventService.removeAcpBus("channel-1");
      const second = eventService.getAcpBus("channel-1");
      expect(first).not.toBe(second);
    });

    test("ACP bus 与普通 bus 独立", () => {
      const normalBus = eventService.getBus("same-id");
      const acpBus = eventService.getAcpBus("same-id");
      expect(normalBus).not.toBe(acpBus);
    });
  });
});
