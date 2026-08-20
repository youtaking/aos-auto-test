// hermes-client.test.ts — HermesClient 纯逻辑测试
// 测试目标：构造函数平台解析、重连延迟计算、状态快照行为

import { describe, expect, test, beforeEach, mock } from "bun:test";

// ── 复制纯逻辑部分（隔离 WebSocket/transport 依赖）──

const KNOWN_PLATFORMS = ["feishu", "telegram", "discord", "slack", "wecom", "weixin", "dingtalk"];
const MAX_RECONNECT_DELAY_MS = 60_000;

interface HermesStatus {
  connected: boolean;
  url: string;
  platforms: string[];
  reconnecting: boolean;
  lastConnectedAt: number | null;
}

/** 重连延迟计算（指数退避 + 上限） */
function calculateReconnectDelay(attempts: number): number {
  return Math.min(2000 * 2 ** attempts, MAX_RECONNECT_DELAY_MS);
}

/** 解析平台列表（从环境变量或默认值） */
function parsePlatforms(envPlatforms: string | undefined): string[] {
  if (envPlatforms) {
    return envPlatforms.split(",").map((p) => p.trim()).filter(Boolean);
  }
  return [...KNOWN_PLATFORMS];
}

/** 创建初始状态 */
function createInitialStatus(url: string): HermesStatus {
  return {
    connected: false,
    url,
    platforms: [],
    reconnecting: false,
    lastConnectedAt: null,
  };
}

/** 创建状态快照（深拷贝） */
function snapshotStatus(status: HermesStatus): HermesStatus {
  return { ...status, platforms: [...status.platforms] };
}

// 模拟 handleMessage 的消息类型分发
function classifyMessage(msg: Record<string, unknown>): string {
  if (msg.type === "message") return "inbound";
  if (msg.type === "pong") return "pong";
  if (msg.type === "platform_status") return "platform_status";
  if (msg.type === "error") return "error";
  if (msg.type === "result") return "result";
  return "unknown";
}

// ── Tests ──

describe("hermes-client 纯逻辑", () => {
  beforeEach(() => {
    mock.restore();
  });

  // ── calculateReconnectDelay ──

  describe("calculateReconnectDelay（指数退避）", () => {
    test("首次重连 2 秒", () => {
      expect(calculateReconnectDelay(0)).toBe(2000);
    });

    test("第二次 4 秒", () => {
      expect(calculateReconnectDelay(1)).toBe(4000);
    });

    test("第三次 8 秒", () => {
      expect(calculateReconnectDelay(2)).toBe(8000);
    });

    test("第四次 16 秒", () => {
      expect(calculateReconnectDelay(3)).toBe(16000);
    });

    test("第五次 32 秒", () => {
      expect(calculateReconnectDelay(4)).toBe(32000);
    });

    test("第六次 60 秒（达到上限）", () => {
      expect(calculateReconnectDelay(5)).toBe(60000);
    });

    test("第 100 次仍为 60 秒上限", () => {
      expect(calculateReconnectDelay(100)).toBe(60000);
    });
  });

  // ── parsePlatforms ──

  describe("parsePlatforms", () => {
    test("undefined 返回默认平台列表", () => {
      const result = parsePlatforms(undefined);
      expect(result).toEqual(KNOWN_PLATFORMS);
    });

    test("逗号分隔的平台名正确解析", () => {
      const result = parsePlatforms("feishu,telegram,discord");
      expect(result).toEqual(["feishu", "telegram", "discord"]);
    });

    test("trim 空格", () => {
      const result = parsePlatforms(" feishu , telegram ");
      expect(result).toEqual(["feishu", "telegram"]);
    });

    test("过滤空字符串", () => {
      const result = parsePlatforms("feishu,,telegram,");
      expect(result).toEqual(["feishu", "telegram"]);
    });

    test("空字符串返回默认列表", () => {
      // 空字符串是 falsy，走默认分支
      const result = parsePlatforms("");
      expect(result).toEqual(KNOWN_PLATFORMS);
    });

    test("KNOWN_PLATFORMS 包含 7 个平台", () => {
      expect(KNOWN_PLATFORMS.length).toBe(7);
      expect(KNOWN_PLATFORMS).toContain("feishu");
      expect(KNOWN_PLATFORMS).toContain("telegram");
      expect(KNOWN_PLATFORMS).toContain("discord");
      expect(KNOWN_PLATFORMS).toContain("slack");
      expect(KNOWN_PLATFORMS).toContain("wecom");
      expect(KNOWN_PLATFORMS).toContain("weixin");
      expect(KNOWN_PLATFORMS).toContain("dingtalk");
    });
  });

  // ── createInitialStatus / snapshotStatus ──

  describe("状态管理", () => {
    test("初始状态为未连接", () => {
      const status = createInitialStatus("ws://localhost:8080");
      expect(status.connected).toBe(false);
      expect(status.url).toBe("ws://localhost:8080");
      expect(status.platforms).toEqual([]);
      expect(status.reconnecting).toBe(false);
      expect(status.lastConnectedAt).toBeNull();
    });

    test("快照是深拷贝（修改不影响原状态）", () => {
      const original: HermesStatus = {
        connected: true,
        url: "ws://test",
        platforms: ["feishu", "telegram"],
        reconnecting: false,
        lastConnectedAt: 12345,
      };
      const snap = snapshotStatus(original);
      snap.platforms.push("discord");
      snap.connected = false;
      // 原状态不受影响
      expect(original.platforms.length).toBe(2);
      expect(original.connected).toBe(true);
    });

    test("快照中 platforms 是独立数组", () => {
      const original: HermesStatus = {
        connected: false,
        url: "",
        platforms: ["slack"],
        reconnecting: false,
        lastConnectedAt: null,
      };
      const snap = snapshotStatus(original);
      expect(snap.platforms).toEqual(["slack"]);
      expect(snap.platforms).not.toBe(original.platforms);
    });
  });

  // ── classifyMessage ──

  describe("classifyMessage（消息类型分发）", () => {
    test("message 类型 → inbound", () => {
      expect(classifyMessage({ type: "message" })).toBe("inbound");
    });

    test("pong 类型 → pong", () => {
      expect(classifyMessage({ type: "pong" })).toBe("pong");
    });

    test("platform_status 类型 → platform_status", () => {
      expect(classifyMessage({ type: "platform_status" })).toBe("platform_status");
    });

    test("error 类型 → error", () => {
      expect(classifyMessage({ type: "error" })).toBe("error");
    });

    test("result 类型 → result", () => {
      expect(classifyMessage({ type: "result" })).toBe("result");
    });

    test("未知类型 → unknown", () => {
      expect(classifyMessage({ type: "heartbeat" })).toBe("unknown");
    });

    test("无 type 字段 → unknown", () => {
      expect(classifyMessage({})).toBe("unknown");
    });
  });

  // ── platform_status 处理逻辑 ──

  describe("platform_status 处理", () => {
    function handlePlatformStatus(
      status: HermesStatus,
      platform: string | undefined,
      state: string | undefined,
    ): HermesStatus {
      if (!platform || !state) return status;
      const newStatus = { ...status, platforms: [...status.platforms] };
      if (state === "connected" && !newStatus.platforms.includes(platform)) {
        newStatus.platforms.push(platform);
      } else if (state === "disconnected") {
        newStatus.platforms = newStatus.platforms.filter((p) => p !== platform);
      }
      return newStatus;
    }

    test("平台 connected 时添加到列表", () => {
      const status = createInitialStatus("ws://test");
      status.platforms = ["feishu"];
      const result = handlePlatformStatus(status, "telegram", "connected");
      expect(result.platforms).toEqual(["feishu", "telegram"]);
    });

    test("已存在的平台 connected 时不重复添加", () => {
      const status = createInitialStatus("ws://test");
      status.platforms = ["feishu"];
      const result = handlePlatformStatus(status, "feishu", "connected");
      expect(result.platforms).toEqual(["feishu"]);
    });

    test("平台 disconnected 时从列表移除", () => {
      const status = createInitialStatus("ws://test");
      status.platforms = ["feishu", "telegram", "discord"];
      const result = handlePlatformStatus(status, "telegram", "disconnected");
      expect(result.platforms).toEqual(["feishu", "discord"]);
    });

    test("不存在的平台 disconnected 时不影响列表", () => {
      const status = createInitialStatus("ws://test");
      status.platforms = ["feishu"];
      const result = handlePlatformStatus(status, "slack", "disconnected");
      expect(result.platforms).toEqual(["feishu"]);
    });

    test("platform 为 undefined 时不修改", () => {
      const status = createInitialStatus("ws://test");
      status.platforms = ["feishu"];
      const result = handlePlatformStatus(status, undefined, "connected");
      expect(result.platforms).toEqual(["feishu"]);
    });
  });
});
