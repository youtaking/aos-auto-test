import { describe, expect, test } from "bun:test";
import { buildTrustedOrigins } from "@fenix/auth/trusted-origins";

describe("trusted origins", () => {
  test("includes local dev origin and configured public URLs", () => {
    expect(
      buildTrustedOrigins({
        betterAuthUrl: "https://fenix-agent.pazhoulab-huangpu.com",
        rcsBaseUrl: "https://fenix-agent.pazhoulab-huangpu.com/",
      }),
    ).toEqual(["http://localhost:5173", "https://fenix-agent.pazhoulab-huangpu.com"]);
  });

  test("parses comma-separated trusted origins", () => {
    expect(
      buildTrustedOrigins({
        trustedOrigins: "https://a.example.com, https://b.example.com/",
        rcsBaseUrl: "https://a.example.com",
      }),
    ).toEqual(["http://localhost:5173", "https://a.example.com", "https://b.example.com"]);
  });

  // ── P1: normalizeOrigin 分支覆盖 ──

  test("空输入 {} 仅返回 localhost", () => {
    expect(buildTrustedOrigins({})).toEqual(["http://localhost:5173"]);
  });

  test("无效 URL fallback 到 replace 尾斜杠路径", () => {
    expect(
      buildTrustedOrigins({
        betterAuthUrl: "not-a-valid-url///",
      }),
    ).toEqual(["http://localhost:5173", "not-a-valid-url"]);
  });

  test("betterAuthUrl 与 rcsBaseUrl 相同时去重", () => {
    expect(
      buildTrustedOrigins({
        betterAuthUrl: "https://same.example.com",
        rcsBaseUrl: "https://same.example.com/",
      }),
    ).toEqual(["http://localhost:5173", "https://same.example.com"]);
  });

  test("trustedOrigins 含空白项时跳过空项", () => {
    expect(
      buildTrustedOrigins({
        trustedOrigins: "https://a.com, , https://b.com",
      }),
    ).toEqual(["http://localhost:5173", "https://a.com", "https://b.com"]);
  });
});
