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
});
