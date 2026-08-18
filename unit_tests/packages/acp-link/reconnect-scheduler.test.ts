import { describe, test, expect } from "bun:test";

// ========== Pure function copies from packages/acp-link/src/reconnect-scheduler.ts ==========

function createReconnectScheduler(options: {
  connect: () => void;
  setTimeout?: (cb: () => void, delayMs: number) => any;
  clearTimeout?: (timer: any) => void;
}) {
  const scheduleTimeout = options.setTimeout ?? ((cb, delayMs) => setTimeout(cb, delayMs));
  const cancelTimeout = options.clearTimeout ?? clearTimeout;
  let timer: any = null;
  return {
    schedule(delayMs = 0): boolean {
      if (timer !== null) return false;
      timer = scheduleTimeout(() => {
        timer = null;
        options.connect();
      }, delayMs);
      return true;
    },
    cancel(): void {
      if (timer === null) return;
      cancelTimeout(timer);
      timer = null;
    },
  };
}

// ========== Tests ==========

describe("createReconnectScheduler", () => {
  test("schedule calls connect after delay", () => {
    let connected = false;
    let scheduledDelay: number | null = null;
    let scheduledCb: (() => void) | null = null;

    const scheduler = createReconnectScheduler({
      connect: () => {
        connected = true;
      },
      setTimeout: (cb, delayMs) => {
        scheduledDelay = delayMs;
        scheduledCb = cb;
        return "timer-1";
      },
      clearTimeout: () => {},
    });

    const result = scheduler.schedule(1000);
    expect(result).toBe(true);
    expect(scheduledDelay).toBe(1000);
    expect(connected).toBe(false);

    // Simulate timer firing
    scheduledCb!();
    expect(connected).toBe(true);
  });

  test("schedule with default delay of 0", () => {
    let scheduledDelay: number | null = null;

    const scheduler = createReconnectScheduler({
      connect: () => {},
      setTimeout: (cb, delayMs) => {
        scheduledDelay = delayMs;
        return "timer";
      },
    });

    scheduler.schedule();
    expect(scheduledDelay).toBe(0);
  });

  test("schedule returns false when already scheduled", () => {
    const scheduler = createReconnectScheduler({
      connect: () => {},
      setTimeout: () => "timer-1",
    });

    const first = scheduler.schedule(500);
    const second = scheduler.schedule(500);
    expect(first).toBe(true);
    expect(second).toBe(false);
  });

  test("cancel prevents connect from being called", () => {
    let connected = false;
    let cancelledTimer: any = null;

    const scheduler = createReconnectScheduler({
      connect: () => {
        connected = true;
      },
      setTimeout: (_cb, _delayMs) => "timer-abc",
      clearTimeout: (timer) => {
        cancelledTimer = timer;
      },
    });

    scheduler.schedule(1000);
    scheduler.cancel();

    expect(cancelledTimer).toBe("timer-abc");
    expect(connected).toBe(false);
  });

  test("cancel when no timer is a no-op", () => {
    let clearTimeoutCalled = false;

    const scheduler = createReconnectScheduler({
      connect: () => {},
      setTimeout: () => "timer",
      clearTimeout: () => {
        clearTimeoutCalled = true;
      },
    });

    // No schedule, just cancel
    scheduler.cancel();
    expect(clearTimeoutCalled).toBe(false);
  });

  test("schedule after cancel works", () => {
    let connectCount = 0;
    let cb: (() => void) | null = null;

    const scheduler = createReconnectScheduler({
      connect: () => {
        connectCount++;
      },
      setTimeout: (callback) => {
        cb = callback;
        return "timer";
      },
      clearTimeout: () => {},
    });

    // Schedule, cancel, then schedule again
    scheduler.schedule(100);
    scheduler.cancel();
    const result = scheduler.schedule(200);
    expect(result).toBe(true);

    // Fire the second timer
    cb!();
    expect(connectCount).toBe(1);
  });

  test("schedule after timer fires works", () => {
    let connectCount = 0;
    let cb: (() => void) | null = null;

    const scheduler = createReconnectScheduler({
      connect: () => {
        connectCount++;
      },
      setTimeout: (callback) => {
        cb = callback;
        return "timer";
      },
    });

    // First schedule
    scheduler.schedule(0);
    cb!(); // fire timer
    expect(connectCount).toBe(1);

    // Second schedule should work since timer was cleared
    const result = scheduler.schedule(0);
    expect(result).toBe(true);
    cb!(); // fire second timer
    expect(connectCount).toBe(2);
  });

  test("cancel after timer already fired is a no-op", () => {
    let connected = false;
    let cb: (() => void) | null = null;

    const scheduler = createReconnectScheduler({
      connect: () => {
        connected = true;
      },
      setTimeout: (callback) => {
        cb = callback;
        return "timer";
      },
    });

    scheduler.schedule(0);
    cb!(); // fire timer
    expect(connected).toBe(true);

    // Cancel after fire should be no-op (timer is already null)
    scheduler.cancel();
  });
});
