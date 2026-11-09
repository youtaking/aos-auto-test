// ack-timeout.test.ts — 同步 ACK 超时登记与惰性扫描测试
// 测试目标：createAckTimeoutTracker 的期限校验、幂等登记、代次冲突、边界扫描与结算指标
// 业务意图：重传不能延长 ACK 期限；同 id 换代次是调用方缺陷必须暴露；扫描只读，超期条目保留到结算或清零
// 源：packages/chat-channel/src/sync/provider/ack-timeout.ts（main a7f477a9e）

import { describe, expect, test } from "bun:test";

// ── 复制实现 ──

const MAX_IDENTIFIER_BYTES = 256;
const encoder = new TextEncoder();

class SyncProtocolError extends Error {
  constructor(
    readonly code: "MALFORMED_FRAME" | "IDENTIFIER_TOO_LONG" | "ADMISSION_REJECTED",
    options: { message: string },
  ) {
    super(options.message);
    this.name = "SyncProtocolError";
  }
}

function identifierViolation(value: string): { code: "MALFORMED_FRAME" | "IDENTIFIER_TOO_LONG"; reason: string } | null {
  if (value.length === 0) return { code: "MALFORMED_FRAME", reason: "must not be empty" };
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code <= 0x1f || (code >= 0x7f && code <= 0x9f))
      return { code: "MALFORMED_FRAME", reason: "must not contain control characters" };
  }
  const bytes = encoder.encode(value).length;
  if (bytes > MAX_IDENTIFIER_BYTES)
    return { code: "IDENTIFIER_TOO_LONG", reason: `is ${bytes} UTF-8 bytes, limit is ${MAX_IDENTIFIER_BYTES}` };
  return null;
}

function assertIdentifier(value: string, field: string): void {
  const violation = identifierViolation(value);
  if (violation !== null) throw new SyncProtocolError(violation.code, { message: `identifier "${field}" ${violation.reason}` });
}

interface Clock {
  now(): number;
}

interface AckTimeoutEntry {
  readonly deliveryId: string;
  readonly transportEpoch: string;
}

interface TrackerOptions {
  readonly clock: Clock;
  readonly ackDeadlineMs: number;
  readonly recordDuration?: (seconds: number, attributes: Record<string, string>) => void;
}

function assertPositiveInteger(value: number, field: string): number {
  if (!Number.isSafeInteger(value) || value <= 0) {
    throw new SyncProtocolError("ADMISSION_REJECTED", {
      message: `ack timeout rejected: ${field} must be a positive safe integer, received ${String(value)}`,
    });
  }
  return value;
}

function createAckTimeoutTracker(options: TrackerOptions) {
  const { clock } = options;
  const ackDeadlineMs = assertPositiveInteger(options.ackDeadlineMs, "ackDeadlineMs");
  const entries = new Map<string, { readonly transportEpoch: string; readonly trackedAt: number }>();

  return {
    track(deliveryId: string, transportEpoch: string): void {
      assertIdentifier(deliveryId, "deliveryId");
      assertIdentifier(transportEpoch, "transportEpoch");
      const existing = entries.get(deliveryId);
      if (existing !== undefined) {
        if (existing.transportEpoch !== transportEpoch) {
          throw new SyncProtocolError("MALFORMED_FRAME", {
            message:
              `ack timeout rejected: deliveryId ${deliveryId} is already tracked with transportEpoch ` +
              `${existing.transportEpoch}, received ${transportEpoch}`,
          });
        }
        return;
      }
      entries.set(deliveryId, { transportEpoch, trackedAt: clock.now() });
    },

    settle(deliveryId: string): boolean {
      assertIdentifier(deliveryId, "deliveryId");
      const entry = entries.get(deliveryId);
      if (entry)
        options.recordDuration?.(Math.max(0, clock.now() - entry.trackedAt) / 1000, {
          channel: "sync",
          message: "delivery",
        });
      return entries.delete(deliveryId);
    },

    scan(): readonly AckTimeoutEntry[] {
      const now = clock.now();
      const expired: AckTimeoutEntry[] = [];
      for (const [deliveryId, entry] of entries) {
        if (now - entry.trackedAt >= ackDeadlineMs) {
          expired.push({ deliveryId, transportEpoch: entry.transportEpoch });
        }
      }
      return expired;
    },

    outstandingCount(): number {
      return entries.size;
    },

    reset(): void {
      entries.clear();
    },
  };
}

// ── 辅助 ──

function setup(ackDeadlineMs = 30_000) {
  let now = 0;
  const recorded: Array<[number, Record<string, string>]> = [];
  const tracker = createAckTimeoutTracker({
    clock: { now: () => now },
    ackDeadlineMs,
    recordDuration: (seconds, attributes) => recorded.push([seconds, attributes]),
  });
  return {
    tracker,
    recorded,
    advance: (ms: number) => {
      now += ms;
    },
    setNow: (value: number) => {
      now = value;
    },
  };
}

// ── tests ──

describe("期限配置校验", () => {
  test("非正或非整数期限在装配期拒绝", () => {
    for (const value of [0, -1, 1.5, Number.NaN, Number.POSITIVE_INFINITY]) {
      expect(() => createAckTimeoutTracker({ clock: { now: () => 0 }, ackDeadlineMs: value })).toThrow(
        "must be a positive safe integer",
      );
      try {
        createAckTimeoutTracker({ clock: { now: () => 0 }, ackDeadlineMs: value });
      } catch (error) {
        expect((error as SyncProtocolError).code).toBe("ADMISSION_REJECTED");
      }
    }
  });
});

describe("登记与结算", () => {
  test("登记后在途计数增加，结算后减少", () => {
    const { tracker } = setup();
    tracker.track("d-1", "epoch-1");
    expect(tracker.outstandingCount()).toBe(1);
    expect(tracker.settle("d-1")).toBe(true);
    expect(tracker.outstandingCount()).toBe(0);
  });

  test("结算未登记的投递返回 false 且不记录指标", () => {
    const { tracker, recorded } = setup();
    expect(tracker.settle("missing")).toBe(false);
    expect(recorded).toEqual([]);
  });

  test("结算记录秒级耗时与固定属性", () => {
    const { tracker, recorded, advance } = setup();
    tracker.track("d-1", "epoch-1");
    advance(2500);
    tracker.settle("d-1");
    expect(recorded).toEqual([[2.5, { channel: "sync", message: "delivery" }]]);
  });

  test("时钟回退时耗时按 0 记录", () => {
    const { tracker, recorded, setNow } = setup();
    setNow(10_000);
    tracker.track("d-1", "epoch-1");
    setNow(9000);
    tracker.settle("d-1");
    expect(recorded).toEqual([[0, { channel: "sync", message: "delivery" }]]);
  });

  test("重复登记同代次不续期", () => {
    const { tracker, advance } = setup();
    tracker.track("d-1", "epoch-1");
    advance(29_000);
    tracker.track("d-1", "epoch-1");
    expect(tracker.outstandingCount()).toBe(1);
    advance(2_000);
    expect(tracker.scan()).toEqual([{ deliveryId: "d-1", transportEpoch: "epoch-1" }]);
  });

  test("同 id 换代次抛 MALFORMED_FRAME 且保留原条目", () => {
    const { tracker } = setup();
    tracker.track("d-1", "epoch-1");
    expect(() => tracker.track("d-1", "epoch-2")).toThrow("already tracked with transportEpoch epoch-1");
    expect(tracker.outstandingCount()).toBe(1);
    expect(tracker.scan()).toEqual([]);
  });
});

describe("惰性扫描", () => {
  test("恰好到期限即超期，未到不超期", () => {
    const { tracker, advance } = setup();
    tracker.track("d-1", "epoch-1");
    advance(29_999);
    expect(tracker.scan()).toEqual([]);
    advance(1);
    expect(tracker.scan()).toEqual([{ deliveryId: "d-1", transportEpoch: "epoch-1" }]);
  });

  test("按登记顺序返回超期条目", () => {
    const { tracker, advance } = setup();
    tracker.track("d-2", "epoch-1");
    tracker.track("d-1", "epoch-1");
    tracker.track("d-3", "epoch-1");
    advance(30_000);
    expect(tracker.scan().map((entry) => entry.deliveryId)).toEqual(["d-2", "d-1", "d-3"]);
  });

  test("扫描只读：条目保留且重复扫描结果稳定", () => {
    const { tracker, advance } = setup();
    tracker.track("d-1", "epoch-1");
    advance(30_000);
    const first = tracker.scan();
    const second = tracker.scan();
    expect(first).toEqual(second);
    expect(tracker.outstandingCount()).toBe(1);
  });

  test("时钟回退不会误判超期", () => {
    const { tracker, advance, setNow } = setup();
    setNow(100_000);
    tracker.track("d-1", "epoch-1");
    setNow(100_000 - 60_000);
    expect(tracker.scan()).toEqual([]);
  });

  test("reset 清空全部条目", () => {
    const { tracker } = setup();
    tracker.track("d-1", "epoch-1");
    tracker.track("d-2", "epoch-1");
    tracker.reset();
    expect(tracker.outstandingCount()).toBe(0);
    expect(tracker.scan()).toEqual([]);
  });
});

describe("标识校验", () => {
  test("空标识拒绝", () => {
    const { tracker } = setup();
    expect(() => tracker.track("", "epoch-1")).toThrow('identifier "deliveryId" must not be empty');
    expect(() => tracker.track("d-1", "")).toThrow('identifier "transportEpoch" must not be empty');
    expect(() => tracker.settle("")).toThrow('identifier "deliveryId" must not be empty');
  });

  test("控制字符与 C1 字符拒绝", () => {
    const { tracker } = setup();
    for (const value of [0, 31, 0x7f, 0x9f].map((code) => `a${String.fromCharCode(code)}b`)) {
      expect(() => tracker.track(value, "epoch-1")).toThrow("must not contain control characters");
    }
  });

  test("超过 256 UTF-8 字节拒绝，边界内允许", () => {
    const { tracker } = setup();
    tracker.track("字".repeat(85), "epoch-1");
    expect(tracker.outstandingCount()).toBe(1);
    expect(() => tracker.track("字".repeat(86), "epoch-1")).toThrow("is 258 UTF-8 bytes, limit is 256");
    try {
      tracker.track("字".repeat(86), "epoch-1");
    } catch (error) {
      expect((error as SyncProtocolError).code).toBe("IDENTIFIER_TOO_LONG");
    }
  });
});
