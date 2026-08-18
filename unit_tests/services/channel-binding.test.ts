// channel-binding.test.ts — 频道绑定消息匹配测试
// 测试目标：findBindingForMessage 的精确匹配、通配符匹配、优先级、过滤逻辑
// 业务意图：确保消息路由到正确的 Agent 频道绑定

import { describe, expect, test } from "bun:test";

// ── 复制纯函数（无外部依赖）──

interface ChannelBinding {
  id: string;
  platform: string;
  chatId: string | null;
  agentId: string;
  enabled: boolean;
}

interface BindingMatchResult {
  binding: ChannelBinding;
  matchType: "exact" | "wildcard";
}

function findBindingForMessage(
  bindings: ChannelBinding[],
  platform: string,
  chatId: string,
): BindingMatchResult | undefined {
  const enabledBindings = bindings.filter((b) => b.platform === platform && b.enabled);

  const exact = enabledBindings.find((b) => b.chatId === chatId);
  if (exact) return { binding: exact, matchType: "exact" };

  const wildcard = enabledBindings.find((b) => b.chatId === null);
  if (wildcard) return { binding: wildcard, matchType: "wildcard" };

  return undefined;
}

// ── 辅助工厂 ──

function makeBinding(overrides: Partial<ChannelBinding> = {}): ChannelBinding {
  return {
    id: "bind-1",
    platform: "dingtalk",
    chatId: "chat-123",
    agentId: "agent-1",
    enabled: true,
    ...overrides,
  };
}

// ── tests ──

describe("ChannelBinding 消息匹配", () => {
  // ── 精确匹配 ──

  describe("精确匹配（exact）", () => {
    test("chatId 完全匹配时返回 exact", () => {
      const bindings = [makeBinding({ id: "bind-1", chatId: "chat-123" })];
      const result = findBindingForMessage(bindings, "dingtalk", "chat-123");
      expect(result).toBeDefined();
      expect(result!.matchType).toBe("exact");
      expect(result!.binding.id).toBe("bind-1");
    });

    test("多个绑定中精确匹配优先于通配符", () => {
      const bindings = [
        makeBinding({ id: "wildcard", chatId: null, agentId: "agent-wild" }),
        makeBinding({ id: "exact", chatId: "chat-123", agentId: "agent-exact" }),
      ];
      const result = findBindingForMessage(bindings, "dingtalk", "chat-123");
      expect(result).toBeDefined();
      expect(result!.matchType).toBe("exact");
      expect(result!.binding.id).toBe("exact");
    });

    test("精确匹配返回对应的 agentId", () => {
      const bindings = [
        makeBinding({ id: "bind-a", chatId: "chat-a", agentId: "agent-a" }),
        makeBinding({ id: "bind-b", chatId: "chat-b", agentId: "agent-b" }),
      ];
      const result = findBindingForMessage(bindings, "dingtalk", "chat-b");
      expect(result!.binding.agentId).toBe("agent-b");
    });
  });

  // ── 通配符匹配 ──

  describe("通配符匹配（wildcard）", () => {
    test("chatId 为 null 的绑定作为通配符匹配", () => {
      const bindings = [makeBinding({ id: "wildcard", chatId: null })];
      const result = findBindingForMessage(bindings, "dingtalk", "any-chat");
      expect(result).toBeDefined();
      expect(result!.matchType).toBe("wildcard");
      expect(result!.binding.id).toBe("wildcard");
    });

    test("无精确匹配时 fallback 到通配符", () => {
      const bindings = [
        makeBinding({ id: "exact-other", chatId: "other-chat" }),
        makeBinding({ id: "wildcard", chatId: null }),
      ];
      const result = findBindingForMessage(bindings, "dingtalk", "unknown-chat");
      expect(result).toBeDefined();
      expect(result!.matchType).toBe("wildcard");
      expect(result!.binding.id).toBe("wildcard");
    });
  });

  // ── 无匹配 ──

  describe("无匹配", () => {
    test("无绑定返回 undefined", () => {
      const result = findBindingForMessage([], "dingtalk", "chat-123");
      expect(result).toBeUndefined();
    });

    test("chatId 不匹配且无通配符返回 undefined", () => {
      const bindings = [makeBinding({ chatId: "chat-other" })];
      const result = findBindingForMessage(bindings, "dingtalk", "chat-123");
      expect(result).toBeUndefined();
    });
  });

  // ── disabled 过滤 ──

  describe("disabled 绑定被忽略", () => {
    test("精确匹配但 disabled 不匹配", () => {
      const bindings = [makeBinding({ chatId: "chat-123", enabled: false })];
      const result = findBindingForMessage(bindings, "dingtalk", "chat-123");
      expect(result).toBeUndefined();
    });

    test("通配符但 disabled 不匹配", () => {
      const bindings = [makeBinding({ chatId: null, enabled: false })];
      const result = findBindingForMessage(bindings, "dingtalk", "any-chat");
      expect(result).toBeUndefined();
    });

    test("disabled 精确匹配不阻塞 enabled 通配符", () => {
      const bindings = [
        makeBinding({ id: "exact-disabled", chatId: "chat-123", enabled: false }),
        makeBinding({ id: "wildcard-enabled", chatId: null, enabled: true }),
      ];
      const result = findBindingForMessage(bindings, "dingtalk", "chat-123");
      expect(result).toBeDefined();
      expect(result!.matchType).toBe("wildcard");
      expect(result!.binding.id).toBe("wildcard-enabled");
    });
  });

  // ── platform 过滤 ──

  describe("platform 过滤", () => {
    test("不同平台的绑定不匹配", () => {
      const bindings = [makeBinding({ platform: "slack", chatId: "chat-123" })];
      const result = findBindingForMessage(bindings, "dingtalk", "chat-123");
      expect(result).toBeUndefined();
    });

    test("只匹配指定平台的绑定", () => {
      const bindings = [
        makeBinding({ id: "slack-bind", platform: "slack", chatId: "chat-123" }),
        makeBinding({ id: "ding-bind", platform: "dingtalk", chatId: "chat-123" }),
      ];
      const result = findBindingForMessage(bindings, "dingtalk", "chat-123");
      expect(result).toBeDefined();
      expect(result!.binding.id).toBe("ding-bind");
    });

    test("不同平台的通配符不匹配", () => {
      const bindings = [
        makeBinding({ platform: "slack", chatId: null }),
        makeBinding({ platform: "dingtalk", chatId: null, id: "ding-wild" }),
      ];
      const result = findBindingForMessage(bindings, "dingtalk", "any-chat");
      expect(result).toBeDefined();
      expect(result!.binding.id).toBe("ding-wild");
    });
  });

  // ── 边界情况 ──

  describe("边界情况", () => {
    test("多个精确匹配时返回第一个", () => {
      const bindings = [
        makeBinding({ id: "first", chatId: "chat-123" }),
        makeBinding({ id: "second", chatId: "chat-123" }),
      ];
      const result = findBindingForMessage(bindings, "dingtalk", "chat-123");
      expect(result!.binding.id).toBe("first");
    });

    test("多个通配符时返回第一个", () => {
      const bindings = [
        makeBinding({ id: "wild-first", chatId: null }),
        makeBinding({ id: "wild-second", chatId: null }),
      ];
      const result = findBindingForMessage(bindings, "dingtalk", "any-chat");
      expect(result!.binding.id).toBe("wild-first");
    });

    test("enabled 和 platform 同时过滤", () => {
      const bindings = [
        makeBinding({ id: "a", platform: "dingtalk", chatId: "chat-1", enabled: true }),
        makeBinding({ id: "b", platform: "dingtalk", chatId: "chat-1", enabled: false }),
        makeBinding({ id: "c", platform: "slack", chatId: "chat-1", enabled: true }),
      ];
      const result = findBindingForMessage(bindings, "dingtalk", "chat-1");
      expect(result!.binding.id).toBe("a");
    });
  });
});
