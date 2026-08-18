import { describe, expect, test } from "bun:test";

// ── mcp-server.ts validateMcpConfig command 校验可读性验证 ──
// R37 修复：!every(typeof === "string") → some(typeof !== "string")

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

describe("validateMcpConfig command validation (some vs every)", () => {
  test("accepts valid string command array", () => {
    expect(
      validateMcpConfig({
        type: "local",
        command: ["npx", "-y", "server-github"],
      }),
    ).toBeNull();
  });

  test("rejects command array with non-string element", () => {
    expect(
      validateMcpConfig({
        type: "local",
        command: ["npx", 123, "server"],
      }),
    ).toBe("INVALID_COMMAND");
  });

  test("rejects empty command array", () => {
    expect(
      validateMcpConfig({
        type: "local",
        command: [],
      }),
    ).toBe("INVALID_COMMAND");
  });

  test("rejects command array with null", () => {
    expect(
      validateMcpConfig({
        type: "local",
        command: ["npx", null],
      }),
    ).toBe("INVALID_COMMAND");
  });

  test("rejects command array with object", () => {
    expect(
      validateMcpConfig({
        type: "local",
        command: [{ bin: "npx" }],
      }),
    ).toBe("INVALID_COMMAND");
  });
});
