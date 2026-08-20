// agent-knowledge.test.ts — Agent 知识库绑定纯逻辑测试
// 测试目标：resolveAgentKnowledgePolicy、normalizeKnowledgeBaseIds、InvalidKnowledgeBindingError
// 业务意图：确保知识库绑定解析、去重、策略默认值正确

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数 ──

const DEFAULT_SEARCH_FIRST = true;
const DEFAULT_MAX_RESULTS = 5;

interface AgentKnowledgePolicy {
  searchFirst?: boolean;
  maxResults?: number;
  defaultNamespaces?: string[];
}

interface ResolvedAgentKnowledgePolicy {
  searchFirst: boolean;
  maxResults: number;
  defaultNamespaces: string[];
}

class InvalidKnowledgeBindingError extends Error {
  code = "INVALID_KNOWLEDGE_BINDINGS";
  constructor(message: string) {
    super(message);
    this.name = "InvalidKnowledgeBindingError";
  }
}

function resolveAgentKnowledgePolicy(policy?: AgentKnowledgePolicy | null): ResolvedAgentKnowledgePolicy {
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

function normalizeKnowledgeBaseIds(knowledgeBaseIds: string[] | undefined): string[] {
  const seen = new Set<string>();
  const ids: string[] = [];
  for (const value of knowledgeBaseIds ?? []) {
    if (typeof value !== "string") continue;
    const id = value.trim();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    ids.push(id);
  }
  return ids;
}

// ── tests ──

describe("agent-knowledge 知识库绑定", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("resolveAgentKnowledgePolicy 策略解析", () => {
    test("null 策略使用全部默认值", () => {
      const result = resolveAgentKnowledgePolicy(null);
      expect(result.searchFirst).toBe(true);
      expect(result.maxResults).toBe(5);
      expect(result.defaultNamespaces).toEqual([]);
    });

    test("undefined 策略使用全部默认值", () => {
      const result = resolveAgentKnowledgePolicy(undefined);
      expect(result.searchFirst).toBe(true);
      expect(result.maxResults).toBe(5);
      expect(result.defaultNamespaces).toEqual([]);
    });

    test("空对象使用全部默认值", () => {
      const result = resolveAgentKnowledgePolicy({});
      expect(result.searchFirst).toBe(true);
      expect(result.maxResults).toBe(5);
      expect(result.defaultNamespaces).toEqual([]);
    });

    test("自定义 searchFirst", () => {
      const result = resolveAgentKnowledgePolicy({ searchFirst: false });
      expect(result.searchFirst).toBe(false);
    });

    test("自定义 maxResults", () => {
      const result = resolveAgentKnowledgePolicy({ maxResults: 10 });
      expect(result.maxResults).toBe(10);
    });

    test("有效 defaultNamespaces 被保留", () => {
      const result = resolveAgentKnowledgePolicy({
        defaultNamespaces: ["ns1", "ns2"],
      });
      expect(result.defaultNamespaces).toEqual(["ns1", "ns2"]);
    });

    test("过滤空字符串和非字符串", () => {
      const result = resolveAgentKnowledgePolicy({
        defaultNamespaces: ["ns1", "", "  ", null as any, 42 as any, "ns2"],
      });
      expect(result.defaultNamespaces).toEqual(["ns1", "ns2"]);
    });

    test("非数组 defaultNamespaces 返回空数组", () => {
      const result = resolveAgentKnowledgePolicy({
        defaultNamespaces: "ns1" as any,
      });
      expect(result.defaultNamespaces).toEqual([]);
    });

    test("maxResults 为 0 时使用 0", () => {
      const result = resolveAgentKnowledgePolicy({ maxResults: 0 });
      expect(result.maxResults).toBe(0);
    });
  });

  describe("normalizeKnowledgeBaseIds ID 去重规范化", () => {
    test("正常 ID 列表保持顺序", () => {
      const result = normalizeKnowledgeBaseIds(["kb-1", "kb-2", "kb-3"]);
      expect(result).toEqual(["kb-1", "kb-2", "kb-3"]);
    });

    test("去重：重复 ID 只保留第一个", () => {
      const result = normalizeKnowledgeBaseIds(["kb-1", "kb-2", "kb-1", "kb-2"]);
      expect(result).toEqual(["kb-1", "kb-2"]);
    });

    test("过滤空字符串", () => {
      const result = normalizeKnowledgeBaseIds(["kb-1", "", "kb-2"]);
      expect(result).toEqual(["kb-1", "kb-2"]);
    });

    test("过滤纯空格", () => {
      const result = normalizeKnowledgeBaseIds(["kb-1", "  ", "kb-2"]);
      expect(result).toEqual(["kb-1", "kb-2"]);
    });

    test("trim 前后空格", () => {
      const result = normalizeKnowledgeBaseIds(["  kb-1  ", "kb-2"]);
      expect(result).toEqual(["kb-1", "kb-2"]);
    });

    test("undefined 返回空数组", () => {
      const result = normalizeKnowledgeBaseIds(undefined);
      expect(result).toEqual([]);
    });

    test("空数组返回空数组", () => {
      const result = normalizeKnowledgeBaseIds([]);
      expect(result).toEqual([]);
    });

    test("过滤非字符串值", () => {
      const result = normalizeKnowledgeBaseIds(["kb-1", 42 as any, null as any, "kb-2"]);
      expect(result).toEqual(["kb-1", "kb-2"]);
    });

    test("trim 后相同的 ID 视为重复", () => {
      const result = normalizeKnowledgeBaseIds(["kb-1", "  kb-1  "]);
      expect(result).toEqual(["kb-1"]);
    });
  });

  describe("InvalidKnowledgeBindingError", () => {
    test("code 为 INVALID_KNOWLEDGE_BINDINGS", () => {
      const err = new InvalidKnowledgeBindingError("test");
      expect(err.code).toBe("INVALID_KNOWLEDGE_BINDINGS");
    });

    test("instanceof Error 为 true", () => {
      const err = new InvalidKnowledgeBindingError("test");
      expect(err instanceof Error).toBe(true);
    });

    test("message 正确传递", () => {
      const err = new InvalidKnowledgeBindingError("知识库不存在");
      expect(err.message).toBe("知识库不存在");
    });
  });
});
