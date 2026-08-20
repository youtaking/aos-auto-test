// acp-idle-monitor.test.ts — ACP 空闲监控纯逻辑测试
// 测试目标：shouldCountInstanceActivity、消息分类、空闲判定
// 业务意图：确保保活消息不计入活跃度，idle sweep 逻辑正确

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数 ──

function isIgnoredActivityMessageType(type: string | undefined): boolean {
  return type === "keep_alive" || type === "heartbeat" || type === "ping" || type === "pong";
}

function shouldCountInstanceActivity(message: Record<string, unknown>): boolean {
  if ((message.jsonrpc as string | undefined) === "2.0") return true;
  return !isIgnoredActivityMessageType(message.type as string | undefined);
}

// ── 空闲判定辅助 ──

interface IdleCheckInput {
  lastActivityAt: number;
  lastRelayDetachedAt: number | null;
  relayCount: number;
  spawnSource: string;
  now: number;
  idleTimeoutMs: number;
  activityTimeoutMs: number;
}

function classifyIdleState(input: IdleCheckInput): {
  shouldStop: boolean;
  reason: "inactive" | "idle" | null;
} {
  // interactive 实例不自动回收
  if (input.spawnSource === "interactive") return { shouldStop: false, reason: null };

  // activity 超时：后台任务长时间无消息
  const inactiveTooLong = input.now - input.lastActivityAt >= input.activityTimeoutMs;
  if (inactiveTooLong) return { shouldStop: true, reason: "inactive" };

  // idle 回收：必须无 relay 且超过 idle 超时
  if (input.relayCount > 0) return { shouldStop: false, reason: null };

  const idleSince = Math.max(input.lastActivityAt, input.lastRelayDetachedAt ?? 0);
  if (input.now - idleSince < input.idleTimeoutMs) return { shouldStop: false, reason: null };

  return { shouldStop: true, reason: "idle" };
}

// ── tests ──

describe("acp-idle-monitor 空闲监控", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("shouldCountInstanceActivity 消息活跃度判定", () => {
    test("keep_alive 不计入活跃度", () => {
      expect(shouldCountInstanceActivity({ type: "keep_alive" })).toBe(false);
    });

    test("heartbeat 不计入活跃度", () => {
      expect(shouldCountInstanceActivity({ type: "heartbeat" })).toBe(false);
    });

    test("ping 不计入活跃度", () => {
      expect(shouldCountInstanceActivity({ type: "ping" })).toBe(false);
    });

    test("pong 不计入活跃度", () => {
      expect(shouldCountInstanceActivity({ type: "pong" })).toBe(false);
    });

    test("JSON-RPC 2.0 消息计入活跃度", () => {
      expect(shouldCountInstanceActivity({ jsonrpc: "2.0", method: "session/prompt" })).toBe(true);
    });

    test("普通业务消息计入活跃度", () => {
      expect(shouldCountInstanceActivity({ type: "session_data" })).toBe(true);
    });

    test("relay_closed 计入活跃度", () => {
      expect(shouldCountInstanceActivity({ type: "relay_closed" })).toBe(true);
    });

    test("error 计入活跃度", () => {
      expect(shouldCountInstanceActivity({ type: "error" })).toBe(true);
    });

    test("无 type 无 jsonrpc 计入活跃度", () => {
      expect(shouldCountInstanceActivity({})).toBe(true);
    });

    test("JSON-RPC 覆盖保活类型仍计入", () => {
      expect(shouldCountInstanceActivity({ jsonrpc: "2.0", type: "keep_alive" })).toBe(true);
    });

    test("prepare_result 计入活跃度", () => {
      expect(shouldCountInstanceActivity({ type: "prepare_result" })).toBe(true);
    });

    test("session_started 计入活跃度", () => {
      expect(shouldCountInstanceActivity({ type: "session_started" })).toBe(true);
    });
  });

  describe("classifyIdleState 空闲状态分类", () => {
    const baseInput: IdleCheckInput = {
      lastActivityAt: 1000,
      lastRelayDetachedAt: null,
      relayCount: 0,
      spawnSource: "scheduled",
      now: 100_000,
      idleTimeoutMs: 60_000,
      activityTimeoutMs: 120_000,
    };

    test("interactive 实例不回收", () => {
      const result = classifyIdleState({ ...baseInput, spawnSource: "interactive" });
      expect(result.shouldStop).toBe(false);
      expect(result.reason).toBeNull();
    });

    test("scheduled 实例 activity 超时回收", () => {
      const result = classifyIdleState({
        ...baseInput,
        lastActivityAt: 1000,
        now: 200_000,
        activityTimeoutMs: 120_000,
      });
      expect(result.shouldStop).toBe(true);
      expect(result.reason).toBe("inactive");
    });

    test("system 实例 activity 超时回收", () => {
      const result = classifyIdleState({
        ...baseInput,
        spawnSource: "system",
        lastActivityAt: 1000,
        now: 200_000,
        activityTimeoutMs: 120_000,
      });
      expect(result.shouldStop).toBe(true);
      expect(result.reason).toBe("inactive");
    });

    test("relay_count > 0 阻止 idle 回收但不阻止 activity 回收", () => {
      // activity 未超时但 idle 超时 + relay_count > 0 → 不回收
      const resultIdle = classifyIdleState({
        ...baseInput,
        lastActivityAt: 50_000,
        relayCount: 1,
        now: 120_000,
      });
      expect(resultIdle.shouldStop).toBe(false);

      // activity 超时 + relay_count > 0 → 仍回收
      const resultActivity = classifyIdleState({
        ...baseInput,
        lastActivityAt: 1000,
        relayCount: 1,
        now: 200_000,
        activityTimeoutMs: 120_000,
      });
      expect(resultActivity.shouldStop).toBe(true);
      expect(resultActivity.reason).toBe("inactive");
    });

    test("无 relay 且 idle 超时回收", () => {
      const result = classifyIdleState({
        ...baseInput,
        lastActivityAt: 10_000,
        lastRelayDetachedAt: 15_000,
        relayCount: 0,
        now: 100_000,
        idleTimeoutMs: 60_000,
        activityTimeoutMs: 200_000,
      });
      expect(result.shouldStop).toBe(true);
      expect(result.reason).toBe("idle");
    });

    test("idle 时间取 max(lastActivityAt, lastRelayDetachedAt)", () => {
      // relay 断开时间晚于 lastActivityAt → idle 从 relay 断开算起
      const result1 = classifyIdleState({
        ...baseInput,
        lastActivityAt: 10_000,
        lastRelayDetachedAt: 50_000,
        relayCount: 0,
        now: 100_000,
        idleTimeoutMs: 60_000,
        activityTimeoutMs: 200_000,
      });
      // idle 从 50_000 算起，now=100_000，idle=50_000 < 60_000 → 不回收
      expect(result1.shouldStop).toBe(false);

      // lastActivityAt 晚于 relay 断开 → idle 从 activity 算起
      const result2 = classifyIdleState({
        ...baseInput,
        lastActivityAt: 50_000,
        lastRelayDetachedAt: 10_000,
        relayCount: 0,
        now: 120_000,
        idleTimeoutMs: 60_000,
        activityTimeoutMs: 200_000,
      });
      // idle 从 50_000 算起，now=120_000，idle=70_000 > 60_000 → 回收
      expect(result2.shouldStop).toBe(true);
      expect(result2.reason).toBe("idle");
    });

    test("恰好等于 idle 阈值时不回收", () => {
      const result = classifyIdleState({
        ...baseInput,
        lastActivityAt: 40_000,
        lastRelayDetachedAt: null,
        relayCount: 0,
        now: 100_000,
        idleTimeoutMs: 60_000,
        activityTimeoutMs: 200_000,
      });
      // idle = 100_000 - 40_000 = 60_000 = idleTimeoutMs → 不小于，所以回收
      expect(result.shouldStop).toBe(true);
    });
  });
});
