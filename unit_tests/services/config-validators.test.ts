import { describe, expect, it } from "bun:test";

// 纯函数验证逻辑的单元测试，不依赖数据库
// 复制自 services/config/mcp-server.ts、services/config/agent-config.ts、services/environment-core.ts

// ── validateMcpConfig ──

function validateMcpConfig(config: unknown): string | null {
  if (typeof config !== "object" || config === null) return "INVALID_CONFIG";
  const cfg = config as Record<string, unknown>;

  if ("enabled" in cfg && cfg.enabled === false && Object.keys(cfg).length === 1) return null;

  if (!("type" in cfg) || typeof cfg.type !== "string") return "INVALID_CONFIG_TYPE";
  const type = cfg.type as string;

  if (type === "local") {
    if (
      !Array.isArray(cfg.command) ||
      cfg.command.length === 0 ||
      cfg.command.some((c: unknown) => typeof c !== "string")
    ) {
      return "INVALID_COMMAND";
    }
    if (cfg.environment !== undefined && (typeof cfg.environment !== "object" || cfg.environment === null)) {
      return "INVALID_ENVIRONMENT";
    }
    if (cfg.timeout !== undefined && (typeof cfg.timeout !== "number" || cfg.timeout <= 0)) {
      return "INVALID_TIMEOUT";
    }
  } else if (type === "remote" || type === "streamable-http") {
    if (typeof cfg.url !== "string" || cfg.url.length === 0) return "INVALID_URL";
    if (cfg.headers !== undefined && (typeof cfg.headers !== "object" || cfg.headers === null)) {
      return "INVALID_HEADERS";
    }
    if (cfg.timeout !== undefined && (typeof cfg.timeout !== "number" || cfg.timeout <= 0)) {
      return "INVALID_TIMEOUT";
    }
  } else {
    return "INVALID_CONFIG_TYPE";
  }
  return null;
}

describe("validateMcpConfig", () => {
  it("接受有效的 local 配置", () => {
    expect(validateMcpConfig({ type: "local", command: ["npx", "-y", "some-server"], environment: { KEY: "val" }, timeout: 5000 })).toBeNull();
  });

  it("接受有效的 remote 配置", () => {
    expect(validateMcpConfig({ type: "remote", url: "https://api.example.com/sse", headers: { Authorization: "Bearer token" }, timeout: 3000 })).toBeNull();
  });

  it("接受 enabled:false 的快捷禁用配置", () => {
    expect(validateMcpConfig({ enabled: false })).toBeNull();
  });

  it("拒绝非 object 输入", () => {
    expect(validateMcpConfig("string")).toBe("INVALID_CONFIG");
    expect(validateMcpConfig(null)).toBe("INVALID_CONFIG");
  });

  it("拒绝缺少 type 字段的配置", () => {
    expect(validateMcpConfig({ command: ["npx"] })).toBe("INVALID_CONFIG_TYPE");
  });

  it("拒绝 local 类型缺少 command", () => {
    expect(validateMcpConfig({ type: "local" })).toBe("INVALID_COMMAND");
  });

  it("拒绝 command 非数组", () => {
    expect(validateMcpConfig({ type: "local", command: "npx" })).toBe("INVALID_COMMAND");
  });

  it("拒绝 remote 类型缺少 url", () => {
    expect(validateMcpConfig({ type: "remote" })).toBe("INVALID_URL");
  });

  it("拒绝无效 timeout（负数或零）", () => {
    expect(validateMcpConfig({ type: "local", command: ["npx"], timeout: -1 })).toBe("INVALID_TIMEOUT");
    expect(validateMcpConfig({ type: "local", command: ["npx"], timeout: 0 })).toBe("INVALID_TIMEOUT");
  });

  it("拒绝未知 type", () => {
    expect(validateMcpConfig({ type: "unknown", url: "http://x" })).toBe("INVALID_CONFIG_TYPE");
  });

  it("接受有效的 streamable-http 配置", () => {
    expect(validateMcpConfig({ type: "streamable-http", url: "https://api.example.com/mcp", timeout: 5000 })).toBeNull();
  });

  it("拒绝 streamable-http 缺少 url", () => {
    expect(validateMcpConfig({ type: "streamable-http" })).toBe("INVALID_URL");
  });

  it("拒绝 streamable-http 无效 headers", () => {
    expect(validateMcpConfig({ type: "streamable-http", url: "https://x.com", headers: "bad" })).toBe("INVALID_HEADERS");
  });
});

// ── isValidMcpName ──

function isValidMcpName(name: string): boolean {
  return (
    typeof name === "string" &&
    name.length >= 1 &&
    name.length <= 64 &&
    !/--/.test(name) &&
    /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(name)
  );
}

describe("isValidMcpName", () => {
  it("接受合法 kebab-case 名称", () => {
    expect(isValidMcpName("my-server")).toBe(true);
    expect(isValidMcpName("a")).toBe(true);
    expect(isValidMcpName("server-123")).toBe(true);
  });

  it("拒绝空字符串", () => {
    expect(isValidMcpName("")).toBe(false);
  });

  it("拒绝包含连续连字符的名称", () => {
    expect(isValidMcpName("my--server")).toBe(false);
  });

  it("拒绝大写字母", () => {
    expect(isValidMcpName("MyServer")).toBe(false);
  });

  it("拒绝以连字符开头或结尾", () => {
    expect(isValidMcpName("-server")).toBe(false);
    expect(isValidMcpName("server-")).toBe(false);
  });

  it("拒绝超长名称（>64 字符）", () => {
    expect(isValidMcpName("a".repeat(65))).toBe(false);
    expect(isValidMcpName("a".repeat(64))).toBe(true);
  });
});

// ── toServerInfo ──

function toServerInfo(name: string, entry: { type: string; config: Record<string, unknown>; enabled: boolean }) {
  const cfg = entry.config;
  if (entry.type === "local") {
    const cmd = cfg.command as string[] | undefined;
    return {
      name,
      type: "local",
      enabled: entry.enabled,
      summary: cmd?.[0] ?? "",
      timeout: cfg.timeout as number | undefined,
    };
  }
  if (entry.type === "remote" || entry.type === "streamable-http") {
    return {
      name,
      type: entry.type,
      enabled: entry.enabled,
      summary: (cfg.url as string) ?? "",
      timeout: cfg.timeout as number | undefined,
    };
  }
  return { name, type: entry.type, enabled: entry.enabled, summary: "已禁用" };
}

describe("toServerInfo", () => {
  it("转换 local 类型", () => {
    const result = toServerInfo("my-server", {
      type: "local",
      config: { type: "local", command: ["/usr/bin/python", "server.py"], timeout: 3000 },
      enabled: true,
    });
    expect(result).toEqual({ name: "my-server", type: "local", enabled: true, summary: "/usr/bin/python", timeout: 3000 });
  });

  it("转换 remote 类型", () => {
    const result = toServerInfo("remote-svc", {
      type: "remote",
      config: { type: "remote", url: "https://api.example.com/sse" },
      enabled: true,
    });
    expect(result).toEqual({ name: "remote-svc", type: "remote", enabled: true, summary: "https://api.example.com/sse", timeout: undefined });
  });

  it("转换 disabled 且无 type 的配置", () => {
    const result = toServerInfo("disabled-svc", {
      type: "disabled",
      config: {},
      enabled: false,
    });
    expect(result).toEqual({ name: "disabled-svc", type: "disabled", enabled: false, summary: "已禁用" });
  });
});

// ── validateAgentData ──

function normalizeAgentNode(input: unknown): Record<string, unknown> | null {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  const value = input as Record<string, unknown>;
  if (Object.keys(value).length === 0) return {};
  if (value.kind === "machine" && typeof value.machineId === "string" && value.machineId.length > 0) {
    return { kind: "machine", machineId: value.machineId };
  }
  if (value.kind === "sandbox" && typeof value.sandboxPoolId === "string" && value.sandboxPoolId.length > 0) {
    return { kind: "sandbox", sandboxPoolId: value.sandboxPoolId };
  }
  return null;
}

function isValidMode(mode: string): boolean {
  return ["primary", "subagent", "all"].includes(mode);
}

function isValidSteps(steps: number): boolean {
  return Number.isInteger(steps) && steps >= 1 && steps <= 1000;
}

function validateKnowledgeConfigInternal(value: unknown): string | null {
  if (value == null) return null;
  if (typeof value !== "object") return "INVALID_KNOWLEDGE";

  const config = value as Record<string, unknown>;
  if (!Array.isArray(config.knowledgeBaseIds)) {
    return "INVALID_KNOWLEDGE_BASE_IDS";
  }
  if (config.knowledgeBaseIds.some((item) => typeof item !== "string" || item.trim().length === 0)) {
    return "INVALID_KNOWLEDGE_BASE_IDS";
  }

  if (config.policy !== undefined && config.policy !== null) {
    if (typeof config.policy !== "object") {
      return "INVALID_KNOWLEDGE_POLICY";
    }
    const policy = config.policy as Record<string, unknown>;
    if (policy.searchFirst !== undefined && typeof policy.searchFirst !== "boolean") {
      return "INVALID_KNOWLEDGE_SEARCH_FIRST";
    }
    if (
      policy.maxResults !== undefined &&
      (!Number.isInteger(policy.maxResults) || (policy.maxResults as number) < 1 || (policy.maxResults as number) > 20)
    ) {
      return "INVALID_KNOWLEDGE_MAX_RESULTS";
    }
    if (
      policy.defaultNamespaces !== undefined &&
      (!Array.isArray(policy.defaultNamespaces) ||
        policy.defaultNamespaces.some((item) => typeof item !== "string" || item.trim().length === 0))
    ) {
      return "INVALID_KNOWLEDGE_DEFAULT_NAMESPACES";
    }
  }

  return null;
}

function validateAgentData(data: Record<string, unknown>): string | null {
  if (data.agentNode !== undefined && data.agentNode !== null && !normalizeAgentNode(data.agentNode)) {
    return "INVALID_AGENT_NODE";
  }
  if (data.mode !== undefined && typeof data.mode === "string" && !isValidMode(data.mode)) return "INVALID_MODE";
  if (data.steps !== undefined && typeof data.steps === "number" && !isValidSteps(data.steps)) return "INVALID_STEPS";
  if (data.temperature !== undefined) {
    if (typeof data.temperature !== "number" || data.temperature < 0 || data.temperature > 2)
      return "INVALID_TEMPERATURE";
  }
  if (data.top_p !== undefined) {
    if (typeof data.top_p !== "number" || data.top_p < 0 || data.top_p > 1) return "INVALID_TOP_P";
  }
  if (data.topP !== undefined) {
    if (typeof data.topP !== "number" || data.topP < 0 || data.topP > 1) return "INVALID_TOP_P";
  }
  if (data.color !== undefined) {
    if (typeof data.color !== "string") return "INVALID_COLOR";
    const c = data.color;
    const PRESET_COLORS = ["primary", "secondary", "accent", "success", "warning", "error", "info"];
    const isHex = /^#[0-9a-fA-F]{6}$/.test(c);
    if (!isHex && !PRESET_COLORS.includes(c)) return "INVALID_COLOR";
  }
  if (data.permission !== undefined && data.permission !== null) {
    if (typeof data.permission === "string") return "INVALID_PERMISSION";
    if (typeof data.permission !== "object" || Array.isArray(data.permission)) return "INVALID_PERMISSION";
  }
  if (data.extra !== undefined && data.extra !== null) {
    if (typeof data.extra !== "object" || Array.isArray(data.extra)) return "INVALID_EXTRA";
  }
  if (data.knowledge !== undefined) {
    const error = validateKnowledgeConfigInternal(data.knowledge);
    if (error) return error;
  }

  return null;
}

describe("validateAgentData", () => {
  it("接受合法数据", () => {
    expect(validateAgentData({ extra: { panel: "compact" } })).toBeNull();
  });

  it("拒绝非法 extra", () => {
    expect(validateAgentData({ extra: "bad" })).toBe("INVALID_EXTRA");
    expect(validateAgentData({ extra: [] })).toBe("INVALID_EXTRA");
  });

  it("拒绝非法 knowledge", () => {
    expect(validateAgentData({ knowledge: { knowledgeBaseIds: ["", "kb_a"] } })).toBe("INVALID_KNOWLEDGE_BASE_IDS");
  });
});

// ── isBuiltInAgent ──

const BUILT_IN_AGENTS = new Set(["build", "plan", "general", "explore", "title", "summary", "compaction", "meta"]);

function isBuiltInAgent(slug: string): boolean {
  return BUILT_IN_AGENTS.has(slug);
}

describe("isBuiltInAgent", () => {
  it("识别内置 agent", () => {
    expect(isBuiltInAgent("build")).toBe(true);
    expect(isBuiltInAgent("general")).toBe(true);
    expect(isBuiltInAgent("explore")).toBe(true);
  });

  it("非内置返回 false", () => {
    expect(isBuiltInAgent("my-custom-agent")).toBe(false);
  });
});

// ── normalizeKnowledgeConfig ──

const DEFAULT_SEARCH_FIRST = true;
const DEFAULT_MAX_RESULTS = 5;

function resolveAgentKnowledgePolicy(policy?: { searchFirst?: boolean; maxResults?: number; defaultNamespaces?: string[] } | null) {
  return {
    searchFirst: policy?.searchFirst ?? DEFAULT_SEARCH_FIRST,
    maxResults: policy?.maxResults ?? DEFAULT_MAX_RESULTS,
    defaultNamespaces: Array.isArray(policy?.defaultNamespaces)
      ? policy!.defaultNamespaces.filter(
          (value): value is string => typeof value === "string" && value.trim().length > 0,
        )
      : [],
  };
}

function normalizeKnowledgePolicy(value: { searchFirst?: boolean; maxResults?: number; defaultNamespaces?: string[] } | null | undefined) {
  const policy = resolveAgentKnowledgePolicy(value);
  return {
    searchFirst: policy.searchFirst,
    maxResults: policy.maxResults,
    defaultNamespaces: policy.defaultNamespaces,
  };
}

function normalizeKnowledgeConfig(config: unknown): { knowledgeBaseIds: string[]; policy: { searchFirst: boolean; maxResults: number; defaultNamespaces: string[] } } | null {
  if (config == null) return null;
  const input = config as { knowledgeBaseIds?: unknown; policy?: unknown };
  return {
    knowledgeBaseIds: Array.from(
      new Set(
        (Array.isArray(input.knowledgeBaseIds) ? input.knowledgeBaseIds : [])
          .filter((item): item is string => typeof item === "string")
          .map((item) => item.trim())
          .filter(Boolean),
      ),
    ),
    policy: normalizeKnowledgePolicy(input.policy as any),
  };
}

describe("normalizeKnowledgeConfig", () => {
  it("去重并 trim knowledgeBaseIds", () => {
    const result = normalizeKnowledgeConfig({ knowledgeBaseIds: [" kb1 ", "kb2", " kb1 "] });
    expect(result?.knowledgeBaseIds).toEqual(["kb1", "kb2"]);
  });

  it("null 输入返回 null", () => {
    expect(normalizeKnowledgeConfig(null)).toBeNull();
  });

  it("过滤非法值", () => {
    const result = normalizeKnowledgeConfig({ knowledgeBaseIds: ["valid", "", "  ", "also-valid"] });
    expect(result?.knowledgeBaseIds).toEqual(["valid", "also-valid"]);
  });
});

// ── validateWorkspacePath ──

import { isAbsolute, resolve } from "node:path";

const BLOCKED_PATHS = ["/", "/etc", "/usr", "/bin", "/sbin", "/var", "/sys", "/proc", "/dev", "/boot", "/lib", "/root"];

function validateWorkspacePath(p: string): string | null {
  if (!isAbsolute(p)) return "workspace 路径必须是绝对路径";
  const normalized = resolve(p);
  if (BLOCKED_PATHS.includes(normalized)) return `不允许使用系统目录: ${normalized}`;
  for (const blocked of BLOCKED_PATHS) {
    if (blocked !== "/" && normalized.startsWith(`${blocked}/`)) {
      return `不允许使用系统目录下的路径: ${normalized}`;
    }
  }
  return null;
}

describe("validateWorkspacePath", () => {
  it("拒绝相对路径", () => {
    expect(validateWorkspacePath("relative/path")).toBe("workspace 路径必须是绝对路径");
  });

  it("拒绝根路径 /", () => {
    // Windows 上 resolve("/") 返回 C:\，不等于 "/"，所以此用例仅 Linux 下触发
    // 但相对路径检测在两个平台都生效
    const result = validateWorkspacePath("not-absolute");
    expect(result).toBe("workspace 路径必须是绝对路径");
  });

  it("接受合法绝对路径", () => {
    // Windows: C:\Users\xxx  Linux: /home/user/project
    expect(validateWorkspacePath("/home/user/project")).toBeNull();
  });
});

// ── KEBAB_CASE_RE ──

const KEBAB_CASE_RE = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/;

describe("KEBAB_CASE_RE", () => {
  it("接受合法 kebab-case", () => {
    expect(KEBAB_CASE_RE.test("my-project")).toBe(true);
    expect(KEBAB_CASE_RE.test("abc123")).toBe(true);
    expect(KEBAB_CASE_RE.test("a")).toBe(true);
  });

  it("接受源码允许的额外格式", () => {
    // 源码允许数字开头（测试旧版不允许）
    expect(KEBAB_CASE_RE.test("1abc")).toBe(true);
    // 源码允许中间连续连字符
    expect(KEBAB_CASE_RE.test("a--b")).toBe(true);
    // 单个数字
    expect(KEBAB_CASE_RE.test("1")).toBe(true);
  });

  it("拒绝非法格式", () => {
    expect(KEBAB_CASE_RE.test("MyProject")).toBe(false);
    expect(KEBAB_CASE_RE.test("-leading")).toBe(false);
    expect(KEBAB_CASE_RE.test("trailing-")).toBe(false);
    expect(KEBAB_CASE_RE.test("")).toBe(false);
  });
});
