import { describe, expect, test } from "bun:test";
import { isExecutable, resolveExecutable } from "@fenix/utils/executable";

describe("isExecutable", () => {
  test("returns true for an executable file", () => {
    const bunPath = process.execPath;
    expect(isExecutable(bunPath)).toBe(true);
  });

  test("returns false for a non-existent file", () => {
    expect(isExecutable("/nonexistent/path/binary")).toBe(false);
  });
});

describe("resolveExecutable", () => {
  test("resolves 'bun' executable", () => {
    const path = resolveExecutable("bun");
    expect(path).toBeTruthy();
    expect(typeof path).toBe("string");
  });

  test("resolves 'node' executable", () => {
    const path = resolveExecutable("node");
    expect(path).toBeTruthy();
  });

  test("throws for non-existent command", () => {
    expect(() => resolveExecutable("nonexistent_command_xyz_12345")).toThrow(/not found/);
  });
});
