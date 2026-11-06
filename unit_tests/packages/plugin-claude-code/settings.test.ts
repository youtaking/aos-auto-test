// settings.test.ts — plugin-claude-code 配置构建测试
// 测试目标：buildMcpConfig / buildSettings 的转换正确性
// 业务意图：确保 AgentLaunchSpec 正确映射为 Claude Code 的 .mcp.json 和 settings.local.json 格式

import { describe, test, expect } from "bun:test";

// ── 复制纯函数（来自 packages/plugin-claude-code/src/runtime/settings.ts）──

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
  timeout?: number;
}

type McpServerConfig = StdioMcpServerConfig | StreamableHttpMcpServerConfig;

interface AgentLaunchSpec {
  organizationId: string;
  userId: string;
  env?: Record<string, string>;
  plugins?: "hindsight"[];
  agent: { name: string; prompt?: string; extra?: Record<string, unknown> | null };
  model: {
    provider: string;
    protocol: "openai" | "anthropic";
    baseUrl: string;
    apiKey: string;
    model: string;
    modelName?: string;
  };
  skills: { name: string; url: string }[];
  mcpServers: McpServerConfig[];
}

interface ClaudeCodeMcpStdioConfig {
  command: string;
  args?: string[];
  env?: Record<string, string>;
  cwd?: string;
}

interface ClaudeCodeMcpRemoteConfig {
  url: string;
  headers?: Record<string, string>;
}

type ClaudeCodeMcpServerConfig = ClaudeCodeMcpStdioConfig | ClaudeCodeMcpRemoteConfig;

interface ClaudeCodeSettings {
  env?: Record<string, string>;
  model?: string;
  modelType?: string;
  enabledPlugins?: Record<string, boolean>;
  permissions?: { allow?: string[]; deny?: string[]; defaultMode?: string };
}

function isStreamableHttp(server: McpServerConfig): server is Extract<McpServerConfig, { type: "streamable-http" }> {
  return server.type === "streamable-http";
}

function buildMcpConfig(launchSpec: AgentLaunchSpec): { mcpServers: Record<string, ClaudeCodeMcpServerConfig> } {
  const mcpServers: Record<string, ClaudeCodeMcpServerConfig> = {};
  for (const server of launchSpec.mcpServers) {
    if (isStreamableHttp(server)) {
      mcpServers[server.name] = {
        url: server.url,
        ...(server.headers ? { headers: server.headers } : {}),
      };
    } else {
      mcpServers[server.name] = {
        command: server.command,
        ...(server.args ? { args: server.args } : {}),
        ...(server.env ? { env: server.env } : {}),
        ...(server.cwd ? { cwd: server.cwd } : {}),
      };
    }
  }

  return { mcpServers };
}

function buildSettings(launchSpec: AgentLaunchSpec, _installedSkills: { name: string; path: string }[]): ClaudeCodeSettings {
  const config: ClaudeCodeSettings = {};
  const env: Record<string, string> = {};
  const { model } = launchSpec;

  if (model.apiKey) {
    if (model.protocol === "anthropic") {
      env.ANTHROPIC_AUTH_TOKEN = model.apiKey;
      if (model.baseUrl) env.ANTHROPIC_BASE_URL = model.baseUrl;
    } else {
      env.OPENAI_API_KEY = model.apiKey;
      if (model.baseUrl) env.OPENAI_BASE_URL = model.baseUrl;
    }
  }

  if (model.modelName) {
    env.ANTHROPIC_MODEL = model.modelName;
  }

  if (launchSpec.env) {
    Object.assign(env, launchSpec.env);
  }

  if (Object.keys(env).length > 0) {
    config.env = env;
  }

  if (model.modelName) {
    config.model = model.modelName;
  }

  // 沿用 ccb/peri 镜像预装的市场别名；本地 Claude Code 也需安装同名市场插件。
  if (launchSpec.plugins?.includes("hindsight")) {
    config.enabledPlugins = { "hindsight-memory@hindsight-plugin": true };
  }

  return config;
}

// ── 辅助 ──

function baseSpec(overrides?: Partial<AgentLaunchSpec>): AgentLaunchSpec {
  return {
    organizationId: "org-1",
    userId: "user-1",
    agent: { name: "agent-1" },
    model: { provider: "openai", protocol: "openai", baseUrl: "http://api", apiKey: "sk-123", model: "gpt-4" },
    skills: [],
    mcpServers: [],
    ...overrides,
  };
}

// ── 测试 ──

describe("buildMcpConfig", () => {
  // 空集合必须投影为空对象，不能返回 null：null 会让调用方跳过写文件，
  // 取消全部 MCP 后 agent 仍按旧清单加载工具。
  test("边界 - 空 mcpServers 返回空对象而不是 null", () => {
    expect(buildMcpConfig(baseSpec())).toEqual({ mcpServers: {} });
  });

  test("正向 - stdio 类型包含 command/args/env/cwd", () => {
    const spec = baseSpec({
      mcpServers: [{ name: "fs", type: "stdio", command: "node", args: ["index.js"], env: { X: "1" }, cwd: "/tmp" }],
    });
    const result = buildMcpConfig(spec);
    expect(result!.mcpServers.fs).toEqual({ command: "node", args: ["index.js"], env: { X: "1" }, cwd: "/tmp" });
  });

  test("正向 - streamable-http 类型包含 url/headers", () => {
    const spec = baseSpec({
      mcpServers: [{ name: "remote", type: "streamable-http", url: "http://mcp.example.com", headers: { Auth: "bearer" } }],
    });
    const result = buildMcpConfig(spec);
    expect(result!.mcpServers.remote).toEqual({ url: "http://mcp.example.com", headers: { Auth: "bearer" } });
  });

  test("分支 - stdio 无可选字段时只包含 command", () => {
    const spec = baseSpec({ mcpServers: [{ name: "simple", type: "stdio", command: "echo" }] });
    const result = buildMcpConfig(spec);
    expect(result!.mcpServers.simple).toEqual({ command: "echo" });
  });

  test("分支 - streamable-http 无 headers 时只包含 url", () => {
    const spec = baseSpec({ mcpServers: [{ name: "r", type: "streamable-http", url: "http://x" }] });
    const result = buildMcpConfig(spec);
    expect(result!.mcpServers.r).toEqual({ url: "http://x" });
  });

  test("正向 - 多个 server 全部转换", () => {
    const spec = baseSpec({
      mcpServers: [
        { name: "a", type: "stdio", command: "a" },
        { name: "b", type: "streamable-http", url: "http://b" },
      ],
    });
    const result = buildMcpConfig(spec);
    expect(Object.keys(result!.mcpServers)).toEqual(["a", "b"]);
  });
});

describe("buildSettings", () => {
  test("正向 - openai 协议设置 OPENAI_API_KEY 和 OPENAI_BASE_URL", () => {
    const settings = buildSettings(baseSpec(), []);
    expect(settings.env!.OPENAI_API_KEY).toBe("sk-123");
    expect(settings.env!.OPENAI_BASE_URL).toBe("http://api");
  });

  test("正向 - anthropic 协议设置 ANTHROPIC_AUTH_TOKEN 和 ANTHROPIC_BASE_URL", () => {
    const spec = baseSpec({
      model: { provider: "anthropic", protocol: "anthropic", baseUrl: "http://anthropic", apiKey: "ak", model: "claude-3" },
    });
    const settings = buildSettings(spec, []);
    expect(settings.env!.ANTHROPIC_AUTH_TOKEN).toBe("ak");
    expect(settings.env!.ANTHROPIC_BASE_URL).toBe("http://anthropic");
  });

  test("正向 - modelName 设置 ANTHROPIC_MODEL 和 config.model", () => {
    const spec = baseSpec({
      model: { provider: "openai", protocol: "openai", baseUrl: "http://api", apiKey: "sk", model: "gpt-4", modelName: "custom-model" },
    });
    const settings = buildSettings(spec, []);
    expect(settings.env!.ANTHROPIC_MODEL).toBe("custom-model");
    expect(settings.model).toBe("custom-model");
  });

  test("分支 - 无 modelName 时不设置 ANTHROPIC_MODEL 和 model 字段", () => {
    const settings = buildSettings(baseSpec(), []);
    expect(settings.env!.ANTHROPIC_MODEL).toBeUndefined();
    expect(settings.model).toBeUndefined();
  });

  test("正向 - launchSpec.env 合并到 settings.env", () => {
    const spec = baseSpec({ env: { CUSTOM: "value" } });
    const settings = buildSettings(spec, []);
    expect(settings.env!.CUSTOM).toBe("value");
  });

  test("边界 - 无 apiKey 时 env 可能为空对象", () => {
    const spec = baseSpec({ model: { provider: "openai", protocol: "openai", baseUrl: "", apiKey: "", model: "gpt-4" } });
    const settings = buildSettings(spec, []);
    expect(settings.env).toBeUndefined();
  });

  // hindsight 插件由平台预装，必须写进 enabledPlugins，否则本地 Claude Code 不会加载记忆插件。
  test("正向 - plugins 含 hindsight 时写入 enabledPlugins", () => {
    const settings = buildSettings(baseSpec({ plugins: ["hindsight"] }), []);
    expect(settings.enabledPlugins).toEqual({ "hindsight-memory@hindsight-plugin": true });
  });

  test("分支 - 未声明 plugins 时不写 enabledPlugins", () => {
    const settings = buildSettings(baseSpec(), []);
    expect(settings.enabledPlugins).toBeUndefined();
  });
});
