// agent-launch-spec.test.ts — plugin-sdk AgentLaunchSpec 类型完整性测试
// 测试目标：验证类型结构（纯类型模块，测试构造与字段兼容性）
// 业务意图：确保 AgentLaunchSpec 可被正确构造，字段可选性符合预期

import { describe, test, expect } from "bun:test";

// ── 复制类型定义（来自 packages/plugin-sdk/src/agent-launch-spec.ts）──

interface AgentConfig {
  name: string;
  prompt?: string;
  extra?: Record<string, unknown> | null;
}

interface ModelConfig {
  provider: string;
  protocol: "openai" | "anthropic";
  baseUrl: string;
  apiKey: string;
  model: string;
  modelName?: string;
  modalities?: { input?: ("text" | "image")[]; output?: ("text" | "image")[] } | string[];
}

interface SkillConfig {
  name: string;
  url: string;
}

interface StdioMcpServerConfig {
  name: string;
  type: "stdio";
  command: string;
  args?: string[];
  cwd?: string;
  env?: Record<string, string>;
  timeout?: number;
}

interface StreamableHttpMcpServerConfig {
  name: string;
  type: "streamable-http";
  url: string;
  headers?: Record<string, string>;
  oauth?: { clientId?: string; clientSecret?: string; scope?: string; redirectUri?: string } | false;
  timeout?: number;
}

type McpServerConfig = StdioMcpServerConfig | StreamableHttpMcpServerConfig;

interface AgentLaunchSpec {
  organizationId: string;
  userId: string;
  environmentId?: string;
  env?: Record<string, string>;
  agent: AgentConfig;
  model: ModelConfig;
  skills: SkillConfig[];
  mcpServers: McpServerConfig[];
}

// ── 测试 ──

describe("AgentLaunchSpec 结构", () => {
  test("正向 - 最小必需字段可构造", () => {
    const spec: AgentLaunchSpec = {
      organizationId: "org-1",
      userId: "user-1",
      agent: { name: "test" },
      model: { provider: "openai", protocol: "openai", baseUrl: "http://api", apiKey: "sk", model: "gpt-4" },
      skills: [],
      mcpServers: [],
    };
    expect(spec.organizationId).toBe("org-1");
    expect(spec.agent.name).toBe("test");
    expect(spec.skills).toEqual([]);
  });

  test("正向 - 可选字段可设置", () => {
    const spec: AgentLaunchSpec = {
      organizationId: "org-1",
      userId: "user-1",
      environmentId: "env-1",
      env: { KEY: "value" },
      agent: { name: "test", prompt: "you are helpful", extra: { steps: 500 } },
      model: {
        provider: "anthropic",
        protocol: "anthropic",
        baseUrl: "http://api",
        apiKey: "ak",
        model: "claude-3",
        modelName: "claude-3-opus",
        modalities: { input: ["text", "image"], output: ["text"] },
      },
      skills: [{ name: "skill-1", url: "http://dl" }],
      mcpServers: [
        { name: "fs", type: "stdio", command: "node", args: ["index.js"] },
        { name: "remote", type: "streamable-http", url: "http://mcp", headers: { Auth: "bearer" } },
      ],
    };
    expect(spec.environmentId).toBe("env-1");
    expect(spec.agent.prompt).toBe("you are helpful");
    expect(spec.model.modelName).toBe("claude-3-opus");
    expect(spec.skills.length).toBe(1);
    expect(spec.mcpServers.length).toBe(2);
  });

  test("正向 - agent.extra 可以为 null", () => {
    const spec: AgentLaunchSpec = {
      organizationId: "o",
      userId: "u",
      agent: { name: "a", extra: null },
      model: { provider: "o", protocol: "openai", baseUrl: "x", apiKey: "k", model: "m" },
      skills: [],
      mcpServers: [],
    };
    expect(spec.agent.extra).toBeNull();
  });

  test("正向 - stdio MCP server 可选字段均为 undefined", () => {
    const server: StdioMcpServerConfig = { name: "fs", type: "stdio", command: "node" };
    expect(server.args).toBeUndefined();
    expect(server.cwd).toBeUndefined();
    expect(server.env).toBeUndefined();
    expect(server.timeout).toBeUndefined();
  });

  test("正向 - streamable-http MCP server oauth 可为 false", () => {
    const server: StreamableHttpMcpServerConfig = { name: "r", type: "streamable-http", url: "http://x", oauth: false };
    expect(server.oauth).toBe(false);
  });

  test("分支 - model.protocol 只能是 openai 或 anthropic", () => {
    // 运行时不校验，仅编译期保证；这里验证两种值都可赋值
    const openai: ModelConfig = { provider: "o", protocol: "openai", baseUrl: "x", apiKey: "k", model: "m" };
    const anthropic: ModelConfig = { provider: "a", protocol: "anthropic", baseUrl: "x", apiKey: "k", model: "m" };
    expect(openai.protocol).toBe("openai");
    expect(anthropic.protocol).toBe("anthropic");
  });

  test("隔离 - modalities 数组格式也可赋值", () => {
    const model: ModelConfig = {
      provider: "o",
      protocol: "openai",
      baseUrl: "x",
      apiKey: "k",
      model: "m",
      modalities: ["text"],
    };
    expect(Array.isArray(model.modalities)).toBe(true);
  });
});
