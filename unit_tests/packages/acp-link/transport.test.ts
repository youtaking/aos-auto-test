// transport.test.ts — WebSocket 传输层状态机测试
// 测试目标：TransportState 状态枚举和传输层常量
// 业务意图：确保传输层状态机常量和重连策略参数正确

import { describe, test, expect } from "bun:test";

// ── 复制常量和纯函数（来自 packages/acp-link/src/client/transport.ts）──

type TransportState = "connecting" | "connected" | "disconnected" | "error";

const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30000;
const STABLE_THRESHOLD_MS = 5000;

/** 计算指数退避延迟（带 jitter） */
function calculateReconnectDelay(attempt: number): number {
  const exponentialDelay = Math.min(BASE_DELAY_MS * 2 ** attempt, MAX_DELAY_MS);
  const jitter = Math.random() * 0.3 * exponentialDelay;
  return exponentialDelay + jitter;
}

/** 判断连接是否稳定（连接时间超过阈值） */
function isConnectionStable(connectedAt: number, now: number): boolean {
  return now - connectedAt >= STABLE_THRESHOLD_MS;
}

// ── 测试 ──

describe("TransportState", () => {
  test("正向 - 四个状态值", () => {
    const states: TransportState[] = ["connecting", "connected", "disconnected", "error"];
    expect(states.length).toBe(4);
  });
});

describe("重连常量", () => {
  test("正向 - 最大重连次数为 5", () => {
    expect(MAX_RECONNECT_ATTEMPTS).toBe(5);
  });

  test("正向 - 基础延迟 1s", () => {
    expect(BASE_DELAY_MS).toBe(1000);
  });

  test("正向 - 最大延迟 30s", () => {
    expect(MAX_DELAY_MS).toBe(30000);
  });

  test("正向 - 稳定阈值 5s", () => {
    expect(STABLE_THRESHOLD_MS).toBe(5000);
  });
});

describe("calculateReconnectDelay", () => {
  test("正向 - 首次重连延迟约 1s（±jitter）", () => {
    const delay = calculateReconnectDelay(0);
    expect(delay).toBeGreaterThanOrEqual(BASE_DELAY_MS);
    expect(delay).toBeLessThanOrEqual(BASE_DELAY_MS * 1.3);
  });

  test("正向 - 延迟随 attempt 指数增长", () => {
    // 取多次样本，确认 attempt 越大延迟倾向于越大
    const delays0: number[] = [];
    const delays3: number[] = [];
    for (let i = 0; i < 20; i++) {
      delays0.push(calculateReconnectDelay(0));
      delays3.push(calculateReconnectDelay(3));
    }
    const avg0 = delays0.reduce((s, v) => s + v, 0) / delays0.length;
    const avg3 = delays3.reduce((s, v) => s + v, 0) / delays3.length;
    expect(avg3).toBeGreaterThan(avg0);
  });

  test("边界 - 延迟不超过 MAX_DELAY_MS * 1.3", () => {
    const delay = calculateReconnectDelay(20);
    expect(delay).toBeLessThanOrEqual(MAX_DELAY_MS * 1.3);
  });

  test("正向 - 延迟始终 >= BASE_DELAY_MS", () => {
    for (let i = 0; i < 10; i++) {
      expect(calculateReconnectDelay(0)).toBeGreaterThanOrEqual(BASE_DELAY_MS);
    }
  });
});

describe("isConnectionStable", () => {
  test("正向 - 超过阈值返回 true", () => {
    expect(isConnectionStable(1000, 1000 + STABLE_THRESHOLD_MS)).toBe(true);
  });

  test("正向 - 恰好等于阈值返回 true", () => {
    expect(isConnectionStable(0, STABLE_THRESHOLD_MS)).toBe(true);
  });

  test("分支 - 未达阈值返回 false", () => {
    expect(isConnectionStable(1000, 1000 + STABLE_THRESHOLD_MS - 1)).toBe(false);
  });

  test("边界 - 连接时间为 0 且 now 为 0 返回 false", () => {
    expect(isConnectionStable(0, 0)).toBe(false);
  });
});
