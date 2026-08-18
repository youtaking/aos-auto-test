import { describe, expect, it, afterEach } from "bun:test";

// agent-sites.ts 纯函数测试
// 覆盖：isAgentSitesConfigured

// ── 纯函数复制 ──

function isAgentSitesConfigured(): boolean {
  return !!process.env.AGENT_SITES_BASE_URL && !!process.env.AGENT_SITES_MASTER_KEY;
}

// ── 测试 ──

describe("isAgentSitesConfigured", () => {
  const origBaseUrl = process.env.AGENT_SITES_BASE_URL;
  const origMasterKey = process.env.AGENT_SITES_MASTER_KEY;

  afterEach(() => {
    // 恢复原始环境变量
    if (origBaseUrl === undefined) {
      delete process.env.AGENT_SITES_BASE_URL;
    } else {
      process.env.AGENT_SITES_BASE_URL = origBaseUrl;
    }
    if (origMasterKey === undefined) {
      delete process.env.AGENT_SITES_MASTER_KEY;
    } else {
      process.env.AGENT_SITES_MASTER_KEY = origMasterKey;
    }
  });

  it("两个环境变量都存在时返回 true", () => {
    process.env.AGENT_SITES_BASE_URL = "http://localhost:3000";
    process.env.AGENT_SITES_MASTER_KEY = "mk_test_123";
    expect(isAgentSitesConfigured()).toBe(true);
  });

  it("缺少 BASE_URL 时返回 false", () => {
    delete process.env.AGENT_SITES_BASE_URL;
    process.env.AGENT_SITES_MASTER_KEY = "mk_test_123";
    expect(isAgentSitesConfigured()).toBe(false);
  });

  it("缺少 MASTER_KEY 时返回 false", () => {
    process.env.AGENT_SITES_BASE_URL = "http://localhost:3000";
    delete process.env.AGENT_SITES_MASTER_KEY;
    expect(isAgentSitesConfigured()).toBe(false);
  });

  it("两个都缺少时返回 false", () => {
    delete process.env.AGENT_SITES_BASE_URL;
    delete process.env.AGENT_SITES_MASTER_KEY;
    expect(isAgentSitesConfigured()).toBe(false);
  });

  it("BASE_URL 为空字符串时返回 false", () => {
    process.env.AGENT_SITES_BASE_URL = "";
    process.env.AGENT_SITES_MASTER_KEY = "mk_test_123";
    expect(isAgentSitesConfigured()).toBe(false);
  });

  it("MASTER_KEY 为空字符串时返回 false", () => {
    process.env.AGENT_SITES_BASE_URL = "http://localhost:3000";
    process.env.AGENT_SITES_MASTER_KEY = "";
    expect(isAgentSitesConfigured()).toBe(false);
  });

  it("两个都为空字符串时返回 false", () => {
    process.env.AGENT_SITES_BASE_URL = "";
    process.env.AGENT_SITES_MASTER_KEY = "";
    expect(isAgentSitesConfigured()).toBe(false);
  });
});
