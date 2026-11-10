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

/**
 * 复制 packages/agent-runtime/src/services/orchestration-instance.ts 的启动环境合并语义：
 * 调用方覆盖其余变量，但运行环境身份（AGENT_CONFIG_ID / ENVIRONMENT_ID）始终取服务端记录。
 */
function mergeLaunchEnv(input: {
  platformEnv: Record<string, string>;
  extraEnv: Record<string, string>;
  agentConfigId?: string;
  environmentId: string;
}): Record<string, string> {
  return {
    ...input.platformEnv,
    ...input.extraEnv,
    AGENT_CONFIG_ID: input.agentConfigId ?? "",
    ENVIRONMENT_ID: input.environmentId,
  };
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

  describe("mergeLaunchEnv 启动环境合并", () => {
    const platformEnv = {
      USER_META_API_KEY: "platform-key",
      USER_META_USER_ID: "platform-user",
      USER_META_ORG_ID: "platform-org",
      AGENT_CONFIG_ID: "platform-agent",
      ENVIRONMENT_ID: "platform-env",
    };

    test("调用方请求者上下文覆盖共享 meta env", () => {
      const merged = mergeLaunchEnv({
        platformEnv,
        extraEnv: {
          USER_META_API_KEY: "caller-key",
          USER_META_USER_ID: "caller-user",
          USER_META_ORG_ID: "caller-org",
        },
        agentConfigId: "server-agent",
        environmentId: "server-env",
      });
      expect(merged.USER_META_API_KEY).toBe("caller-key");
      expect(merged.USER_META_USER_ID).toBe("caller-user");
      expect(merged.USER_META_ORG_ID).toBe("caller-org");
    });

    test("调用方无法改写 AGENT_CONFIG_ID，始终取服务端记录", () => {
      const merged = mergeLaunchEnv({
        platformEnv,
        extraEnv: { AGENT_CONFIG_ID: "caller-agent" },
        agentConfigId: "server-agent",
        environmentId: "server-env",
      });
      expect(merged.AGENT_CONFIG_ID).toBe("server-agent");
    });

    test("调用方无法改写 ENVIRONMENT_ID，始终取服务端记录", () => {
      const merged = mergeLaunchEnv({
        platformEnv,
        extraEnv: { ENVIRONMENT_ID: "caller-env" },
        agentConfigId: "server-agent",
        environmentId: "server-env",
      });
      expect(merged.ENVIRONMENT_ID).toBe("server-env");
    });

    test("服务端 agentConfigId 缺失时身份为空字符串而不是调用方值", () => {
      const merged = mergeLaunchEnv({
        platformEnv,
        extraEnv: { AGENT_CONFIG_ID: "caller-agent" },
        environmentId: "server-env",
      });
      expect(merged.AGENT_CONFIG_ID).toBe("");
    });

    test("未覆盖的平台变量原样保留", () => {
      const merged = mergeLaunchEnv({
        platformEnv: { UNTOUCHED: "keep", ENVIRONMENT_ID: "platform-env" },
        extraEnv: {},
        agentConfigId: "server-agent",
        environmentId: "server-env",
      });
      expect(merged.UNTOUCHED).toBe("keep");
    });

    test("完整合并结果只包含期望键值", () => {
      const merged = mergeLaunchEnv({
        platformEnv: { A: "1" },
        extraEnv: { B: "2", ENVIRONMENT_ID: "caller" },
        agentConfigId: "agent",
        environmentId: "env",
      });
      expect(merged).toEqual({
        A: "1",
        B: "2",
        AGENT_CONFIG_ID: "agent",
        ENVIRONMENT_ID: "env",
      });
    });
  });
});
