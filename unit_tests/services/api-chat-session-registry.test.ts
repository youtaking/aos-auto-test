// api-chat-session-registry.test.ts — v1 会话续接注册表测试
// 测试目标：ApiChatSessionRegistry 的 reserve/confirm/acquire/validate/release/invalidateInstance
// 业务意图：确保会话句柄只能由同一所属主体续接、并发续接互斥、生命周期事件只失效目标实例
// 源：packages/agent-runtime/src/services/api-chat-session-registry.ts（main a7f477a9e）

import { beforeEach, describe, expect, mock, test } from "bun:test";
import { randomBytes } from "node:crypto";

// ── 复制实现 ──

class AppError extends Error {
  code: string;
  statusCode: number;
  constructor(message: string, code: string, statusCode: number) {
    super(message);
    this.name = "AppError";
    this.code = code;
    this.statusCode = statusCode;
  }
}

interface ApiChatSessionOwner {
  organizationId: string;
  userId: string;
  agentConfigId: string;
  environmentId: string;
  instanceId: string;
  runtimeGeneration: number;
}

type ApiChatSessionSubject = Pick<ApiChatSessionOwner, "organizationId" | "userId" | "agentConfigId"> &
  Partial<Pick<ApiChatSessionOwner, "instanceId" | "environmentId" | "runtimeGeneration">>;

interface ApiChatSessionLease {
  readonly handle: string;
  readonly owner: ApiChatSessionOwner;
  sessionId?: string;
  expiresAt: number;
  readonly signal: AbortSignal;
}

interface Entry extends ApiChatSessionLease {
  active: boolean;
  controller: AbortController;
  lastUsed: number;
}

const unavailable = () => new AppError("Session unavailable", "SESSION_UNAVAILABLE", 409);

class ApiChatSessionRegistry {
  private readonly entries = new Map<string, Entry>();
  private readonly now: () => number;
  private readonly ttl: number;
  private readonly perOwner: number;
  private readonly max: number;
  constructor(options: { now?: () => number; ttlMs?: number; perOwner?: number; maxEntries?: number } = {}) {
    this.now = options.now ?? Date.now;
    this.ttl = options.ttlMs ?? 30 * 60 * 1000;
    this.perOwner = options.perOwner ?? 256;
    this.max = options.maxEntries ?? 10000;
  }
  private remove(entry: Entry) {
    this.entries.delete(entry.handle);
    entry.controller.abort(unavailable());
  }
  private matches(entry: Entry, subject: ApiChatSessionSubject) {
    return Object.entries(subject).every(
      ([key, value]) => value === undefined || entry.owner[key as keyof ApiChatSessionOwner] === value,
    );
  }
  reserve(owner: ApiChatSessionOwner): ApiChatSessionLease {
    const now = this.now();
    for (const entry of this.entries.values()) if (!entry.active && entry.expiresAt <= now) this.remove(entry);
    const sameOwner = (entry: Entry) =>
      entry.owner.organizationId === owner.organizationId && entry.owner.userId === owner.userId;
    const count = () => [...this.entries.values()].filter(sameOwner).length;
    while (count() >= this.perOwner || this.entries.size >= this.max) {
      const candidates = [...this.entries.values()]
        .filter((entry) => !entry.active && (count() < this.perOwner || sameOwner(entry)))
        .sort((a, b) => a.lastUsed - b.lastUsed);
      if (!candidates[0]) throw new AppError("Session capacity reached", "SESSION_CAPACITY_EXCEEDED", 429);
      this.remove(candidates[0]);
    }
    const controller = new AbortController();
    const entry: Entry = {
      handle: `fcs_${randomBytes(24).toString("base64url")}`,
      owner: { ...owner },
      expiresAt: now + this.ttl,
      lastUsed: now,
      active: true,
      controller,
      signal: controller.signal,
    };
    this.entries.set(entry.handle, entry);
    return entry;
  }
  confirm(lease: ApiChatSessionLease, sessionId: string): void {
    const entry = this.entries.get(lease.handle);
    if (entry !== lease || !entry.active || !sessionId) throw unavailable();
    entry.sessionId = sessionId;
  }
  acquire(handle: string, subject: ApiChatSessionSubject): ApiChatSessionLease {
    const entry = this.entries.get(handle);
    if (!entry?.sessionId || !this.matches(entry, subject)) throw unavailable();
    if (entry.active) throw new AppError("Session busy", "AGENT_SESSION_BUSY", 409);
    if (entry.expiresAt <= this.now()) {
      this.remove(entry);
      throw unavailable();
    }
    entry.active = true;
    entry.lastUsed = this.now();
    entry.expiresAt = entry.lastUsed + this.ttl;
    return entry;
  }
  validate(lease: ApiChatSessionLease, owner: ApiChatSessionOwner): void {
    const entry = this.entries.get(lease.handle);
    if (entry !== lease || !this.matches(entry, owner)) {
      if (entry) this.remove(entry);
      throw unavailable();
    }
  }
  release(lease: ApiChatSessionLease, success: boolean): void {
    const entry = this.entries.get(lease.handle);
    if (entry !== lease) return;
    if (!success || !entry.sessionId) {
      this.remove(entry);
      return;
    }
    entry.active = false;
    entry.lastUsed = this.now();
    entry.expiresAt = entry.lastUsed + this.ttl;
  }
  invalidateInstance(instanceId: string): void {
    for (const entry of this.entries.values()) if (entry.owner.instanceId === instanceId) this.remove(entry);
  }
  size(): number {
    return this.entries.size;
  }
}

// ── 测试辅助 ──

const owner: ApiChatSessionOwner = {
  organizationId: "org-1",
  userId: "user-1",
  agentConfigId: "agent-1",
  environmentId: "env-1",
  instanceId: "inst-1",
  runtimeGeneration: 1,
};

const subject = { organizationId: "org-1", userId: "user-1", agentConfigId: "agent-1" };

function setup(options: { ttlMs?: number; perOwner?: number; maxEntries?: number } = {}) {
  let now = 1_000_000;
  const registry = new ApiChatSessionRegistry({
    ...options,
    now: () => now,
  });
  return {
    registry,
    owner,
    advance(ms: number) {
      now += ms;
    },
    current() {
      return now;
    },
  };
}

// ── tests ──

describe("api-chat-session-registry v1 会话注册表", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("reserve", () => {
    test("生成 fcs_ 前缀句柄并复制所属身份", () => {
      const { registry, owner } = setup();
      const lease = registry.reserve(owner);
      expect(lease.handle.startsWith("fcs_")).toBe(true);
      expect(lease.owner).toEqual(owner);
      expect(lease.owner).not.toBe(owner);
    });

    test("新租约处于活跃状态且带中止信号", () => {
      const { registry, owner, current } = setup({ ttlMs: 60_000 });
      const lease = registry.reserve(owner);
      expect(lease.expiresAt).toBe(current() + 60_000);
      expect(lease.signal.aborted).toBe(false);
    });

    test("不同调用生成不同句柄", () => {
      const { registry, owner } = setup();
      expect(registry.reserve(owner).handle).not.toBe(registry.reserve(owner).handle);
    });

    test("预留时清理已过期的空闲会话", () => {
      const { registry, owner, advance } = setup({ ttlMs: 1_000 });
      const first = registry.reserve(owner);
      registry.confirm(first, "acp-1");
      registry.release(first, true);
      advance(1_001);
      registry.reserve(owner);
      expect(first.signal.aborted).toBe(true);
    });

    test("活跃会话不会被过期清理影响", () => {
      const { registry, owner, advance } = setup({ ttlMs: 1_000 });
      const active = registry.reserve(owner);
      advance(5_000);
      registry.reserve(owner);
      expect(active.signal.aborted).toBe(false);
    });

    test("超出单用户上限时淘汰最久未用的空闲会话", () => {
      const { registry, owner } = setup({ perOwner: 2 });
      const first = registry.reserve(owner);
      registry.confirm(first, "acp-1");
      registry.release(first, true);
      const second = registry.reserve(owner);
      const third = registry.reserve(owner);
      expect(first.signal.aborted).toBe(true);
      expect(second.signal.aborted).toBe(false);
      expect(third.signal.aborted).toBe(false);
    });

    test("全部活跃且达到上限时返回 429", () => {
      const { registry, owner } = setup({ maxEntries: 1 });
      registry.reserve(owner);
      expect(() => registry.reserve(owner)).toThrow("Session capacity reached");
      try {
        registry.reserve(owner);
      } catch (error) {
        expect(error).toMatchObject({ code: "SESSION_CAPACITY_EXCEEDED", statusCode: 429 });
      }
    });
  });

  describe("confirm", () => {
    test("握手成功后记录 ACP sessionId", () => {
      const { registry, owner } = setup();
      const lease = registry.reserve(owner);
      registry.confirm(lease, "acp-1");
      expect(lease.sessionId).toBe("acp-1");
    });

    test("非本人租约不能确认", () => {
      const { registry, owner } = setup();
      const lease = registry.reserve(owner);
      const forged = { ...lease, handle: "fcs_forged" };
      expect(() => registry.confirm(forged, "acp-1")).toThrow("Session unavailable");
    });

    test("已释放的租约不能确认", () => {
      const { registry, owner } = setup();
      const lease = registry.reserve(owner);
      registry.release(lease, false);
      expect(() => registry.confirm(lease, "acp-1")).toThrow("Session unavailable");
    });

    test("空 sessionId 被拒绝", () => {
      const { registry, owner } = setup();
      const lease = registry.reserve(owner);
      expect(() => registry.confirm(lease, "")).toThrow("Session unavailable");
    });
  });

  describe("acquire", () => {
    test("未确认的会话不能续接", () => {
      const { registry, owner } = setup();
      const lease = registry.reserve(owner);
      expect(() => registry.acquire(lease.handle, subject)).toThrow("Session unavailable");
    });

    test("未知句柄返回 unavailable", () => {
      const { registry } = setup();
      expect(() => registry.acquire("fcs_unknown", subject)).toThrow("Session unavailable");
    });

    test("所属维度不匹配时拒绝（跨用户）", () => {
      const { registry, owner } = setup();
      const lease = registry.reserve(owner);
      registry.confirm(lease, "acp-1");
      registry.release(lease, true);
      expect(() => registry.acquire(lease.handle, { ...subject, userId: "user-2" })).toThrow("Session unavailable");
    });

    test("未提供可选维度时不做匹配", () => {
      const { registry, owner } = setup();
      const lease = registry.reserve(owner);
      registry.confirm(lease, "acp-1");
      registry.release(lease, true);
      expect(registry.acquire(lease.handle, subject).handle).toBe(lease.handle);
    });

    test("提供 instanceId 且不匹配时拒绝", () => {
      const { registry, owner } = setup();
      const lease = registry.reserve(owner);
      registry.confirm(lease, "acp-1");
      registry.release(lease, true);
      expect(() => registry.acquire(lease.handle, { ...subject, instanceId: "inst-other" })).toThrow(
        "Session unavailable",
      );
    });

    test("活跃中的会话并发续接返回 AGENT_SESSION_BUSY", () => {
      const { registry, owner } = setup();
      const lease = registry.reserve(owner);
      registry.confirm(lease, "acp-1");
      expect(() => registry.acquire(lease.handle, subject)).toThrow("Session busy");
      try {
        registry.acquire(lease.handle, subject);
      } catch (error) {
        expect(error).toMatchObject({ code: "AGENT_SESSION_BUSY", statusCode: 409 });
      }
    });

    test("空闲会话续接后重新计时并占用", () => {
      const { registry, owner, current, advance } = setup({ ttlMs: 60_000 });
      const lease = registry.reserve(owner);
      registry.confirm(lease, "acp-1");
      registry.release(lease, true);
      advance(10_000);
      registry.acquire(lease.handle, subject);
      expect(lease.expiresAt).toBe(current() + 60_000);
      expect(() => registry.acquire(lease.handle, subject)).toThrow("Session busy");
    });

    test("过期会话被移除并拒绝续接", () => {
      const { registry, owner, advance } = setup({ ttlMs: 1_000 });
      const lease = registry.reserve(owner);
      registry.confirm(lease, "acp-1");
      registry.release(lease, true);
      advance(1_001);
      expect(() => registry.acquire(lease.handle, subject)).toThrow("Session unavailable");
    });
  });

  describe("validate", () => {
    test("身份完全一致时通过", () => {
      const { registry, owner } = setup();
      const lease = registry.reserve(owner);
      expect(() => registry.validate(lease, owner)).not.toThrow();
    });

    test("任一维度变化时移除会话并拒绝", () => {
      const { registry, owner } = setup();
      const lease = registry.reserve(owner);
      expect(() => registry.validate(lease, { ...owner, runtimeGeneration: 2 })).toThrow("Session unavailable");
      expect(lease.signal.aborted).toBe(true);
      expect(registry.size()).toBe(0);
    });
  });

  describe("release", () => {
    test("成功且已确认的会话回到空闲，可再次续接", () => {
      const { registry, owner } = setup();
      const lease = registry.reserve(owner);
      registry.confirm(lease, "acp-1");
      registry.release(lease, true);
      expect(lease.signal.aborted).toBe(false);
      expect(registry.acquire(lease.handle, subject).handle).toBe(lease.handle);
    });

    test("失败会话立即失效", () => {
      const { registry, owner } = setup();
      const lease = registry.reserve(owner);
      registry.confirm(lease, "acp-1");
      registry.release(lease, false);
      expect(lease.signal.aborted).toBe(true);
      expect(registry.size()).toBe(0);
    });

    test("未确认的会话释放即失效", () => {
      const { registry, owner } = setup();
      const lease = registry.reserve(owner);
      registry.release(lease, true);
      expect(lease.signal.aborted).toBe(true);
    });

    test("非本人租约释放是空操作", () => {
      const { registry, owner } = setup();
      const lease = registry.reserve(owner);
      registry.release({ ...lease, handle: "fcs_other" }, false);
      expect(lease.signal.aborted).toBe(false);
    });
  });

  describe("invalidateInstance", () => {
    test("只失效目标实例的会话", () => {
      const { registry } = setup();
      const first = registry.reserve(owner);
      const second = registry.reserve({ ...owner, instanceId: "inst-2" });
      registry.invalidateInstance("inst-1");
      expect(first.signal.aborted).toBe(true);
      expect(second.signal.aborted).toBe(false);
    });

    test("同实例不同代次的会话都会失效", () => {
      const { registry } = setup();
      const first = registry.reserve(owner);
      const second = registry.reserve({ ...owner, runtimeGeneration: 2 });
      registry.invalidateInstance("inst-1");
      expect(first.signal.aborted).toBe(true);
      expect(second.signal.aborted).toBe(true);
    });
  });
});
