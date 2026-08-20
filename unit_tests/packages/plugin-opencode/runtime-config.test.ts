// runtime-config.test.ts — plugin-opencode 运行时配置构建测试
// 测试目标：buildOpencodeRuntimeConfig 的转换正确性
// 业务意图：确保 AgentLaunchSpec 正确映射为 opencode 的 JSON 配置格式

import { describe, test, expect } from "bun:test";

// ── 复制核心转换逻辑（来自 packages/plugin-opencode/src/runtime/runtime-config.ts）──

interface McpServerConfig {
  name: string;
  type: string;
  command?: string;
  args?: string[];
  cwd?: string;
  env?: Record<string, string>;
  url?: string;
  headers?: Record<string, string>;
  timeout?: number;
}

interface AgentLaunchSpec {
  organizationId: string;
  userId: string;
  agent: { name: string; prompt?: string; extra?: Record<string, unknown> | null };
  model: {
    provider: string;
    protocol: "openai" | "anthropic";
    baseUrl: string;
    apiKey: string;
    model: string;
    modelName?: string;
    modalities?: { input?: string[]; output?: string[] } | string[];
  };
  skills: { name: string; url: string }[];
  mcpServers: McpServerConfig[];
}

function toProviderPackage(protocol: string): string {
  switch (protocol) {
    case "anthropic":
      return "@ai-sdk/anthropic";
    default:
      return "@ai-sdk/openai-compatible";
  }
}

function toMcpRecord(mcpServers: McpServerConfig[]): Record<string, unknown> {
  return Object.fromEntries(
    mcpServers.map((server) => {
      if (server.type === "stdio") {
        return [
          server.name,
          {
            type: "local",
            command: [server.command, ...(server.args ?? [])],
            cwd: server.cwd,
            environment: server.env,
            timeout: server.timeout,
          },
        ];
      }
      return [
        server.name,
        {
          type: "remote",
          url: server.url,
          headers: server.headers,
          timeout: server.timeout,
        },
      ];
    }),
  );
}

function buildOpencodeRuntimeConfig(launchSpec: AgentLaunchSpec) {
  const providerId = launchSpec.model.provider;
  const modelId = launchSpec.model.modelName ?? launchSpec.model.model;
  const agentName = launchSpec.agent.name;
  const providerModelRef = `${providerId}/${modelId}`;

  const rawModalities = launchSpec.model.modalities;
  const modelHasImage =
    rawModalities != null &&
    typeof rawModalities === "object" &&
    !Array.isArray(rawModalities) &&
    (rawModalities as { input?: string[] }).input?.includes("image");

  return {
    $schema: "https://opencode.ai/config.json",
    autoupdate: false,
    default_agent: agentName,
    enabled_providers: [providerId],
    provider: {
      [providerId]: {
        npm: toProviderPackage(launchSpec.model.protocol),
        options: { baseURL: launchSpec.model.baseUrl, apiKey: launchSpec.model.apiKey, setCacheKey: true },
        models: {
          [modelId]: {
            name: launchSpec.model.model,
            modalities: modelHasImage
              ? (rawModalities as { input?: string[]; output?: string[] })
              : { input: ["text"], output: ["text"] },
          },
        },
      },
    },
    model: providerModelRef,
    agent: {
      [agentName]: {
        model: providerModelRef,
        mode: "primary",
        steps: (launchSpec.agent.extra?.steps as number) ?? 1000,
        ...(launchSpec.agent.prompt ? { prompt: launchSpec.agent.prompt } : {}),
        hidden: false,
        disable: false,
      },
    },
    mcp: toMcpRecord(launchSpec.mcpServers.filter((s) => s.name !== "hindsight")),
    ...(launchSpec.agent.extra?.plugin && Array.isArray(launchSpec.agent.extra.plugin)
      ? { plugin: launchSpec.agent.extra.plugin }
      : {}),
  };
}

// ── 辅助 ──

function baseSpec(overrides?: Partial<AgentLaunchSpec>): AgentLaunchSpec {
  return {
    organizationId: "org-1",
    userId: "user-1",
    agent: { name: "coder" },
    model: { provider: "openai", protocol: "openai", baseUrl: "http://api", apiKey: "sk", model: "gpt-4" },
    skills: [],
    mcpServers: [],
    ...overrides,
  };
}

// ── 测试 ──

describe("buildOpencodeRuntimeConfig", () => {
  test("正向 - 基本字段正确", () => {
    const config = buildOpencodeRuntimeConfig(baseSpec());
    expect(config.$schema).toBe("https://opencode.ai/config.json");
    expect(config.autoupdate).toBe(false);
    expect(config.default_agent).toBe("coder");
    expect(config.model).toBe("openai/gpt-4");
  });

  test("正向 - openai 协议使用 openai-compatible 包", () => {
    const config = buildOpencodeRuntimeConfig(baseSpec());
    expect(config.provider.openai.npm).toBe("@ai-sdk/openai-compatible");
  });

  test("正向 - anthropic 协议使用 anthropic 包", () => {
    const spec = baseSpec({
      model: { provider: "anthropic", protocol: "anthropic", baseUrl: "http://x", apiKey: "ak", model: "claude-3" },
    });
    const config = buildOpencodeRuntimeConfig(spec);
    expect(config.provider.anthropic.npm).toBe("@ai-sdk/anthropic");
  });

  test("正向 - modelName 优先于 model 作为 modelId", () => {
    const spec = baseSpec({
      model: { provider: "openai", protocol: "openai", baseUrl: "http://x", apiKey: "sk", model: "gpt-4", modelName: "custom" },
    });
    const config = buildOpencodeRuntimeConfig(spec);
    expect(config.model).toBe("openai/custom");
    expect(config.provider.openai.models.custom.name).toBe("gpt-4");
  });

  test("正向 - agent 配置包含 model 和 mode", () => {
    const config = buildOpencodeRuntimeConfig(baseSpec());
    expect(config.agent.coder.model).toBe("openai/gpt-4");
    expect(config.agent.coder.mode).toBe("primary");
    expect(config.agent.coder.steps).toBe(1000);
    expect(config.agent.coder.hidden).toBe(false);
    expect(config.agent.coder.disable).toBe(false);
  });

  test("分支 - agent.extra.steps 覆盖默认值", () => {
    const spec = baseSpec({ agent: { name: "coder", extra: { steps: 500 } } });
    const config = buildOpencodeRuntimeConfig(spec);
    expect(config.agent.coder.steps).toBe(500);
  });

  test("分支 - agent.prompt 存在时包含", () => {
    const spec = baseSpec({ agent: { name: "coder", prompt: "you are helpful" } });
    const config = buildOpencodeRuntimeConfig(spec);
    expect(config.agent.coder.prompt).toBe("you are helpful");
  });

  test("分支 - 无 prompt 时不包含", () => {
    const config = buildOpencodeRuntimeConfig(baseSpec());
    expect("prompt" in config.agent.coder).toBe(false);
  });

  test("正向 - stdio MCP server 转换为 local 类型", () => {
    const spec = baseSpec({
      mcpServers: [{ name: "fs", type: "stdio", command: "node", args: ["index.js"], env: { X: "1" } }],
    });
    const config = buildOpencodeRuntimeConfig(spec);
    expect(config.mcp.fs).toEqual({
      type: "local",
      command: ["node", "index.js"],
      cwd: undefined,
      environment: { X: "1" },
      timeout: undefined,
    });
  });

  test("正向 - remote MCP server 转换为 remote 类型", () => {
    const spec = baseSpec({
      mcpServers: [{ name: "r", type: "streamable-http", url: "http://mcp", headers: { Auth: "b" } }],
    });
    const config = buildOpencodeRuntimeConfig(spec);
    expect(config.mcp.r).toEqual({ type: "remote", url: "http://mcp", headers: { Auth: "b" }, timeout: undefined });
  });

  test("分支 - hindsight MCP server 被过滤", () => {
    const spec = baseSpec({
      mcpServers: [
        { name: "hindsight", type: "stdio", command: "x" },
        { name: "fs", type: "stdio", command: "y" },
      ],
    });
    const config = buildOpencodeRuntimeConfig(spec);
    expect(config.mcp.hindsight).toBeUndefined();
    expect(config.mcp.fs).toBeDefined();
  });

  test("分支 - modalities 对象格式含 image 时保留", () => {
    const spec = baseSpec({
      model: {
        provider: "openai",
        protocol: "openai",
        baseUrl: "http://x",
        apiKey: "sk",
        model: "gpt-4o",
        modalities: { input: ["text", "image"], output: ["text"] },
      },
    });
    const config = buildOpencodeRuntimeConfig(spec);
    expect(config.provider.openai.models["gpt-4o"].modalities).toEqual({
      input: ["text", "image"],
      output: ["text"],
    });
  });

  test("分支 - modalities 数组格式降级为纯文本", () => {
    const spec = baseSpec({
      model: {
        provider: "openai",
        protocol: "openai",
        baseUrl: "http://x",
        apiKey: "sk",
        model: "gpt-4",
        modalities: ["text"],
      },
    });
    const config = buildOpencodeRuntimeConfig(spec);
    expect(config.provider.openai.models["gpt-4"].modalities).toEqual({ input: ["text"], output: ["text"] });
  });

  test("分支 - agent.extra.plugin 数组时包含 plugin 字段", () => {
    const spec = baseSpec({
      agent: { name: "coder", extra: { plugin: [["plugin-a", { opt: 1 }]] } },
    });
    const config = buildOpencodeRuntimeConfig(spec);
    expect(config.plugin).toEqual([["plugin-a", { opt: 1 }]]);
  });

  test("边界 - 无 plugin 时不包含 plugin 字段", () => {
    const config = buildOpencodeRuntimeConfig(baseSpec());
    expect("plugin" in config).toBe(false);
  });
});
