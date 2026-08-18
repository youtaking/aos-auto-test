import { describe, expect, test } from "bun:test";
import { isExecutable, resolveExecutable } from "@fenix/utils/executable";

// ── Source: src/utils/executable.ts ──
// Source version: FenixAgent/src/utils/executable.ts (commit f5ac00e, 2025-08)
//
// CI Bun environment note:
//   These tests use direct imports from the source (not copies) via @fenix/utils/executable path alias.
//   The source uses Node.js-specific APIs: accessSync/constants.X_OK from node:fs,
//   execSync from node:child_process. Bun provides compatibility shims for these.
//   In CI (unit-runner container based on oven/bun:latest), the environment is Linux.
//   On Windows dev machines, path separator differs (: vs ;) and 'which' vs 'where' differs.
//   resolveExecutable uses ':' as PATH separator (Linux convention) — this may not work
//   correctly on Windows where PATH uses ';'. Tests account for this by testing with
//   known-available executables (bun, node) that exist on both platforms.

describe("isExecutable", () => {
  test("returns true for an executable file", () => {
    const bunPath = process.execPath;
    expect(isExecutable(bunPath)).toBe(true);
  });

  test("returns false for a non-existent file", () => {
    expect(isExecutable("/nonexistent/path/binary")).toBe(false);
  });

  // ── Boundary tests ──

  test("returns false for empty string path", () => {
    expect(isExecutable("")).toBe(false);
  });
});

describe("resolveExecutable", () => {
  test("resolves 'bun' executable", () => {
    const path = resolveExecutable("bun");
    expect(typeof path).toBe("string");
    expect(path.length).toBeGreaterThan(0);
  });

  test("resolves 'node' executable", () => {
    const path = resolveExecutable("node");
    expect(typeof path).toBe("string");
    expect(path.length).toBeGreaterThan(0);
  });

  test("throws for non-existent command", () => {
    expect(() => resolveExecutable("nonexistent_command_xyz_12345")).toThrow();
  });
});
