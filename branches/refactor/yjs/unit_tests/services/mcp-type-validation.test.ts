import { describe, expect, test } from "bun:test";

// validateMcpConfig 和 isValidMcpName 扩展测试（type 验证场景）

const VALID_MCP_TYPES = new Set(["local", "remote", "streamable-http"]);

function validateMcpConfig(config: unknown): string | null {
  if (typeof config !== "object" || config === null) return "INVALID_CONFIG";
  const cfg = config as Record<string, unknown>;
  if ("enabled" in cfg && cfg.enabled === false && Object.keys(cfg).length === 1) return null;
  if (!("type" in cfg) || typeof cfg.type !== "string") return "INVALID_CONFIG_TYPE";
  const type = cfg.type as string;
  if (type === "local") {
    if (!Array.isArray(cfg.command) || cfg.command.length === 0) return "INVALID_COMMAND";
    if (cfg.command.some((c: unknown) => typeof c !== "string")) return "INVALID_COMMAND";
  } else if (type === "remote" || type === "streamable-http") {
    if (typeof cfg.url !== "string" || cfg.url.length === 0) return "INVALID_URL";
  } else {
    return "INVALID_CONFIG_TYPE";
  }
  return null;
}

const MCP_NAME_RE = /^[a-z][a-z0-9]*(-[a-z0-9]+)*$/;
function isValidMcpName(name: string): boolean {
  if (!name || name.length > 64) return false;
  return MCP_NAME_RE.test(name);
}

describe("validateMcpConfig type validation", () => {
  test("accepts streamable-http type", () => {
    expect(validateMcpConfig({ type: "streamable-http", url: "https://mcp.example.com/mcp", enabled: true })).toBeNull();
  });

  test("accepts local type", () => {
    expect(validateMcpConfig({ type: "local", command: ["npx", "server-github"], enabled: true })).toBeNull();
  });

  test("accepts remote type", () => {
    expect(validateMcpConfig({ type: "remote", url: "https://mcp.example.com/sse", enabled: true })).toBeNull();
  });

  test("rejects unknown type", () => {
    expect(validateMcpConfig({ type: "foo-bar", url: "https://example.com", enabled: true })).toBe("INVALID_CONFIG_TYPE");
  });

  test("allows enabled-only config", () => {
    expect(validateMcpConfig({ enabled: false })).toBeNull();
  });
});

describe("isValidMcpName (extended)", () => {
  test("accepts valid kebab-case names", () => {
    expect(isValidMcpName("my-server")).toBe(true);
    expect(isValidMcpName("a")).toBe(true);
    expect(isValidMcpName("server123")).toBe(true);
  });

  test("rejects invalid names", () => {
    expect(isValidMcpName("")).toBe(false);
    expect(isValidMcpName("My-Server")).toBe(false);
    expect(isValidMcpName("-server")).toBe(false);
    expect(isValidMcpName("server-")).toBe(false);
    expect(isValidMcpName("a--b")).toBe(false);
  });
});

describe("VALID_MCP_TYPES", () => {
  test("包含 local, remote, streamable-http", () => {
    expect(VALID_MCP_TYPES.has("local")).toBe(true);
    expect(VALID_MCP_TYPES.has("remote")).toBe(true);
    expect(VALID_MCP_TYPES.has("streamable-http")).toBe(true);
  });

  test("不包含其他类型", () => {
    expect(VALID_MCP_TYPES.has("stdio")).toBe(false);
    expect(VALID_MCP_TYPES.has("websocket")).toBe(false);
    expect(VALID_MCP_TYPES.has("")).toBe(false);
  });
});
