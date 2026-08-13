import { describe, expect, it } from "bun:test";

// toServerInfo 纯函数扩展测试（更完整的 command/url 守卫和降级场景）
// 复制自 services/config/mcp-server.ts

function toServerInfo(name: string, entry: { type: string; config: Record<string, unknown>; enabled: boolean }) {
  const cfg = entry.config;
  const cfgType = (cfg.type as string) || entry.type;

  if (!entry.enabled && !cfgType) {
    return { name, type: "disabled", enabled: false, summary: "已禁用", timeout: undefined };
  }

  if (cfgType === "local") {
    const cmd = Array.isArray(cfg.command) ? (cfg.command as string[]) : null;
    return {
      name,
      type: "local",
      enabled: entry.enabled,
      summary: cmd?.[0] ?? "",
      timeout: cfg.timeout as number | undefined,
    };
  }

  if (cfgType === "remote" || cfgType === "streamable-http") {
    return {
      name,
      type: cfgType,
      enabled: entry.enabled,
      summary: (cfg.url as string) ?? "",
      timeout: cfg.timeout as number | undefined,
    };
  }

  // 未知类型归为 remote
  return {
    name,
    type: "remote",
    enabled: entry.enabled,
    summary: (cfg.url as string) ?? "",
    timeout: cfg.timeout as number | undefined,
  };
}

describe("toServerInfo (extended)", () => {
  it("禁用且无 type 返回 disabled 类型", () => {
    const result = toServerInfo("test", { type: "", config: {}, enabled: false });
    expect(result.type).toBe("disabled");
    expect(result.enabled).toBe(false);
  });

  it("local 类型解析 command 数组", () => {
    const result = toServerInfo("my-server", {
      type: "local",
      config: { type: "local", command: ["npx", "-y", "server-github"] },
      enabled: true,
    });
    expect(result.type).toBe("local");
    expect(result.summary).toBe("npx");
  });

  it("command 为非数组时安全降级为空字符串", () => {
    const result = toServerInfo("bad-server", {
      type: "local",
      config: { type: "local", command: "not-an-array" },
      enabled: true,
    });
    expect(result.type).toBe("local");
    expect(result.summary).toBe("");
  });

  it("command 缺失时安全降级", () => {
    const result = toServerInfo("no-cmd", {
      type: "local",
      config: { type: "local" },
      enabled: true,
    });
    expect(result.type).toBe("local");
    expect(result.summary).toBe("");
  });

  it("remote 类型解析 url", () => {
    const result = toServerInfo("remote-server", {
      type: "remote",
      config: { type: "remote", url: "https://api.example.com/sse" },
      enabled: true,
    });
    expect(result.type).toBe("remote");
    expect(result.summary).toBe("https://api.example.com/sse");
  });

  it("remote 类型无 url 时降级为空字符串", () => {
    const result = toServerInfo("no-url", {
      type: "remote",
      config: { type: "remote" },
      enabled: true,
    });
    expect(result.type).toBe("remote");
    expect(result.summary).toBe("");
  });

  it("透传 timeout 配置", () => {
    const result = toServerInfo("timeout-server", {
      type: "local",
      config: { type: "local", command: ["npx", "server"], timeout: 5000 },
      enabled: true,
    });
    expect(result.timeout).toBe(5000);
  });

  it("streamable-http 类型正确识别", () => {
    const result = toServerInfo("stream-server", {
      type: "streamable-http",
      config: { type: "streamable-http", url: "https://api.example.com/mcp" },
      enabled: true,
    });
    expect(result.type).toBe("streamable-http");
    expect(result.summary).toBe("https://api.example.com/mcp");
  });

  it("streamable-http 无 url 时降级为空字符串", () => {
    const result = toServerInfo("stream-no-url", {
      type: "streamable-http",
      config: { type: "streamable-http" },
      enabled: true,
    });
    expect(result.type).toBe("streamable-http");
    expect(result.summary).toBe("");
  });

  it("未知类型归为 remote", () => {
    const result = toServerInfo("unknown-server", {
      type: "custom",
      config: { type: "custom", url: "https://custom.example.com" },
      enabled: true,
    });
    expect(result.type).toBe("remote");
  });
});
