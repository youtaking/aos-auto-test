// ── Source provenance ──
// 旧版共享模块 `src/utils/executable.ts` 已随 FenixAgent 2026-09-17 重构（bda524de3）拆散，
// 现在只以「各插件私有副本」存在，且彼此行为已分化：
//   - packages/plugin-opencode/src/process/executable.ts
//   - packages/plugin-peri/src/process/executable.ts
//   - packages/plugin-ccb/src/process/executable.ts
//   - packages/acp-link/src/client/resolve-executable.ts
// 这些副本位于各包内部（包的 exports 不暴露 process/executable 深路径），
// 无法直连导入，故按「拆散的模块改纯函数副本」策略：把 plugin-opencode 变体的实现
// 原样拷贝到本文件测试。若上游实现变更，需同步本副本。
//
// CI Bun environment note:
//   The source uses Node.js-specific APIs: accessSync/constants.X_OK from node:fs,
//   execSync from node:child_process. Bun provides compatibility shims for these.
//   In CI (unit-runner container based on oven/bun:latest), the environment is Linux.
//   On Windows dev machines, path separator differs (: vs ;) and 'which' vs 'where' differs —
//   the implementation branches on process.platform, so both are handled.

import { describe, expect, test } from "bun:test";
import { execSync } from "node:child_process";
import { accessSync, constants } from "node:fs";
import { delimiter, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const EXECUTABLE_FILE_DIR = dirname(fileURLToPath(import.meta.url));

export function isExecutable(filePath: string): boolean {
  try {
    accessSync(filePath, constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

function listAncestorDirs(startDir: string): string[] {
  const directories: string[] = [];
  let currentDir = resolve(startDir);

  while (true) {
    directories.push(currentDir);
    const parentDir = dirname(currentDir);
    if (parentDir === currentDir) {
      return directories;
    }
    currentDir = parentDir;
  }
}

export function resolveExecutable(command: string): string {
  // 1. 优先使用 which/where 查找 PATH 上的全局版本（跳过 node_modules/.bin 避免锁定项目内旧版本）
  try {
    const whichCommand = process.platform === "win32" ? "where" : "which";
    const result = execSync(`${whichCommand} -a ${command}`, {
      encoding: "utf-8",
      stdio: ["pipe", "pipe", "ignore"],
    }).trim();
    const candidates = result
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean);
    for (const candidate of candidates) {
      if (candidate.includes("node_modules/.bin")) continue;
      return candidate;
    }
  } catch {
    // 忽略 which/where 失败
  }

  // 2. 回退：扫描 PATH 但排除 node_modules/.bin
  const pathEntries = (process.env.PATH ?? "").split(delimiter).filter(Boolean);
  for (const entry of pathEntries) {
    if (entry.includes("node_modules/.bin")) continue;
    const candidate = join(entry, command);
    if (isExecutable(candidate)) {
      return candidate;
    }
  }

  // 3. 全局版本都找不到时，才回退到 node_modules/.bin（兜底）
  const searchRoots = new Set<string>([...listAncestorDirs(process.cwd()), ...listAncestorDirs(EXECUTABLE_FILE_DIR)]);
  for (const rootDir of searchRoots) {
    const localBin = join(rootDir, "node_modules", ".bin", command);
    if (isExecutable(localBin)) {
      return localBin;
    }
  }

  throw new Error(`Required executable not found: ${command}`);
}

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
  test("resolves 'bun' to a path that is actually executable", () => {
    const resolved = resolveExecutable("bun");
    expect(resolved.length).toBeGreaterThan(0);
    expect(isExecutable(resolved)).toBe(true);
  });

  test("does not resolve from node_modules/.bin while a global version exists", () => {
    const resolved = resolveExecutable("bun");
    expect(resolved.includes("node_modules/.bin")).toBe(false);
  });

  test("throws for non-existent command", () => {
    expect(() => resolveExecutable("nonexistent_command_xyz_12345")).toThrow(
      "Required executable not found: nonexistent_command_xyz_12345",
    );
  });
});

describe("listAncestorDirs", () => {
  test("includes the start directory and terminates at the filesystem root", () => {
    const dirs = listAncestorDirs(resolve("/a/b/c"));
    expect(dirs[0]).toBe(resolve("/a/b/c"));
    expect(dirs[1]).toBe(resolve("/a/b"));
    expect(dirs.at(-1)).toBe(resolve("/"));
  });
});
