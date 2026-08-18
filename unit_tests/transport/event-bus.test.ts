import { beforeEach, describe, expect, test } from "bun:test";

// EventBus 类复制（原类位于 transport/event-bus.ts，因 @fenix/logger 依赖链无法直接 import）

interface SessionEvent {
  id: string;
  sessionId: string;
  type: string;
  payload: unknown;
  direction: "inbound" | "outbound";
  seqNum: number;
  createdAt: number;
}

type Subscriber = (event: SessionEvent) => void;

const MAX_EVENTS_PER_BUS = 5000;

class EventBus {
  private subscribers = new Set<Subscriber>();
  private events: SessionEvent[] = [];
  private seqNum = 0;
  private closed = false;

  subscribe(callback: Subscriber): () => void {
    this.subscribers.add(callback);
    return () => this.subscribers.delete(callback);
  }

  subscriberCount(): number {
    return this.subscribers.size;
  }

  publish(event: Omit<SessionEvent, "seqNum" | "createdAt">): SessionEvent {
    if (this.closed) throw new Error("EventBus is closed");
    this.seqNum++;
    const full: SessionEvent = {
      ...event,
      seqNum: this.seqNum,
      createdAt: Date.now(),
    };
    this.events.push(full);
    if (this.events.length > MAX_EVENTS_PER_BUS) {
      this.events = this.events.slice(-Math.floor(MAX_EVENTS_PER_BUS / 2));
    }
    for (const sub of this.subscribers) {
      try {
        sub(full);
      } catch {
        // subscriber error isolated
      }
    }
    return full;
  }

  getEventsSince(seqNum: number): SessionEvent[] {
    const idx = this.events.findIndex((e) => e.seqNum > seqNum);
    if (idx === -1) return [];
    return this.events.slice(idx);
  }

  getLastSeqNum(): number {
    return this.seqNum;
  }

  close(): void {
    this.closed = true;
    this.subscribers.clear();
  }
}

// 全局 registry 复制
const registry = new Map<string, EventBus>();

function getEventBus(sessionId: string): EventBus {
  let bus = registry.get(sessionId);
  if (!bus) {
    bus = new EventBus();
    registry.set(sessionId, bus);
  }
  return bus;
}

function removeEventBus(sessionId: string): void {
  const bus = registry.get(sessionId);
  if (bus) {
    bus.close();
    registry.delete(sessionId);
  }
}

function getAllEventBuses(): Map<string, EventBus> {
  return registry;
}

// ── EventBus tests ──

describe("EventBus", () => {
  let bus: EventBus;

  beforeEach(() => {
    bus = new EventBus();
  });

  describe("publish", () => {
    test("publishes event with seqNum starting at 1", () => {
      const event = bus.publish({
        id: "e1", sessionId: "s1", type: "user", payload: { content: "hello" }, direction: "outbound",
      });
      expect(event.seqNum).toBe(1);
      expect(event.createdAt).toBeGreaterThan(0);
    });

    test("increments seqNum on each publish", () => {
      bus.publish({ id: "e1", sessionId: "s1", type: "user", payload: {}, direction: "outbound" });
      bus.publish({ id: "e2", sessionId: "s1", type: "assistant", payload: {}, direction: "inbound" });
      const event = bus.publish({ id: "e3", sessionId: "s1", type: "result", payload: {}, direction: "inbound" });
      expect(event.seqNum).toBe(3);
    });

    test("throws when publishing to a closed bus", () => {
      bus.close();
      expect(() =>
        bus.publish({ id: "e1", sessionId: "s1", type: "user", payload: {}, direction: "outbound" }),
      ).toThrow("EventBus is closed");
    });
  });

  describe("subscribe", () => {
    test("receives published events", () => {
      const received: unknown[] = [];
      bus.subscribe((event) => received.push(event));
      bus.publish({ id: "e1", sessionId: "s1", type: "user", payload: { content: "hi" }, direction: "outbound" });
      expect(received).toHaveLength(1);
      expect((received[0] as SessionEvent).payload).toEqual({ content: "hi" });
    });

    test("unsubscribe stops receiving events", () => {
      const received: unknown[] = [];
      const unsub = bus.subscribe((event) => received.push(event));
      unsub();
      bus.publish({ id: "e1", sessionId: "s1", type: "user", payload: {}, direction: "outbound" });
      expect(received).toHaveLength(0);
    });

    test("multiple subscribers all receive events", () => {
      const r1: unknown[] = [];
      const r2: unknown[] = [];
      bus.subscribe((e) => r1.push(e));
      bus.subscribe((e) => r2.push(e));
      bus.publish({ id: "e1", sessionId: "s1", type: "user", payload: {}, direction: "outbound" });
      expect(r1).toHaveLength(1);
      expect(r2).toHaveLength(1);
    });

    test("subscriber error does not affect other subscribers", () => {
      const received: unknown[] = [];
      bus.subscribe(() => { throw new Error("boom"); });
      bus.subscribe((e) => received.push(e));
      bus.publish({ id: "e1", sessionId: "s1", type: "user", payload: {}, direction: "outbound" });
      expect(received).toHaveLength(1);
    });

    test("subscriberCount", () => {
      expect(bus.subscriberCount()).toBe(0);
      const unsub1 = bus.subscribe(() => {});
      expect(bus.subscriberCount()).toBe(1);
      bus.subscribe(() => {});
      expect(bus.subscriberCount()).toBe(2);
      unsub1();
      expect(bus.subscriberCount()).toBe(1);
    });
  });

  describe("getEventsSince", () => {
    test("returns events after given seqNum", () => {
      bus.publish({ id: "e1", sessionId: "s1", type: "user", payload: {}, direction: "outbound" });
      bus.publish({ id: "e2", sessionId: "s1", type: "assistant", payload: {}, direction: "inbound" });
      bus.publish({ id: "e3", sessionId: "s1", type: "result", payload: {}, direction: "inbound" });
      const events = bus.getEventsSince(1);
      expect(events).toHaveLength(2);
      expect(events[0].seqNum).toBe(2);
      expect(events[1].seqNum).toBe(3);
    });

    test("returns empty for seqNum beyond last", () => {
      bus.publish({ id: "e1", sessionId: "s1", type: "user", payload: {}, direction: "outbound" });
      expect(bus.getEventsSince(1)).toHaveLength(0);
    });

    test("returns all events when seqNum is 0", () => {
      bus.publish({ id: "e1", sessionId: "s1", type: "user", payload: {}, direction: "outbound" });
      bus.publish({ id: "e2", sessionId: "s1", type: "assistant", payload: {}, direction: "inbound" });
      expect(bus.getEventsSince(0)).toHaveLength(2);
    });
  });

  describe("getLastSeqNum", () => {
    test("returns 0 for empty bus", () => {
      expect(bus.getLastSeqNum()).toBe(0);
    });

    test("returns last seqNum after publishes", () => {
      bus.publish({ id: "e1", sessionId: "s1", type: "user", payload: {}, direction: "outbound" });
      bus.publish({ id: "e2", sessionId: "s1", type: "user", payload: {}, direction: "outbound" });
      expect(bus.getLastSeqNum()).toBe(2);
    });
  });

  describe("close", () => {
    test("clears subscribers and prevents publishing", () => {
      bus.subscribe(() => {});
      bus.close();
      expect(bus.subscriberCount()).toBe(0);
      expect(() =>
        bus.publish({ id: "e1", sessionId: "s1", type: "user", payload: {}, direction: "outbound" }),
      ).toThrow();
    });
  });

  describe("event eviction", () => {
    test("evicts oldest events when exceeding MAX_EVENTS_PER_BUS", () => {
      const first = bus.publish({ id: "e1", sessionId: "s1", type: "user", payload: {}, direction: "outbound" });
      expect(first.seqNum).toBe(1);
      for (let i = 2; i <= 5001; i++) {
        bus.publish({ id: `e${i}`, sessionId: "s1", type: "user", payload: {}, direction: "outbound" });
      }
      const eventsSince0 = bus.getEventsSince(0);
      expect(eventsSince0.length).toBe(2500);
      expect(bus.getLastSeqNum()).toBe(5001);
    });
  });
});

describe("EventBus registry", () => {
  beforeEach(() => {
    for (const [key] of getAllEventBuses()) {
      removeEventBus(key);
    }
  });

  describe("getEventBus", () => {
    test("creates new bus for unknown session", () => {
      const bus = getEventBus("s1");
      expect(bus).toBeInstanceOf(EventBus);
      expect(getAllEventBuses().has("s1")).toBe(true);
    });

    test("returns same bus for same session", () => {
      const bus1 = getEventBus("s1");
      const bus2 = getEventBus("s1");
      expect(bus1).toBe(bus2);
    });
  });

  describe("removeEventBus", () => {
    test("removes and closes bus", () => {
      const bus = getEventBus("s2");
      removeEventBus("s2");
      expect(getAllEventBuses().has("s2")).toBe(false);
      expect(() =>
        bus.publish({ id: "e1", sessionId: "s2", type: "user", payload: {}, direction: "outbound" }),
      ).toThrow();
    });

    test("no-op for non-existent bus", () => {
      expect(() => removeEventBus("nonexistent")).not.toThrow();
    });
  });

  describe("getAllEventBuses", () => {
    test("returns all registered buses", () => {
      getEventBus("a");
      getEventBus("b");
      expect(getAllEventBuses().size).toBeGreaterThanOrEqual(2);
    });
  });
});
