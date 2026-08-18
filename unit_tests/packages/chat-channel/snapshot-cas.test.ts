import { describe, test, expect } from "bun:test";
import * as Y from "yjs";

// ========== Pure function copies from packages/chat-channel/src/persist/snapshot-cas.ts ==========

const SNAPSHOT_PERSIST_RETRIES = 5;

function mergeSnapshotUpdates(existingRaw: Buffer | null, localFull: Uint8Array): Uint8Array {
  if (!existingRaw) return localFull;

  try {
    return Y.mergeUpdates([new Uint8Array(existingRaw), localFull]);
  } catch {
    // 兼容此前错误写入的 base64 快照；新写入始终为原始二进制。
    return Y.mergeUpdates([new Uint8Array(Buffer.from(existingRaw.toString(), "base64")), localFull]);
  }
}

type RedisSnapshotTransaction = {
  set(key: string, value: Buffer, expiryMode?: "EX", seconds?: number): RedisSnapshotTransaction;
  exec(): Promise<unknown | null>;
};

type RedisSnapshotConnection = {
  watch(key: string): Promise<unknown>;
  unwatch(): Promise<unknown>;
  getBuffer(key: string): Promise<Buffer | null>;
  multi(): RedisSnapshotTransaction;
  disconnect(): void;
};

async function mergeYjsSnapshotWithCas(
  persistence: RedisSnapshotConnection,
  redisKey: string,
  localFull: Uint8Array,
  ttlSeconds: number = 604800,
): Promise<boolean> {
  for (let attempt = 0; attempt < SNAPSHOT_PERSIST_RETRIES; attempt += 1) {
    let watched = false;
    try {
      await persistence.watch(redisKey);
      watched = true;
      const existingRaw = await persistence.getBuffer(redisKey);
      const merged = mergeSnapshotUpdates(existingRaw, localFull);
      const result = await persistence.multi().set(redisKey, Buffer.from(merged), "EX", ttlSeconds).exec();
      watched = false; // EXEC 会自动 UNWATCH。
      if (result !== null) return true;
    } finally {
      if (watched) await persistence.unwatch().catch(() => {});
    }
  }

  return false;
}

// ========== Mock helpers ==========

type MockCall = { method: string; args: unknown[] };

function createMockPersistence(options: {
  existingBuffer?: Buffer | null;
  execResults: (unknown | null)[];
}): { conn: RedisSnapshotConnection; calls: MockCall[] } {
  const calls: MockCall[] = [];
  let execIndex = 0;
  const existingBuffer = options.existingBuffer ?? null;
  const execResults = options.execResults;

  const conn: RedisSnapshotConnection = {
    async watch(key: string) {
      calls.push({ method: "watch", args: [key] });
      return "OK";
    },
    async unwatch() {
      calls.push({ method: "unwatch", args: [] });
      return "OK";
    },
    async getBuffer(key: string) {
      calls.push({ method: "getBuffer", args: [key] });
      return existingBuffer;
    },
    multi(): RedisSnapshotTransaction {
      calls.push({ method: "multi", args: [] });
      const tx: RedisSnapshotTransaction = {
        set(key: string, value: Buffer, expiryMode?: "EX", seconds?: number) {
          calls.push({ method: "set", args: [key, value, expiryMode, seconds] });
          return tx;
        },
        async exec() {
          calls.push({ method: "exec", args: [] });
          const result = execIndex < execResults.length ? execResults[execIndex] : null;
          execIndex += 1;
          return result;
        },
      };
      return tx;
    },
    disconnect() {
      calls.push({ method: "disconnect", args: [] });
    },
  };

  return { conn, calls };
}

// ========== Helper: create a Yjs update buffer ==========

function createYjsUpdate(text: string): Uint8Array {
  const doc = new Y.Doc();
  doc.getText("test").insert(0, text);
  const update = Y.encodeStateAsUpdate(doc);
  doc.destroy();
  return update;
}

// ========== Tests ==========

describe("mergeSnapshotUpdates", () => {
  test("existingRaw 为 null → 直接返回 localFull", () => {
    // 远端无快照时，本地数据即为最终结果
    const localFull = createYjsUpdate("hello");
    const result = mergeSnapshotUpdates(null, localFull);
    expect(result).toBe(localFull); // 同一引用
  });

  test("existingRaw 为有效 Yjs 二进制 → 返回合并后的 update", () => {
    // 两份不同的 Yjs 状态应正确合并
    const doc1 = new Y.Doc();
    doc1.getText("test").insert(0, "hello");
    const existingRaw = Buffer.from(Y.encodeStateAsUpdate(doc1));

    const doc2 = new Y.Doc();
    doc2.getText("test").insert(0, "world");
    const localFull = Y.encodeStateAsUpdate(doc2);

    const result = mergeSnapshotUpdates(existingRaw, localFull);

    // 合并结果应包含两份数据
    const verifyDoc = new Y.Doc();
    Y.applyUpdate(verifyDoc, result);
    const text = verifyDoc.getText("test").toString();
    expect(text).toContain("hello");
    expect(text).toContain("world");

    doc1.destroy();
    doc2.destroy();
    verifyDoc.destroy();
  });

  test("invalid base64 格式的 existingRaw → fallback 路径仍尝试合并", () => {
    // 如果原始二进制解析失败，函数会尝试 base64 解码
    // 构造一个有效 Yjs update 的 base64 编码作为 Buffer 内容
    const doc1 = new Y.Doc();
    doc1.getText("test").insert(0, "from-base64");
    const validUpdate = Y.encodeStateAsUpdate(doc1);
    const base64Str = Buffer.from(validUpdate).toString("base64");
    // existingRaw 内容实际上是 base64 字符串的二进制表示
    const existingRaw = Buffer.from(base64Str, "utf-8");

    const doc2 = new Y.Doc();
    doc2.getText("test").insert(0, "local-data");
    const localFull = Y.encodeStateAsUpdate(doc2);

    // 原始二进制解析大概率失败（base64 字符串不是有效 Yjs 二进制），进入 catch
    const result = mergeSnapshotUpdates(existingRaw, localFull);

    // 合并后应包含 base64 解码的数据和本地数据
    const verifyDoc = new Y.Doc();
    Y.applyUpdate(verifyDoc, result);
    const text = verifyDoc.getText("test").toString();
    expect(text).toContain("from-base64");
    expect(text).toContain("local-data");

    doc1.destroy();
    doc2.destroy();
    verifyDoc.destroy();
  });

  test("相同 Yjs 状态合并 → 结果与原始一致", () => {
    // 同一份 update 合并自身，幂等性
    const doc = new Y.Doc();
    doc.getText("test").insert(0, "same-content");
    const update = Y.encodeStateAsUpdate(doc);
    const existingRaw = Buffer.from(update);

    const result = mergeSnapshotUpdates(existingRaw, update);

    const verifyDoc = new Y.Doc();
    Y.applyUpdate(verifyDoc, result);
    const text = verifyDoc.getText("test").toString();
    expect(text).toBe("same-content");

    doc.destroy();
    verifyDoc.destroy();
  });

  test("空 Yjs doc 的 update 合并", () => {
    // 空文档的 update 也应正常合并
    const doc1 = new Y.Doc();
    const existingRaw = Buffer.from(Y.encodeStateAsUpdate(doc1));

    const doc2 = new Y.Doc();
    const localFull = Y.encodeStateAsUpdate(doc2);

    const result = mergeSnapshotUpdates(existingRaw, localFull);

    // 结果应为有效的 Yjs update
    const verifyDoc = new Y.Doc();
    expect(() => Y.applyUpdate(verifyDoc, result)).not.toThrow();
    expect(verifyDoc.getText("test").toString()).toBe("");

    doc1.destroy();
    doc2.destroy();
    verifyDoc.destroy();
  });
});

describe("mergeYjsSnapshotWithCas", () => {
  test("成功合并：Redis 无已有数据，EXEC 返回非 null → true", async () => {
    // 首次写入、无冲突场景
    const localFull = createYjsUpdate("new-data");
    const { conn, calls } = createMockPersistence({
      existingBuffer: null,
      execResults: [["OK"]], // 非 null 表示成功
    });

    const result = await mergeYjsSnapshotWithCas(conn, "snap:key1", localFull, 3600);

    expect(result).toBe(true);
    // 验证调用序列
    expect(calls[0].method).toBe("watch");
    expect(calls[0].args[0]).toBe("snap:key1");
    expect(calls[1].method).toBe("getBuffer");
    expect(calls[1].args[0]).toBe("snap:key1");
    expect(calls[2].method).toBe("multi");
    expect(calls[3].method).toBe("set");
    // set 参数验证
    expect(calls[3].args[0]).toBe("snap:key1");
    expect(calls[3].args[2]).toBe("EX");
    expect(calls[3].args[3]).toBe(3600);
    expect(calls[4].method).toBe("exec");
  });

  test("成功合并：Redis 有已有数据 → 合并后写入", async () => {
    // 远端已有快照，应合并后写入
    const doc1 = new Y.Doc();
    doc1.getText("test").insert(0, "remote");
    const existingRaw = Buffer.from(Y.encodeStateAsUpdate(doc1));

    const doc2 = new Y.Doc();
    doc2.getText("test").insert(0, "local");
    const localFull = Y.encodeStateAsUpdate(doc2);

    const { conn, calls } = createMockPersistence({
      existingBuffer: existingRaw,
      execResults: [["OK"]],
    });

    const result = await mergeYjsSnapshotWithCas(conn, "snap:key2", localFull, 7200);

    expect(result).toBe(true);
    // 验证 set 的 value 是合并后的 Buffer
    const setCall = calls.find((c) => c.method === "set");
    expect(setCall).toBeDefined();
    const writtenBuffer = setCall!.args[1] as Buffer;
    expect(writtenBuffer).toBeInstanceOf(Buffer);

    // 验证写入内容包含两份数据
    const verifyDoc = new Y.Doc();
    Y.applyUpdate(verifyDoc, new Uint8Array(writtenBuffer));
    const text = verifyDoc.getText("test").toString();
    expect(text).toContain("remote");
    expect(text).toContain("local");

    doc1.destroy();
    doc2.destroy();
    verifyDoc.destroy();
  });

  test("冲突重试：EXEC 返回 null → 重试直到成功", async () => {
    // 前两次冲突（null），第三次成功
    const localFull = createYjsUpdate("retry-data");
    const { conn, calls } = createMockPersistence({
      existingBuffer: null,
      execResults: [null, null, ["OK"]],
    });

    const result = await mergeYjsSnapshotWithCas(conn, "snap:key3", localFull);

    expect(result).toBe(true);
    // 应有 3 次 watch/getBuffer/multi/set/exec 循环
    const watchCalls = calls.filter((c) => c.method === "watch");
    expect(watchCalls.length).toBe(3);
    const execCalls = calls.filter((c) => c.method === "exec");
    expect(execCalls.length).toBe(3);
    // EXEC 本身会自动 UNWATCH，所以代码在 exec() 后设置 watched=false，不再额外调 unwatch
    const unwatchCalls = calls.filter((c) => c.method === "unwatch");
    expect(unwatchCalls.length).toBe(0);
  });

  test("重试耗尽：5 次全部冲突 → 返回 false", async () => {
    // 所有 5 次重试都冲突
    const localFull = createYjsUpdate("exhaust-data");
    const { conn, calls } = createMockPersistence({
      existingBuffer: null,
      execResults: [null, null, null, null, null],
    });

    const result = await mergeYjsSnapshotWithCas(conn, "snap:key4", localFull);

    expect(result).toBe(false);
    // 确认恰好 5 次循环
    const watchCalls = calls.filter((c) => c.method === "watch");
    expect(watchCalls.length).toBe(5);
    const execCalls = calls.filter((c) => c.method === "exec");
    expect(execCalls.length).toBe(5);
    // EXEC 本身会自动 UNWATCH，代码设置 watched=false 后 finally 不再调 unwatch
    const unwatchCalls = calls.filter((c) => c.method === "unwatch");
    expect(unwatchCalls.length).toBe(0);
  });

  test("TTL 参数传递到 set 调用", async () => {
    // 验证自定义 TTL 正确传递给 Redis set 命令
    const localFull = createYjsUpdate("ttl-test");
    const { conn, calls } = createMockPersistence({
      existingBuffer: null,
      execResults: [["OK"]],
    });

    await mergeYjsSnapshotWithCas(conn, "snap:ttl", localFull, 86400);

    const setCall = calls.find((c) => c.method === "set");
    expect(setCall!.args[2]).toBe("EX");
    expect(setCall!.args[3]).toBe(86400);
  });

  test("成功时不额外调用 unwatch（EXEC 自动 UNWATCH）", async () => {
    // EXEC 成功返回后 watched 设为 false，finally 不会再 unwatch
    const localFull = createYjsUpdate("no-unwatch");
    const { conn, calls } = createMockPersistence({
      existingBuffer: null,
      execResults: [["OK"]],
    });

    await mergeYjsSnapshotWithCas(conn, "snap:no-unwatch", localFull);

    const unwatchCalls = calls.filter((c) => c.method === "unwatch");
    // 成功时 watched=false，finally 不会调 unwatch
    expect(unwatchCalls.length).toBe(0);
  });

  test("getBuffer 异常 → unwatch 被调用且异常向上传播", async () => {
    // getBuffer 抛异常时 finally 仍应 unwatch；try...finally 无 catch，异常会传播出去
    const localFull = createYjsUpdate("error-test");
    const calls: MockCall[] = [];

    const conn: RedisSnapshotConnection = {
      async watch(key: string) {
        calls.push({ method: "watch", args: [key] });
      },
      async unwatch() {
        calls.push({ method: "unwatch", args: [] });
      },
      async getBuffer(_key: string) {
        calls.push({ method: "getBuffer", args: [] });
        throw new Error("Redis connection lost");
      },
      multi() {
        calls.push({ method: "multi", args: [] });
        return {
          set() {
            return this;
          },
          async exec() {
            return null;
          },
        };
      },
      disconnect() {
        calls.push({ method: "disconnect", args: [] });
      },
    };

    // try...finally 无 catch，异常会在第一次 attempt 就传播出去
    await expect(mergeYjsSnapshotWithCas(conn, "snap:error", localFull)).rejects.toThrow(
      "Redis connection lost",
    );
    // 只有 1 次 watch（异常在第一个 attempt 就抛出了）
    const watchCount = calls.filter((c) => c.method === "watch").length;
    const unwatchCount = calls.filter((c) => c.method === "unwatch").length;
    expect(watchCount).toBe(1);
    // finally 保证 unwatch 被调用
    expect(unwatchCount).toBe(1);
  });

  test("写入的 Buffer 是正确的 Yjs update", async () => {
    // 验证写入 Redis 的数据可以被 Yjs 正确反序列化
    const localFull = createYjsUpdate("verify-buffer");
    const { conn, calls } = createMockPersistence({
      existingBuffer: null,
      execResults: [["OK"]],
    });

    await mergeYjsSnapshotWithCas(conn, "snap:verify", localFull, 3600);

    const setCall = calls.find((c) => c.method === "set");
    const writtenBuffer = setCall!.args[1] as Buffer;

    // 写入的 Buffer 应能被 Yjs 正确解析
    const verifyDoc = new Y.Doc();
    Y.applyUpdate(verifyDoc, new Uint8Array(writtenBuffer));
    expect(verifyDoc.getText("test").toString()).toBe("verify-buffer");
    verifyDoc.destroy();
  });

  test("redisKey 参数正确传递给 watch 和 getBuffer", async () => {
    // 验证 key 参数透传
    const localFull = createYjsUpdate("key-test");
    const { conn, calls } = createMockPersistence({
      existingBuffer: null,
      execResults: [["OK"]],
    });

    await mergeYjsSnapshotWithCas(conn, "custom:redis:key:path", localFull, 3600);

    expect(calls[0]).toEqual({ method: "watch", args: ["custom:redis:key:path"] });
    expect(calls[1]).toEqual({ method: "getBuffer", args: ["custom:redis:key:path"] });
  });
});
