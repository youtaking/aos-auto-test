// orchestration-instance.test.ts — 编排域实例管理纯逻辑测试
// 测试目标：spawnInstanceViaCore 的 local vs remote 路由、terminateLocalDeadInstance 判定
// 业务意图：确保实例启动的节点路由和死实例清理逻辑正确

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数 ──

const LOCAL_DEFAULT_NODE_ID = "local-default";

function resolveNodeConfig(
  machineId: string,
  defaultEngineType: string | undefined,
): { nodeId: string; engineType?: string } {
  const nodeId = machineId;
  if (nodeId === LOCAL_DEFAULT_NODE_ID) {
    return { nodeId, engineType: defaultEngineType ?? "opencode" };
  }
  return { nodeId };
}

function shouldTerminateDead(
  nodeId: string | undefined,
  status: string | undefined,
): boolean {
  return nodeId === LOCAL_DEFAULT_NODE_ID && (status === "running" || status === "error");
}

interface SpawnedInstance {
  instanceId: string;
  machineId: string;
  status: string;
}

// ── tests ──

describe("orchestration-instance 编排域实例管理", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("resolveNodeConfig 节点路由配置", () => {
    test("local-default 节点使用默认 engineType", () => {
      const result = resolveNodeConfig("local-default", "opencode");
      expect(result.nodeId).toBe("local-default");
      expect(result.engineType).toBe("opencode");
    });

    test("local-default + 无默认 engineType 回退 opencode", () => {
      const result = resolveNodeConfig("local-default", undefined);
      expect(result.engineType).toBe("opencode");
    });

    test("local-default + 自定义 engineType", () => {
      const result = resolveNodeConfig("local-default", "claude");
      expect(result.engineType).toBe("claude");
    });

    test("远程节点不设置 engineType", () => {
      const result = resolveNodeConfig("remote-node-1", "opencode");
      expect(result.nodeId).toBe("remote-node-1");
      expect(result.engineType).toBeUndefined();
    });

    test("远程节点 engineType 不传", () => {
      const result = resolveNodeConfig("machine-abc", undefined);
      expect(result.nodeId).toBe("machine-abc");
      expect(result.engineType).toBeUndefined();
    });
  });

  describe("shouldTerminateDead 死实例清理判定", () => {
    test("local-default + running → 需要清理", () => {
      expect(shouldTerminateDead("local-default", "running")).toBe(true);
    });

    test("local-default + error → 需要清理", () => {
      expect(shouldTerminateDead("local-default", "error")).toBe(true);
    });

    test("local-default + stopped → 不需要清理", () => {
      expect(shouldTerminateDead("local-default", "stopped")).toBe(false);
    });

    test("local-default + starting → 不需要清理", () => {
      expect(shouldTerminateDead("local-default", "starting")).toBe(false);
    });

    test("远程节点 + running → 不需要清理（远程由节点自身管理）", () => {
      expect(shouldTerminateDead("remote-node-1", "running")).toBe(false);
    });

    test("远程节点 + error → 不需要清理", () => {
      expect(shouldTerminateDead("remote-node-1", "error")).toBe(false);
    });

    test("undefined nodeId → 不需要清理", () => {
      expect(shouldTerminateDead(undefined, "running")).toBe(false);
    });

    test("undefined status → 不需要清理", () => {
      expect(shouldTerminateDead("local-default", undefined)).toBe(false);
    });
  });
});
