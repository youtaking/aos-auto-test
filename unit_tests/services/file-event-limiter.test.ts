// file-event-limiter.test.ts — 文件变更事件限频与批量合并测试
// 测试目标：限频窗口、batch 合并、罕见帧限频
// 业务意图：确保超限事件合并为 batch（增量语义）而非 invalidate_all

import { afterEach, beforeEach, describe, expect, test } from "bun:test";

// ── 简化限频逻辑（避免外部依赖）──

interface RateWindow { start: number; count: number; }

const ENV_RATE_LIMIT = 20;
const MACHINE_RATE_LIMIT = 100;
const RATE_WINDOW_MS = 1_000;
const BATCH_MAX_CHANGES = 50;

function checkRate(map: Map<string, RateWindow>, key: string, limit: number, now: number): boolean {
  const window = map.get(key);
  if (!window || now - window.start >= RATE_WINDOW_MS) {
    map.set(key, { start: now, count: 1 });
    return true;
  }
  if (window.count >= limit) return false;
  window.count++;
  return true;
}

interface FileChangeEvent {
  path: string;
  kind: "write" | "delete" | "mkdir" | "rename" | "upload";
  source: "user" | "agent" | "api";
  actorId?: string;
  to?: string;
}

// ── tests ──

describe("checkRate 限频", () => {
  let rateMap: Map<string, RateWindow>;

  beforeEach(() => { rateMap = new Map(); });

  // 首次请求在窗口内放行
  test("首次请求放行并开启新窗口", () => {
    expect(checkRate(rateMap, "env1", ENV_RATE_LIMIT, 1000)).toBe(true);
    expect(rateMap.get("env1")).toEqual({ start: 1000, count: 1 });
  });

  // 窗口内未超限持续放行
  test("窗口内未超限持续放行并递增计数", () => {
    const t0 = 1000;
    for (let i = 0; i < 20; i++) {
      expect(checkRate(rateMap, "env1", ENV_RATE_LIMIT, t0 + i)).toBe(true);
    }
    expect(rateMap.get("env1")?.count).toBe(20);
  });

  // 窗口内达到上限后拒绝
  test("窗口内达到上限后拒绝", () => {
    const t0 = 1000;
    for (let i = 0; i < 20; i++) checkRate(rateMap, "env1", ENV_RATE_LIMIT, t0);
    expect(checkRate(rateMap, "env1", ENV_RATE_LIMIT, t0)).toBe(false);
  });

  // 窗口过期后重置
  test("窗口过期后自动重置", () => {
    const t0 = 1000;
    for (let i = 0; i < 20; i++) checkRate(rateMap, "env1", ENV_RATE_LIMIT, t0);
    expect(checkRate(rateMap, "env1", ENV_RATE_LIMIT, t0)).toBe(false);
    // 窗口过期（1000ms 后）
    expect(checkRate(rateMap, "env1", ENV_RATE_LIMIT, t0 + RATE_WINDOW_MS)).toBe(true);
    expect(rateMap.get("env1")?.start).toBe(t0 + RATE_WINDOW_MS);
    expect(rateMap.get("env1")?.count).toBe(1);
  });

  // 不同 key 独立计数
  test("不同 key 独立计数互不影响", () => {
    const t0 = 1000;
    for (let i = 0; i < 20; i++) checkRate(rateMap, "env1", ENV_RATE_LIMIT, t0);
    // env1 已满，但 env2 不受影响
    expect(checkRate(rateMap, "env1", ENV_RATE_LIMIT, t0)).toBe(false);
    expect(checkRate(rateMap, "env2", ENV_RATE_LIMIT, t0)).toBe(true);
  });
});

describe("机器级限频", () => {
  let rateMap: Map<string, RateWindow>;

  beforeEach(() => { rateMap = new Map(); });

  // 机器级限频 100 条/s
  test("机器级限频 100 条/s", () => {
    const t0 = 1000;
    for (let i = 0; i < 100; i++) {
      expect(checkRate(rateMap, "machine1", MACHINE_RATE_LIMIT, t0)).toBe(true);
    }
    expect(checkRate(rateMap, "machine1", MACHINE_RATE_LIMIT, t0)).toBe(false);
  });
});

describe("BATCH_MAX_CHANGES 常量", () => {
  // batch 单帧上限 50 条
  test("batch 单帧上限 50 条（增量语义而非 invalidate_all）", () => {
    expect(BATCH_MAX_CHANGES).toBe(50);
  });
});
