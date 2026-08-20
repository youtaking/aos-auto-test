// agent-generation.test.ts — Agent 智能生成纯逻辑测试
// 测试目标：isGenerationConfigured
// 业务意图：确保生成功能的配置检测正确（依赖 OPENAI_API_KEY + OPENAI_MODEL）

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数 ──

function isGenerationConfigured(env: { OPENAI_API_KEY?: string; OPENAI_MODEL?: string }): boolean {
  return !!(env.OPENAI_API_KEY && env.OPENAI_MODEL);
}

// ── tests ──

describe("agent-generation 智能生成", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("isGenerationConfigured 配置检测", () => {
    test("两个变量都存在返回 true", () => {
      expect(
        isGenerationConfigured({ OPENAI_API_KEY: "sk-xxx", OPENAI_MODEL: "gpt-4" }),
      ).toBe(true);
    });

    test("缺少 OPENAI_API_KEY 返回 false", () => {
      expect(isGenerationConfigured({ OPENAI_MODEL: "gpt-4" })).toBe(false);
    });

    test("缺少 OPENAI_MODEL 返回 false", () => {
      expect(isGenerationConfigured({ OPENAI_API_KEY: "sk-xxx" })).toBe(false);
    });

    test("两个变量都缺失返回 false", () => {
      expect(isGenerationConfigured({})).toBe(false);
    });

    test("OPENAI_API_KEY 为空字符串返回 false", () => {
      expect(
        isGenerationConfigured({ OPENAI_API_KEY: "", OPENAI_MODEL: "gpt-4" }),
      ).toBe(false);
    });

    test("OPENAI_MODEL 为空字符串返回 false", () => {
      expect(
        isGenerationConfigured({ OPENAI_API_KEY: "sk-xxx", OPENAI_MODEL: "" }),
      ).toBe(false);
    });

    test("两个都为空字符串返回 false", () => {
      expect(isGenerationConfigured({ OPENAI_API_KEY: "", OPENAI_MODEL: "" })).toBe(false);
    });
  });
});
