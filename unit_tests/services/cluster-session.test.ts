// cluster-session.test.ts — Sandbox 集群控制台浏览器会话凭证测试
// 测试目标：saveSession / readSession / clearSession
// 业务意图：确保凭证固定一天有效期、越界或畸形存储一律视为未登录并清理
// 源：packages/opensandbox-cluster/web/session.ts（main a7f477a9e）

import { describe, expect, test } from "bun:test";

// ── 复制实现 ──

const sessionKey = "opensandbox-cluster-session";
const day = 86400000;
type StoragePort = Pick<Storage, "getItem" | "setItem" | "removeItem">;

interface Session {
  key: string;
  expiresAt: number;
}

function clearSession(storage: StoragePort) {
  try {
    storage.removeItem(sessionKey);
  } catch {
    /* Browsers may disable local storage. */
  }
}

function readSession(storage: StoragePort, now = Date.now()): Session | undefined {
  try {
    const value = JSON.parse(storage.getItem(sessionKey) ?? "null");
    if (
      typeof value?.key === "string" &&
      value.key &&
      Number.isFinite(value.expiresAt) &&
      value.expiresAt > now &&
      value.expiresAt <= now + day
    )
      return value;
  } catch {
    /* Missing or malformed storage requires a fresh login. */
  }
  clearSession(storage);
  return;
}

function saveSession(storage: StoragePort, key: string, now = Date.now()): Session {
  const session = { key, expiresAt: now + day };
  try {
    storage.setItem(sessionKey, JSON.stringify(session));
  } catch {
    /* Login remains usable without persistence. */
  }
  return session;
}

// ── 测试辅助 ──

function memoryStorage(initial?: string) {
  const values = new Map<string, string>();
  if (initial !== undefined) values.set(sessionKey, initial);
  const removed: string[] = [];
  const storage: StoragePort = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => {
      values.set(key, value);
    },
    removeItem: (key) => {
      removed.push(key);
      values.delete(key);
    },
  };
  return { storage, values, removed };
}

const now = 1_700_000_000_000;

// ── tests ──

describe("cluster-session 控制台会话凭证", () => {
  describe("saveSession", () => {
    test("返回一天有效期的凭证", () => {
      const { storage } = memoryStorage();
      expect(saveSession(storage, "secret-key", now)).toEqual({ key: "secret-key", expiresAt: now + day });
    });

    test("凭证写入固定存储键", () => {
      const { storage, values } = memoryStorage();
      saveSession(storage, "secret-key", now);
      expect(JSON.parse(values.get("opensandbox-cluster-session")!)).toEqual({
        key: "secret-key",
        expiresAt: now + day,
      });
    });

    test("存储被禁用时仍返回当前页会话", () => {
      const storage: StoragePort = {
        getItem: () => null,
        setItem: () => {
          throw new Error("storage disabled");
        },
        removeItem: () => {},
      };
      expect(saveSession(storage, "secret-key", now)).toEqual({ key: "secret-key", expiresAt: now + day });
    });
  });

  describe("readSession", () => {
    test("有效凭证被原样恢复", () => {
      const session = { key: "secret-key", expiresAt: now + 1_000 };
      const { storage } = memoryStorage(JSON.stringify(session));
      expect(readSession(storage, now)).toEqual(session);
    });

    test("恰好到期一天仍有效（包含边界）", () => {
      const session = { key: "secret-key", expiresAt: now + day };
      const { storage } = memoryStorage(JSON.stringify(session));
      expect(readSession(storage, now)).toEqual(session);
    });

    test("已过期凭证被清除", () => {
      const { storage, removed } = memoryStorage(JSON.stringify({ key: "k", expiresAt: now }));
      expect(readSession(storage, now)).toBeUndefined();
      expect(removed).toContain(sessionKey);
    });

    test("超过一天窗口的凭证被拒绝（防止篡改延期）", () => {
      const { storage, removed } = memoryStorage(JSON.stringify({ key: "k", expiresAt: now + day + 1 }));
      expect(readSession(storage, now)).toBeUndefined();
      expect(removed).toContain(sessionKey);
    });

    test("缺失存储返回 undefined 并清理", () => {
      const { storage, removed } = memoryStorage();
      expect(readSession(storage, now)).toBeUndefined();
      expect(removed).toContain(sessionKey);
    });

    test("非法 JSON 返回 undefined 并清理", () => {
      const { storage, removed } = memoryStorage("{not-json");
      expect(readSession(storage, now)).toBeUndefined();
      expect(removed).toContain(sessionKey);
    });

    test("key 为空字符串时拒绝", () => {
      const { storage } = memoryStorage(JSON.stringify({ key: "", expiresAt: now + 1 }));
      expect(readSession(storage, now)).toBeUndefined();
    });

    test("key 非字符串时拒绝", () => {
      const { storage } = memoryStorage(JSON.stringify({ key: 42, expiresAt: now + 1 }));
      expect(readSession(storage, now)).toBeUndefined();
    });

    test("expiresAt 非有限数时拒绝", () => {
      const { storage } = memoryStorage('{"key":"k","expiresAt":null}');
      expect(readSession(storage, now)).toBeUndefined();
    });

    test("storage.getItem 抛错时返回 undefined", () => {
      const storage: StoragePort = {
        getItem: () => {
          throw new Error("blocked");
        },
        setItem: () => {},
        removeItem: () => {},
      };
      expect(readSession(storage, now)).toBeUndefined();
    });
  });

  describe("clearSession", () => {
    test("删除固定存储键", () => {
      const { storage, values } = memoryStorage(JSON.stringify({ key: "k", expiresAt: now + 1 }));
      clearSession(storage);
      expect(values.has(sessionKey)).toBe(false);
    });

    test("存储删除抛错时静默", () => {
      const storage: StoragePort = {
        getItem: () => null,
        setItem: () => {},
        removeItem: () => {
          throw new Error("blocked");
        },
      };
      expect(() => clearSession(storage)).not.toThrow();
    });
  });
});
