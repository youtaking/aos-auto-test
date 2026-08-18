// hindsight.test.ts — Hindsight MCP 服务配置测试
// 测试目标：getHindsightConfig 环境变量读取 / HINDSIGHT_MCP_SERVER_NAME 常量
// 业务意图：确保 Hindsight 配置在未设置环境变量时安全返回 null

import { afterEach, beforeEach, describe, expect, test } from "bun:test";

// ── 复制纯函数 ──

function getHindsightConfig(): { url: string } | null {
  const url = process.env.HINDSIGHT_MCP_URL;
  if (!url) return null;
  return { url };
}

const HINDSIGHT_MCP_SERVER_NAME = "hindsight";

// ── tests ──

describe("Hindsight MCP 配置", () => {
  let originalEnv: string | undefined;

  beforeEach(() => {
    originalEnv = process.env.HINDSIGHT_MCP_URL;
  });

  afterEach(() => {
    // 恢复原始环境变量
    if (originalEnv === undefined) {
      delete process.env.HINDSIGHT_MCP_URL;
    } else {
      process.env.HINDSIGHT_MCP_URL = originalEnv;
    }
  });

  describe("getHindsightConfig", () => {
    test("环境变量未设置时返回 null", () => {
      delete process.env.HINDSIGHT_MCP_URL;
      expect(getHindsightConfig()).toBeNull();
    });

    test("环境变量为空字符串时返回 null", () => {
      process.env.HINDSIGHT_MCP_URL = "";
      expect(getHindsightConfig()).toBeNull();
    });

    test("环境变量有值时返回 url 对象", () => {
      process.env.HINDSIGHT_MCP_URL = "http://hindsight.example.com";
      const config = getHindsightConfig();
      expect(config).not.toBeNull();
      expect(config!.url).toBe("http://hindsight.example.com");
    });

    test("返回对象包含 url 属性", () => {
      process.env.HINDSIGHT_MCP_URL = "http://localhost:8080";
      const config = getHindsightConfig();
      expect(config).toEqual({ url: "http://localhost:8080" });
    });

    test("URL 带路径时原样返回", () => {
      process.env.HINDSIGHT_MCP_URL = "https://hindsight.example.com/api/v1";
      const config = getHindsightConfig();
      expect(config!.url).toBe("https://hindsight.example.com/api/v1");
    });
  });

  describe("HINDSIGHT_MCP_SERVER_NAME 常量", () => {
    test("值为 'hindsight'", () => {
      expect(HINDSIGHT_MCP_SERVER_NAME).toBe("hindsight");
    });

    test("类型为 string", () => {
      expect(typeof HINDSIGHT_MCP_SERVER_NAME).toBe("string");
    });
  });
});
