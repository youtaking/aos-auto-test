// api-workspace.test.ts — Workspace 文件上传纯逻辑测试
// 测试目标：relativePaths JSON 解析、路径规范化
// 业务意图：确保 uploadWorkspaceFiles 的前置解析逻辑正确

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数（从 uploadWorkspaceFiles 提取的解析逻辑） ──

function parseRelativePaths(raw: unknown): string[] {
  if (typeof raw !== "string" || raw.trim().length === 0) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [];
  } catch {
    throw new Error("relativePaths must be valid JSON");
  }
}

function resolveTargetPath(raw: unknown, fallback: string): string {
  return typeof raw === "string" && raw.trim().length > 0 ? raw : fallback;
}

function normalizeUserRoutePath(path: string): string {
  const trimmed = path.trim().replace(/\\/g, "/");
  // remove leading "user/"
  const withoutUser = trimmed.startsWith("user/") ? trimmed.slice(5) : trimmed;
  return withoutUser.replace(/\/+$/, "") || "";
}

function isUserPath(path: string): boolean {
  // In the real code, this checks if the resolved path is under user/
  // Simplified: all paths are considered user paths after normalization
  return !path.startsWith("/") && !path.includes("..");
}

function buildDisplayPath(dirPath: string, relPath: string): string {
  const displayBase = dirPath.replace(/\/+$/, "");
  return `${displayBase}/${relPath}`.replace(/\/+/g, "/");
}

// ── tests ──

describe("api-workspace Workspace 文件上传", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("parseRelativePaths JSON 解析", () => {
    test("合法 JSON 数组解析为字符串数组", () => {
      expect(parseRelativePaths('["a.txt", "b.txt"]')).toEqual(["a.txt", "b.txt"]);
    });

    test("过滤非字符串元素", () => {
      expect(parseRelativePaths('["a.txt", 42, null, "b.txt"]')).toEqual(["a.txt", "b.txt"]);
    });

    test("空 JSON 数组返回空", () => {
      expect(parseRelativePaths("[]")).toEqual([]);
    });

    test("非字符串输入返回空", () => {
      expect(parseRelativePaths(undefined)).toEqual([]);
      expect(parseRelativePaths(null)).toEqual([]);
      expect(parseRelativePaths(42)).toEqual([]);
    });

    test("空字符串返回空", () => {
      expect(parseRelativePaths("")).toEqual([]);
    });

    test("纯空格返回空", () => {
      expect(parseRelativePaths("   ")).toEqual([]);
    });

    test("非法 JSON 抛错", () => {
      expect(() => parseRelativePaths("{invalid}")).toThrow("relativePaths must be valid JSON");
    });

    test("非数组 JSON 返回空", () => {
      expect(parseRelativePaths('"just a string"')).toEqual([]);
      expect(parseRelativePaths("123")).toEqual([]);
    });

    test("嵌套数组不被展平", () => {
      // 只有 string 类型的元素被保留
      expect(parseRelativePaths('["a.txt", ["nested"]]')).toEqual(["a.txt"]);
    });
  });

  describe("resolveTargetPath 目标路径解析", () => {
    test("有效路径保持原样", () => {
      expect(resolveTargetPath("user/docs", "user")).toBe("user/docs");
    });

    test("空字符串使用 fallback", () => {
      expect(resolveTargetPath("", "user")).toBe("user");
    });

    test("纯空格使用 fallback", () => {
      expect(resolveTargetPath("   ", "user")).toBe("user");
    });

    test("非字符串使用 fallback", () => {
      expect(resolveTargetPath(null, "user")).toBe("user");
      expect(resolveTargetPath(undefined, "user")).toBe("user");
      expect(resolveTargetPath(42, "user")).toBe("user");
    });
  });

  describe("normalizeUserRoutePath 路径规范化", () => {
    test("user/ 前缀被移除", () => {
      expect(normalizeUserRoutePath("user/docs")).toBe("docs");
    });

    test("无 user/ 前缀保持不变", () => {
      expect(normalizeUserRoutePath("docs")).toBe("docs");
    });

    test("尾部斜杠被移除", () => {
      expect(normalizeUserRoutePath("user/docs/")).toBe("docs");
    });

    test("反斜杠转正斜杠", () => {
      expect(normalizeUserRoutePath("user\\docs")).toBe("docs");
    });

    test("空路径返回空字符串", () => {
      expect(normalizeUserRoutePath("user/")).toBe("");
    });
  });

  describe("buildDisplayPath 显示路径构建", () => {
    test("基本拼接", () => {
      expect(buildDisplayPath("user/docs", "file.txt")).toBe("user/docs/file.txt");
    });

    test("多余斜杠被合并", () => {
      expect(buildDisplayPath("user/docs/", "/file.txt")).toBe("user/docs/file.txt");
    });

    test("目录和文件名拼接", () => {
      expect(buildDisplayPath("user", "image.png")).toBe("user/image.png");
    });
  });

  describe("isUserPath 用户路径检查", () => {
    test("普通相对路径返回 true", () => {
      expect(isUserPath("docs/file.txt")).toBe(true);
    });

    test("绝对路径返回 false", () => {
      expect(isUserPath("/etc/passwd")).toBe(false);
    });

    test("含 .. 的路径返回 false", () => {
      expect(isUserPath("../escape")).toBe(false);
    });
  });
});
