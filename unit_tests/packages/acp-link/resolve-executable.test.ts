// resolve-executable.test.ts — ACP-link 可执行文件路径解析测试
// 测试目标：resolveExecutable 的 PATH 搜索和 which 回退
// 业务意图：确保 ACP 实例能找到正确的命令行工具

import { describe, test, expect } from "bun:test";
import { execSync } from "node:child_process";
import { accessSync, constants } from "node:fs";
import { delimiter, join } from "node:path";

// ── 复制纯函数（来自 packages/acp-link/src/client/resolve-executable.ts）──

function resolveExecutable(command: string): string {
  const pathEntries = (process.env.PATH ?? "").split(delimiter).filter(Boolean);
  for (const entry of pathEntries) {
    const candidate = join(entry, command);
    try {
      accessSync(candidate, constants.X_OK);
      return candidate;
    } catch {
      // not found or not executable, try next entry
    }
  }

  try {
    const whichCommand = process.platform === "win32" ? "where" : "which";
    return execSync(`${whichCommand} ${command}`, {
      encoding: "utf-8",
      stdio: ["pipe", "pipe", "ignore"],
    })
      .trim()
      .split(/\r?\n/, 1)[0]
      .trim();
  } catch {
    throw new Error(`Required executable not found: ${command}`);
  }
}

// ── 测试 ──

describe("resolveExecutable", () => {
  test("正向 - 能找到系统自带的 node 命令", () => {
    const result = resolveExecutable("node");
    expect(result.length).toBeGreaterThan(0);
    expect(result).toContain("node");
  });

  test("异常 - 不存在的命令抛错", () => {
    expect(() => resolveExecutable("this-command-does-not-exist-xyz-123")).toThrow("Required executable not found");
  });

  test("正向 - 结果路径存在且可执行", () => {
    const result = resolveExecutable("node");
    // 不抛异常即表示文件存在
    expect(() => accessSync(result, constants.X_OK)).not.toThrow();
  });
});
