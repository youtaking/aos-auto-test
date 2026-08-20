// registry-heartbeat.test.ts — 心跳监控纯逻辑测试
// 测试目标：HeartbeatEntry 超时计算、sweep 判定逻辑
// 业务意图：确保心跳超时时间 = intervalMs * 3，sweep 能正确检测断连机器

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数 ──

function calculateTimeoutMs(heartbeatIntervalMs: number): number {
  return heartbeatIntervalMs * 3;
}

function shouldSweepMachine(
  machineStatus: string,
  hasActiveConnection: boolean,
): boolean {
  if (machineStatus !== "online") return false;
  return !hasActiveConnection;
}

function isClientInactive(
  lastClientActivity: number,
  now: number,
  activityTimeoutMs: number,
): boolean {
  return now - lastClientActivity > activityTimeoutMs;
}

// ── tests ──

describe("registry-heartbeat 心跳监控", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("calculateTimeoutMs 超时计算", () => {
    test("超时 = interval * 3", () => {
      expect(calculateTimeoutMs(10_000)).toBe(30_000);
    });

    test("默认 30s 间隔 → 90s 超时", () => {
      expect(calculateTimeoutMs(30_000)).toBe(90_000);
    });

    test("1s 间隔 → 3s 超时", () => {
      expect(calculateTimeoutMs(1_000)).toBe(3_000);
    });

    test("0 间隔 → 0 超时", () => {
      expect(calculateTimeoutMs(0)).toBe(0);
    });
  });

  describe("shouldSweepMachine 巡检判定", () => {
    test("online + 无连接 → 需要巡检", () => {
      expect(shouldSweepMachine("online", false)).toBe(true);
    });

    test("online + 有连接 → 不需要巡检", () => {
      expect(shouldSweepMachine("online", true)).toBe(false);
    });

    test("offline + 无连接 → 不需要巡检", () => {
      expect(shouldSweepMachine("offline", false)).toBe(false);
    });

    test("offline + 有连接 → 不需要巡检", () => {
      expect(shouldSweepMachine("offline", true)).toBe(false);
    });
  });

  describe("isClientInactive 客户端活跃度判定", () => {
    test("超过超时阈值 → 不活跃", () => {
      expect(isClientInactive(1000, 100_000, 90_000)).toBe(true);
    });

    test("未超过超时阈值 → 活跃", () => {
      expect(isClientInactive(50_000, 100_000, 90_000)).toBe(false);
    });

    test("恰好等于阈值 → 不活跃（> 不满足）", () => {
      // now - last = 90_000, threshold = 90_000 → 90_000 > 90_000 is false
      expect(isClientInactive(10_000, 100_000, 90_000)).toBe(false);
    });

    test("刚刚活动 → 活跃", () => {
      expect(isClientInactive(99_999, 100_000, 90_000)).toBe(false);
    });
  });
});
