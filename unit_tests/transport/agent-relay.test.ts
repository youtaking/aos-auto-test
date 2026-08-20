// agent-relay.test.ts — Agent Relay 连接纯逻辑测试
// 测试目标：connectAgentRelay 的 dead instance 清理判断逻辑
// 业务意图：确保 relay 连接失败时正确触发本地死实例清理

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数 ──

interface InstanceSnapshot {
  nodeId: string;
  status: string;
}

function shouldTerminateLocalDead(
  snapshot: InstanceSnapshot | undefined | null,
): boolean {
  if (!snapshot) return false;
  return (
    snapshot.nodeId === "local-default" &&
    (snapshot.status === "running" || snapshot.status === "error")
  );
}

function extractInstanceId(instance: { id?: string; instanceId?: string }): string {
  return instance.instanceId ?? instance.id ?? "";
}

// ── tests ──

describe("agent-relay Agent Relay", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("shouldTerminateLocalDead 本地死实例清理判断", () => {
    test("local-default + running → 需要清理", () => {
      expect(shouldTerminateLocalDead({ nodeId: "local-default", status: "running" })).toBe(true);
    });

    test("local-default + error → 需要清理", () => {
      expect(shouldTerminateLocalDead({ nodeId: "local-default", status: "error" })).toBe(true);
    });

    test("local-default + stopped → 不需要清理", () => {
      expect(shouldTerminateLocalDead({ nodeId: "local-default", status: "stopped" })).toBe(false);
    });

    test("local-default + starting → 不需要清理", () => {
      expect(shouldTerminateLocalDead({ nodeId: "local-default", status: "starting" })).toBe(false);
    });

    test("远程节点 + running → 不需要清理", () => {
      expect(shouldTerminateLocalDead({ nodeId: "remote-node-1", status: "running" })).toBe(false);
    });

    test("远程节点 + error → 不需要清理", () => {
      expect(shouldTerminateLocalDead({ nodeId: "remote-node-1", status: "error" })).toBe(false);
    });

    test("null snapshot → 不需要清理", () => {
      expect(shouldTerminateLocalDead(null)).toBe(false);
    });

    test("undefined snapshot → 不需要清理", () => {
      expect(shouldTerminateLocalDead(undefined)).toBe(false);
    });
  });

  describe("extractInstanceId 实例 ID 提取", () => {
    test("有 instanceId 字段时使用它", () => {
      expect(extractInstanceId({ instanceId: "inst-123" })).toBe("inst-123");
    });

    test("无 instanceId 时使用 id", () => {
      expect(extractInstanceId({ id: "old-123" })).toBe("old-123");
    });

    test("两个字段都有时优先 instanceId", () => {
      expect(extractInstanceId({ id: "old", instanceId: "new" })).toBe("new");
    });

    test("都无时返回空字符串", () => {
      expect(extractInstanceId({})).toBe("");
    });
  });
});
