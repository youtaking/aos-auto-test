import { describe, expect, test } from "bun:test";

// 测试 agent-config.ts 的 AGENT_SETTABLE_FIELDS 和 validateAgentData 边界
// 纯函数复制（原模块有 DB 依赖）

const AGENT_SETTABLE_FIELDS = [
  "model",
  "modelId",
  "prompt",
  "description",
  "extra",
  "agentNode",
  "knowledge",
] as const;

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

const BUILT_IN_AGENTS = new Set(["build", "plan", "general", "explore", "title", "summary", "compaction", "meta"]);
function isBuiltInAgent(slug: string): boolean {
  return BUILT_IN_AGENTS.has(slug);
}

// ── AGENT_SETTABLE_FIELDS ──

describe("AGENT_SETTABLE_FIELDS", () => {
  test("包含所有期望的可设置字段", () => {
    const expected = ["model", "modelId", "prompt", "description", "extra", "agentNode", "knowledge"];
    for (const field of expected) {
      expect((AGENT_SETTABLE_FIELDS as readonly string[]).includes(field)).toBe(true);
    }
  });

  test("不再保留 top_p / topP 历史映射", () => {
    expect((AGENT_SETTABLE_FIELDS as readonly string[]).includes("top_p")).toBe(false);
    expect((AGENT_SETTABLE_FIELDS as readonly string[]).includes("topP")).toBe(false);
  });
});

// ── validateAgentData ──

describe("validateAgentData extra 校验", () => {
  test("合法数据返回 null", () => {
    expect(validateAgentData({ extra: { foo: "bar" } })).toBeNull();
    expect(validateAgentData({ knowledge: { knowledgeBaseIds: ["kb_1"] } })).toBeNull();
    expect(validateAgentData({})).toBeNull();
  });

  test("拒绝非法 extra", () => {
    expect(validateAgentData({ extra: [] })).toBe("INVALID_EXTRA");
    expect(validateAgentData({ extra: "bad" })).toBe("INVALID_EXTRA");
    expect(validateAgentData({ extra: "0.5" })).toBe("INVALID_EXTRA");
  });

  test("拒绝非法 knowledge", () => {
    expect(validateAgentData({ knowledge: { knowledgeBaseIds: [1] } })).toBe("INVALID_KNOWLEDGE_BASE_IDS");
  });
});

// ── isBuiltInAgent ──

describe("isBuiltInAgent (expanded)", () => {
  test("识别内置 agent", () => {
    expect(isBuiltInAgent("build")).toBe(true);
    expect(isBuiltInAgent("plan")).toBe(true);
    expect(isBuiltInAgent("general")).toBe(true);
    expect(isBuiltInAgent("explore")).toBe(true);
    expect(isBuiltInAgent("title")).toBe(true);
    expect(isBuiltInAgent("summary")).toBe(true);
    expect(isBuiltInAgent("compaction")).toBe(true);
  });

  test("拒绝非内置 agent", () => {
    expect(isBuiltInAgent("custom")).toBe(false);
    expect(isBuiltInAgent("Build")).toBe(false);
    expect(isBuiltInAgent("")).toBe(false);
  });
});
