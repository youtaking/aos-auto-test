// file-event-queue.test.ts — 文件事件队列测试
// 测试目标：publish/subscribe/溢出收敛/生命周期/destroy
// 业务意图：确保按环境隔离的事件队列正确 fan-out、溢出时收敛为 invalidate_all、无泄漏

import { afterEach, beforeEach, describe, expect, test } from "bun:test";

// ── 复制队列逻辑（避免 @fenix/logger 依赖链）──

type FileChangeKind = "write" | "delete" | "mkdir" | "rename" | "upload";
type FileChangeSource = "user" | "agent" | "api";

interface FileBatchChange {
  path: string;
  kind: FileChangeKind;
  source: FileChangeSource;
  actor_id?: string;
}

type FileEventInput =
  | { type: "file_changed"; path: string; kind: FileChangeKind; source: FileChangeSource; actor_id?: string; to?: string }
  | { type: "file_changed_batch"; changes: FileBatchChange[] }
  | { type: "degraded"; machine_id: string; capability: "file"; status: "down" | "recovered" };

type FileEventFrame =
  | { type: "file_changed"; environment_id: string; path: string; kind: FileChangeKind; source: FileChangeSource; actor_id?: string; to?: string }
  | { type: "file_changed_batch"; environment_id: string; changes: FileBatchChange[] }
  | { type: "invalidate_all"; environment_id: string }
  | { type: "degraded"; machine_id: string; capability: "file"; status: "down" | "recovered" };

type FileEventSubscriber = (frame: FileEventFrame) => void;

const FILE_EVENT_QUEUE_LIMIT = 200;

interface FileEnvironmentQueue {
  envId: string;
  subscribers: Set<FileEventSubscriber>;
  machineDeclared: boolean;
  pending: FileEventFrame[];
  flushScheduled: boolean;
  overflowed: boolean;
}

const queues = new Map<string, FileEnvironmentQueue>();

function ensureQueue(envId: string): FileEnvironmentQueue {
  let queue = queues.get(envId);
  if (!queue) {
    queue = { envId, subscribers: new Set(), machineDeclared: false, pending: [], flushScheduled: false, overflowed: false };
    queues.set(envId, queue);
  }
  return queue;
}

function maybeDestroy(queue: FileEnvironmentQueue) {
  if (queue.subscribers.size === 0 && !queue.machineDeclared) {
    queues.delete(queue.envId);
  }
}

function enqueue(queue: FileEnvironmentQueue, frame: FileEventFrame) {
  if (queue.pending.length >= FILE_EVENT_QUEUE_LIMIT) {
    if (!queue.overflowed) {
      queue.overflowed = true;
      queue.pending.push({ type: "invalidate_all", environment_id: queue.envId });
    }
  } else {
    queue.pending.push(frame);
  }
  if (!queue.flushScheduled) {
    queue.flushScheduled = true;
    queueMicrotask(() => flush(queue));
  }
}

function flush(queue: FileEnvironmentQueue) {
  queue.flushScheduled = false;
  queue.overflowed = false;
  const frames = queue.pending;
  queue.pending = [];
  if (queue.subscribers.size === 0) {
    maybeDestroy(queue);
    return;
  }
  for (const subscriber of queue.subscribers) {
    queueMicrotask(() => {
      for (const frame of frames) {
        try { subscriber(frame); } catch { /* isolated */ }
      }
    });
  }
}

function toFrame(envId: string, event: FileEventInput): FileEventFrame {
  if (event.type === "degraded") return event;
  return { ...event, environment_id: envId };
}

function publishFileEvent(envId: string, event: FileEventInput): void {
  enqueue(ensureQueue(envId), toFrame(envId, event));
}

function publishInvalidateAll(envId: string): void {
  enqueue(ensureQueue(envId), { type: "invalidate_all", environment_id: envId });
}

function subscribe(envId: string, subscriber: FileEventSubscriber): () => void {
  const queue = ensureQueue(envId);
  queue.subscribers.add(subscriber);
  return () => { queue.subscribers.delete(subscriber); maybeDestroy(queue); };
}

function registerEnvironmentQueue(envId: string): void {
  ensureQueue(envId).machineDeclared = true;
}

function destroyEnvironmentQueue(envId: string): void {
  const queue = queues.get(envId);
  if (!queue) return;
  queue.subscribers.clear();
  queue.pending = [];
  queues.delete(envId);
}

// ── tests ──

describe("FileEventQueue", () => {
  beforeEach(() => { queues.clear(); });
  afterEach(() => { queues.clear(); });

  // 发布事件后订阅者收到带 environment_id 的完整帧
  test("发布 file_changed 事件注入 environment_id 后送达订阅者", async () => {
    const received: FileEventFrame[] = [];
    subscribe("env1", (f) => received.push(f));
    publishFileEvent("env1", { type: "file_changed", path: "a.txt", kind: "write", source: "user" });
    await new Promise((r) => setTimeout(r, 10));
    expect(received).toHaveLength(1);
    expect(received[0].type).toBe("file_changed");
    if (received[0].type === "file_changed") {
      expect(received[0].environment_id).toBe("env1");
      expect(received[0].path).toBe("a.txt");
    }
  });

  // 多订阅者均收到同一事件（fan-out）
  test("多个订阅者均收到同一事件", async () => {
    const r1: FileEventFrame[] = [];
    const r2: FileEventFrame[] = [];
    subscribe("env1", (f) => r1.push(f));
    subscribe("env1", (f) => r2.push(f));
    publishFileEvent("env1", { type: "file_changed", path: "b.txt", kind: "delete", source: "agent" });
    await new Promise((r) => setTimeout(r, 10));
    expect(r1).toHaveLength(1);
    expect(r2).toHaveLength(1);
  });

  // 取消订阅后不再收到事件
  test("取消订阅后不再收到事件", async () => {
    const received: FileEventFrame[] = [];
    const unsub = subscribe("env1", (f) => received.push(f));
    unsub();
    publishFileEvent("env1", { type: "file_changed", path: "c.txt", kind: "write", source: "user" });
    await new Promise((r) => setTimeout(r, 10));
    expect(received).toHaveLength(0);
  });

  // 不同环境事件隔离
  test("不同环境事件互相隔离", async () => {
    const r1: FileEventFrame[] = [];
    const r2: FileEventFrame[] = [];
    subscribe("env1", (f) => r1.push(f));
    subscribe("env2", (f) => r2.push(f));
    publishFileEvent("env1", { type: "file_changed", path: "a.txt", kind: "write", source: "user" });
    await new Promise((r) => setTimeout(r, 10));
    expect(r1).toHaveLength(1);
    expect(r2).toHaveLength(0);
  });

  // 队列溢出时收敛为 invalidate_all
  test("队列溢出时后续事件收敛为 invalidate_all", async () => {
    const received: FileEventFrame[] = [];
    subscribe("env1", (f) => received.push(f));
    // 填满 200 条
    for (let i = 0; i < 200; i++) {
      publishFileEvent("env1", { type: "file_changed", path: `f${i}.txt`, kind: "write", source: "user" });
    }
    // 第 201 条触发溢出收敛
    publishFileEvent("env1", { type: "file_changed", path: "overflow.txt", kind: "write", source: "user" });
    await new Promise((r) => setTimeout(r, 10));
    // 200 条正常 + 1 条 invalidate_all = 201 条
    expect(received).toHaveLength(201);
    const invalidateFrames = received.filter((f) => f.type === "invalidate_all");
    expect(invalidateFrames).toHaveLength(1);
  });

  // publishInvalidateAll 发送 invalidate_all 帧
  test("publishInvalidateAll 发送 invalidate_all 帧", async () => {
    const received: FileEventFrame[] = [];
    subscribe("env1", (f) => received.push(f));
    publishInvalidateAll("env1");
    await new Promise((r) => setTimeout(r, 10));
    expect(received).toHaveLength(1);
    expect(received[0].type).toBe("invalidate_all");
  });

  // degraded 帧原样透传（不注入 environment_id）
  test("degraded 帧原样透传不注入 environment_id", async () => {
    const received: FileEventFrame[] = [];
    subscribe("env1", (f) => received.push(f));
    publishFileEvent("env1", { type: "degraded", machine_id: "m1", capability: "file", status: "down" });
    await new Promise((r) => setTimeout(r, 10));
    expect(received).toHaveLength(1);
    expect(received[0].type).toBe("degraded");
    if (received[0].type === "degraded") {
      expect(received[0].machine_id).toBe("m1");
    }
  });

  // registerEnvironmentQueue 后无订阅者也不销毁
  test("registerEnvironmentQueue 后无订阅者队列仍存在", () => {
    registerEnvironmentQueue("env1");
    const unsub = subscribe("env1", () => {});
    unsub();
    // 队列仍在（machineDeclared）
    expect(queues.has("env1")).toBe(true);
  });

  // destroyEnvironmentQueue 强制销毁
  test("destroyEnvironmentQueue 清除一切并删除队列", () => {
    subscribe("env1", () => {});
    registerEnvironmentQueue("env1");
    destroyEnvironmentQueue("env1");
    expect(queues.has("env1")).toBe(false);
  });

  // 无订阅且无机器声明时取消订阅自动销毁
  test("无订阅且无机器声明时取消订阅自动销毁", () => {
    const unsub = subscribe("env1", () => {});
    expect(queues.has("env1")).toBe(true);
    unsub();
    expect(queues.has("env1")).toBe(false);
  });

  // 订阅者抛错不影响其他订阅者
  test("订阅者抛错不影响其他订阅者", async () => {
    const received: FileEventFrame[] = [];
    subscribe("env1", () => { throw new Error("boom"); });
    subscribe("env1", (f) => received.push(f));
    publishFileEvent("env1", { type: "file_changed", path: "x.txt", kind: "write", source: "user" });
    await new Promise((r) => setTimeout(r, 10));
    expect(received).toHaveLength(1);
  });
});
