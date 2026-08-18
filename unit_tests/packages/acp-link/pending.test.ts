import { describe, test, expect, beforeEach } from "bun:test";

// ── Pure class copy from packages/acp-link/src/client/pending.ts ──

interface PendingEntry<T = any> {
  request: any;
  resolve: (value: any) => void;
  reject: (err: Error) => void;
  promise: Promise<T>;
}

class ACPPending {
  private pending = new Map<number | string, PendingEntry<any>>();

  register<TResponse>(
    id: number | string,
    request: any,
    _timeout: number,
  ): Promise<TResponse> {
    const existing = this.pending.get(id);
    if (existing) {
      return existing.promise as Promise<TResponse>;
    }

    let resolveFn!: (value: any) => void;
    let rejectFn!: (err: Error) => void;
    const promise = new Promise<TResponse>((resolve, reject) => {
      resolveFn = resolve;
      rejectFn = reject;
    });

    this.pending.set(id, {
      request,
      resolve: resolveFn,
      reject: rejectFn,
      promise,
    });

    return promise;
  }

  tryResolve(id: number | string, result: any): boolean {
    const entry = this.pending.get(id);
    if (entry) {
      this.pending.delete(id);
      entry.resolve(result);
      return true;
    }
    return false;
  }

  getPendingRequests(): Array<{ id: number | string; request: unknown }> {
    return [...this.pending.entries()].map(([id, entry]) => ({ id, request: entry.request }));
  }

  rejectAll(error: Error): void {
    for (const [_key, entry] of this.pending) {
      entry.reject(error);
    }
    this.pending.clear();
  }

  get hasPending(): boolean {
    return this.pending.size > 0;
  }
}

// ── Tests ──

describe("ACPPending", () => {
  let pending: ACPPending;

  beforeEach(() => {
    pending = new ACPPending();
  });

  describe("register", () => {
    test("registers a new pending request and returns a promise", () => {
      const promise = pending.register(1, { method: "test" }, 5000);
      expect(promise).toBeInstanceOf(Promise);
      expect(pending.hasPending).toBe(true);
    });

    test("returns same promise for duplicate id (dedup)", () => {
      const p1 = pending.register(1, { method: "first" }, 5000);
      const p2 = pending.register(1, { method: "second" }, 5000);
      expect(p1).toBe(p2);
    });

    test("accepts string ids", () => {
      const promise = pending.register("req-abc", { method: "test" }, 5000);
      expect(promise).toBeInstanceOf(Promise);
      expect(pending.hasPending).toBe(true);
    });

    test("accepts numeric ids", () => {
      pending.register(42, { method: "test" }, 5000);
      expect(pending.hasPending).toBe(true);
    });

    test("multiple different ids create separate entries", () => {
      pending.register(1, { method: "a" }, 5000);
      pending.register(2, { method: "b" }, 5000);
      pending.register("three", { method: "c" }, 5000);

      const requests = pending.getPendingRequests();
      expect(requests.length).toBe(3);
    });
  });

  describe("tryResolve", () => {
    test("resolves matching pending and returns true", async () => {
      const promise = pending.register(1, { method: "test" }, 5000);
      const resolved = pending.tryResolve(1, { data: "hello" });

      expect(resolved).toBe(true);
      const result = await promise;
      expect(result).toEqual({ data: "hello" });
    });

    test("removes entry after resolve", () => {
      pending.register(1, { method: "test" }, 5000);
      pending.tryResolve(1, "result");

      expect(pending.hasPending).toBe(false);
    });

    test("returns false for unknown id", () => {
      pending.register(1, { method: "test" }, 5000);
      const resolved = pending.tryResolve(999, "result");

      expect(resolved).toBe(false);
      expect(pending.hasPending).toBe(true);
    });

    test("resolves string id correctly", async () => {
      const promise = pending.register("req-1", { method: "test" }, 5000);
      pending.tryResolve("req-1", "done");

      expect(await promise).toBe("done");
    });

    test("does not resolve duplicate id twice", () => {
      pending.register(1, { method: "test" }, 5000);
      expect(pending.tryResolve(1, "first")).toBe(true);
      expect(pending.tryResolve(1, "second")).toBe(false);
    });
  });

  describe("getPendingRequests", () => {
    test("returns empty array when no pending", () => {
      expect(pending.getPendingRequests()).toEqual([]);
    });

    test("returns all pending requests with id and request data", () => {
      pending.register(1, { method: "a", params: [1] }, 5000);
      pending.register("two", { method: "b", params: [2] }, 5000);

      const requests = pending.getPendingRequests();
      expect(requests.length).toBe(2);

      const ids = requests.map((r) => r.id);
      expect(ids).toContain(1);
      expect(ids).toContain("two");

      const req1 = requests.find((r) => r.id === 1);
      expect(req1?.request).toEqual({ method: "a", params: [1] });
    });

    test("does not include resolved entries", () => {
      pending.register(1, { method: "a" }, 5000);
      pending.register(2, { method: "b" }, 5000);
      pending.tryResolve(1, "done");

      const requests = pending.getPendingRequests();
      expect(requests.length).toBe(1);
      expect(requests[0].id).toBe(2);
    });
  });

  describe("rejectAll", () => {
    test("rejects all pending promises with given error", async () => {
      const p1 = pending.register(1, {}, 5000);
      const p2 = pending.register(2, {}, 5000);

      const err = new Error("connection lost");
      pending.rejectAll(err);

      await expect(p1).rejects.toThrow("connection lost");
      await expect(p2).rejects.toThrow("connection lost");
    });

    test("clears all entries after rejectAll", async () => {
      const p1 = pending.register(1, {}, 5000);
      const p2 = pending.register(2, {}, 5000);

      pending.rejectAll(new Error("disconnect"));

      // Await rejections to avoid unhandled promise errors
      await Promise.allSettled([p1, p2]);

      expect(pending.hasPending).toBe(false);
      expect(pending.getPendingRequests()).toEqual([]);
    });

    test("rejectAll on empty pending does not throw", () => {
      expect(() => pending.rejectAll(new Error("test"))).not.toThrow();
    });
  });

  describe("hasPending", () => {
    test("false when empty", () => {
      expect(pending.hasPending).toBe(false);
    });

    test("true after register", () => {
      pending.register(1, {}, 5000);
      expect(pending.hasPending).toBe(true);
    });

    test("false after resolving the only entry", () => {
      pending.register(1, {}, 5000);
      pending.tryResolve(1, "done");
      expect(pending.hasPending).toBe(false);
    });

    test("true when some entries remain after partial resolve", () => {
      pending.register(1, {}, 5000);
      pending.register(2, {}, 5000);
      pending.tryResolve(1, "done");
      expect(pending.hasPending).toBe(true);
    });
  });
});
