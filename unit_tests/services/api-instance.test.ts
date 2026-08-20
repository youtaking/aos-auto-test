// api-instance.test.ts — API 实例服务纯逻辑测试
// 测试目标：toKebabSegment、pickEnvironment、ensureReadableAgent
// 业务意图：确保 Agent 实例连接时的名称规范化、环境选择、Agent 校验逻辑正确

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数 ──

class AppError extends Error {
  code: string;
  statusCode: number;
  constructor(message: string, code: string, statusCode: number) {
    super(message);
    this.name = "AppError";
    this.code = code;
    this.statusCode = statusCode;
  }
}

function toKebabSegment(input: string): string {
  return input
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 32);
}

interface AgentConfigRecord {
  id: string;
  organizationId?: string | null;
  name: string;
  description?: string | null;
}

function ensureReadableAgent(agent: AgentConfigRecord | null | undefined): AgentConfigRecord {
  if (!agent) {
    throw new AppError("Agent not found", "NOT_FOUND", 404);
  }
  return agent;
}

interface EnvironmentRecord {
  id: string;
  name: string;
  agentConfigId: string;
  userId: string;
}

function pickEnvironment(
  environments: EnvironmentRecord[],
  activeMap: Map<string, Array<{ status: string }>>,
): EnvironmentRecord | null {
  if (environments.length === 0) return null;
  const running = environments.find((env) => {
    const instances = activeMap.get(env.id) ?? [];
    return instances.some((instance) => instance.status === "running" || instance.status === "starting");
  });
  return running ?? environments[0] ?? null;
}

// ── tests ──

describe("api-instance 实例服务", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("toKebabSegment 名称 kebab-case 化", () => {
    test("英文名称保持小写", () => {
      expect(toKebabSegment("MyAgent")).toBe("myagent");
    });

    test("空格替换为连字符", () => {
      expect(toKebabSegment("My Agent")).toBe("my-agent");
    });

    test("多个特殊字符合并为一个连字符", () => {
      expect(toKebabSegment("My---Agent")).toBe("my-agent");
    });

    test("中文被替换为空（前后连字符被 trim）", () => {
      expect(toKebabSegment("智能助手")).toBe("");
    });

    test("混合中英文", () => {
      expect(toKebabSegment("AI 助手 v2")).toBe("ai-v2");
    });

    test("前后空格被 trim", () => {
      expect(toKebabSegment("  hello  ")).toBe("hello");
    });

    test("前后特殊字符被去除", () => {
      expect(toKebabSegment("--hello--")).toBe("hello");
    });

    test("截断到 32 字符", () => {
      const long = "a".repeat(50);
      expect(toKebabSegment(long).length).toBe(32);
    });

    test("空字符串返回空", () => {
      expect(toKebabSegment("")).toBe("");
    });

    test("纯特殊字符返回空", () => {
      expect(toKebabSegment("---")).toBe("");
    });

    test("数字保留", () => {
      expect(toKebabSegment("agent123")).toBe("agent123");
    });

    test("下划线替换为连字符", () => {
      expect(toKebabSegment("my_agent")).toBe("my-agent");
    });

    test("驼峰不拆分（只转小写）", () => {
      expect(toKebabSegment("MyAgentName")).toBe("myagentname");
    });
  });

  describe("ensureReadableAgent Agent 存在性校验", () => {
    test("null 抛 AppError 404", () => {
      expect(() => ensureReadableAgent(null)).toThrow("Agent not found");
      try {
        ensureReadableAgent(null);
      } catch (e: any) {
        expect(e.statusCode).toBe(404);
        expect(e.code).toBe("NOT_FOUND");
      }
    });

    test("undefined 抛 AppError 404", () => {
      expect(() => ensureReadableAgent(undefined)).toThrow("Agent not found");
    });

    test("有效 Agent 原样返回", () => {
      const agent: AgentConfigRecord = { id: "a1", name: "Test", description: "desc" };
      expect(ensureReadableAgent(agent)).toBe(agent);
    });
  });

  describe("pickEnvironment 环境选择", () => {
    const env1: EnvironmentRecord = { id: "env-1", name: "env1", agentConfigId: "a1", userId: "u1" };
    const env2: EnvironmentRecord = { id: "env-2", name: "env2", agentConfigId: "a1", userId: "u1" };

    test("空列表返回 null", () => {
      expect(pickEnvironment([], new Map())).toBeNull();
    });

    test("有 running 实例的环境被优先选中", () => {
      const activeMap = new Map<string, Array<{ status: string }>>([
        ["env-2", [{ status: "running" }]],
      ]);
      expect(pickEnvironment([env1, env2], activeMap)).toBe(env2);
    });

    test("有 starting 实例的环境被选中", () => {
      const activeMap = new Map<string, Array<{ status: string }>>([
        ["env-1", [{ status: "starting" }]],
      ]);
      expect(pickEnvironment([env1, env2], activeMap)).toBe(env1);
    });

    test("无运行实例时返回第一个环境", () => {
      expect(pickEnvironment([env1, env2], new Map())).toBe(env1);
    });

    test("stopped 状态不算运行", () => {
      const activeMap = new Map<string, Array<{ status: string }>>([
        ["env-1", [{ status: "stopped" }]],
        ["env-2", [{ status: "error" }]],
      ]);
      expect(pickEnvironment([env1, env2], activeMap)).toBe(env1); // fallback to first
    });

    test("多实例中有一个 running 即选中", () => {
      const activeMap = new Map<string, Array<{ status: string }>>([
        ["env-1", [{ status: "stopped" }, { status: "running" }]],
      ]);
      expect(pickEnvironment([env1, env2], activeMap)).toBe(env1);
    });

    test("第一个 running 环境被选中（不是最后一个）", () => {
      const activeMap = new Map<string, Array<{ status: string }>>([
        ["env-1", [{ status: "running" }]],
        ["env-2", [{ status: "running" }]],
      ]);
      expect(pickEnvironment([env1, env2], activeMap)).toBe(env1);
    });
  });
});
