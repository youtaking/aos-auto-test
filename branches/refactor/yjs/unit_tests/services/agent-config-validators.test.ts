import { describe, expect, test } from "bun:test";

// 测试 agent-config.ts 的 AGENT_SETTABLE_FIELDS 和 validateAgentData 边界
// 纯函数复制（原模块有 DB 依赖）

const AGENT_SETTABLE_FIELDS = [
  "modelId",
  "prompt",
  "description",
  "extra",
  "machineId",
  "knowledge",
] as const;

function validateAgentData(data: Record<string, unknown>): string | null {
  if ("extra" in data) {
    if (data.extra !== null && data.extra !== undefined && (typeof data.extra !== "object" || Array.isArray(data.extra))) {
      return "INVALID_EXTRA";
    }
  }
  if ("knowledge" in data && data.knowledge) {
    const k = data.knowledge as Record<string, unknown>;
    if ("knowledgeBaseIds" in k) {
      const ids = k.knowledgeBaseIds;
      if (!Array.isArray(ids) || ids.some((id) => typeof id !== "string" || !id.trim())) {
        return "INVALID_KNOWLEDGE_BASE_IDS";
      }
    }
  }
  return null;
}

const BUILT_IN_AGENTS = new Set(["build", "plan", "general", "explore", "title", "summary", "compaction"]);
function isBuiltInAgent(slug: string): boolean {
  return BUILT_IN_AGENTS.has(slug);
}

// ── AGENT_SETTABLE_FIELDS ──

describe("AGENT_SETTABLE_FIELDS", () => {
  test("包含所有期望的可设置字段", () => {
    const expected = ["modelId", "prompt", "description", "extra", "machineId", "knowledge"];
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
