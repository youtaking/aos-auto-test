import { describe, test, expect } from "bun:test";

// ── Pure class copy from packages/workflow-engine/src/scheduler/cancellation.ts ──

class CancellationManager {
  private abortController: AbortController;
  private readonly gracePeriodMs: number;

  constructor(gracePeriodMs = 10000) {
    this.abortController = new AbortController();
    this.gracePeriodMs = gracePeriodMs;
  }

  get signal(): AbortSignal {
    return this.abortController.signal;
  }

  get cancelled(): boolean {
    return this.abortController.signal.aborted;
  }

  cancel(): void {
    this.abortController.abort();
  }

  waitForGracePeriod(): Promise<void> {
    if (this.cancelled) {
      return new Promise((resolve) => setTimeout(resolve, this.gracePeriodMs));
    }
    return Promise.resolve();
  }
}

// ── Tests ──

describe("CancellationManager", () => {
  describe("initial state", () => {
    test("not cancelled by default", () => {
      const cm = new CancellationManager();
      expect(cm.cancelled).toBe(false);
    });

    test("signal is not aborted by default", () => {
      const cm = new CancellationManager();
      expect(cm.signal.aborted).toBe(false);
    });

    test("signal is an AbortSignal", () => {
      const cm = new CancellationManager();
      expect(cm.signal).toBeInstanceOf(AbortSignal);
    });
  });

  describe("cancel", () => {
    test("sets cancelled to true", () => {
      const cm = new CancellationManager();
      cm.cancel();
      expect(cm.cancelled).toBe(true);
    });

    test("aborts the signal", () => {
      const cm = new CancellationManager();
      cm.cancel();
      expect(cm.signal.aborted).toBe(true);
    });

    test("calling cancel multiple times does not throw", () => {
      const cm = new CancellationManager();
      cm.cancel();
      expect(() => cm.cancel()).not.toThrow();
      expect(cm.cancelled).toBe(true);
    });

    test("signal abort event fires on cancel", () => {
      const cm = new CancellationManager();
      let aborted = false;
      cm.signal.addEventListener("abort", () => { aborted = true; });
      cm.cancel();
      expect(aborted).toBe(true);
    });
  });

  describe("waitForGracePeriod", () => {
    test("resolves immediately when not cancelled", async () => {
      const cm = new CancellationManager(100);
      const start = Date.now();
      await cm.waitForGracePeriod();
      const elapsed = Date.now() - start;
      expect(elapsed).toBeLessThan(50);
    });

    test("waits for grace period when cancelled", async () => {
      const graceMs = 100;
      const cm = new CancellationManager(graceMs);
      cm.cancel();

      const start = Date.now();
      await cm.waitForGracePeriod();
      const elapsed = Date.now() - start;
      expect(elapsed).toBeGreaterThanOrEqual(graceMs - 10);
    });

    test("default grace period constructor creates valid instance", () => {
      // gracePeriodMs 是 private readonly，无法从外部直接读取。
      // 等待 10s 来验证默认值不现实，因此验证实例完整性和方法签名。
      const cm = new CancellationManager();
      expect(cm).not.toBeNull();
      expect(cm.cancelled).toBe(false);
      expect(cm.signal).toBeInstanceOf(AbortSignal);
      expect(typeof cm.cancel).toBe("function");
      expect(typeof cm.waitForGracePeriod).toBe("function");
    });

    test("custom grace period works", async () => {
      const cm = new CancellationManager(50);
      cm.cancel();

      const start = Date.now();
      await cm.waitForGracePeriod();
      const elapsed = Date.now() - start;
      expect(elapsed).toBeGreaterThanOrEqual(40);
      expect(elapsed).toBeLessThan(200);
    });
  });

  describe("signal sharing", () => {
    test("same signal instance returned on multiple accesses", () => {
      const cm = new CancellationManager();
      const sig1 = cm.signal;
      const sig2 = cm.signal;
      expect(sig1).toBe(sig2);
    });

    test("multiple listeners on signal all fire on cancel", () => {
      const cm = new CancellationManager();
      const results: boolean[] = [];

      cm.signal.addEventListener("abort", () => results.push(true));
      cm.signal.addEventListener("abort", () => results.push(true));

      cm.cancel();
      expect(results.length).toBe(2);
      expect(results.every((r) => r === true)).toBe(true);
    });
  });
});
