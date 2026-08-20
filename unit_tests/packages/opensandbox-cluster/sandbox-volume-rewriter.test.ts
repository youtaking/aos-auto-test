// sandbox-volume-rewriter.test.ts — Sandbox 卷路径重写测试
// 测试目标：路径安全校验（穿越、NUL、绝对路径拒绝）与重写正确性
// 业务意图：确保用户提供的 volume 路径被安全收敛到 workspace 下，防止路径穿越攻击

import { describe, test, expect } from "bun:test";

// ── 复制纯函数（来自 packages/opensandbox-cluster/src/services/sandbox-volume-rewriter.ts）──

class SandboxVolumeRewriteError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SandboxVolumeRewriteError";
  }
}

function normalizeRelativePath(value: string): string {
  if (value.includes("\0")) throw new SandboxVolumeRewriteError("volume host path contains a NUL byte");

  const slashPath = value.replaceAll("\\", "/").replace(/^\/+/, "");
  if (/^[A-Za-z]:\//.test(slashPath)) {
    throw new SandboxVolumeRewriteError("volume host path must be relative to the sandbox workspace");
  }

  // posix.normalize 等效
  const normalized = normalizePath(slashPath);
  if (normalized === ".." || normalized.startsWith("../")) {
    throw new SandboxVolumeRewriteError("volume host path escapes the sandbox workspace");
  }
  return normalized === "." ? "" : normalized;
}

// 简化版 posix.normalize（够用即可）
function normalizePath(p: string): string {
  const parts = p.split("/").filter((s) => s !== "" && s !== ".");
  const result: string[] = [];
  for (const part of parts) {
    if (part === "..") {
      if (result.length > 0 && result[result.length - 1] !== "..") {
        result.pop();
      } else {
        result.push("..");
      }
    } else {
      result.push(part);
    }
  }
  return result.join("/") || ".";
}

function workspacePath(workspaceRoot: string, path: string): string {
  const relativePath = normalizeRelativePath(path);
  const root = workspaceRoot.replace(/\\/g, "/").replace(/\/+$/, "");
  if (!root.startsWith("/") || root === "/" || root.includes("\0") || root.includes("/../") || root.endsWith("/..")) {
    throw new SandboxVolumeRewriteError("workspace root must be a safe absolute path");
  }
  return relativePath ? `${root}/${relativePath}` : root;
}

function rewriteSandboxCreateBody(body: unknown, workspaceRoot: string): unknown {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    throw new SandboxVolumeRewriteError("sandbox create body must be an object");
  }

  const input = body as { volumes?: unknown };
  if (input.volumes === undefined) return body;
  if (!Array.isArray(input.volumes)) throw new SandboxVolumeRewriteError("volumes must be an array");

  return {
    ...input,
    volumes: input.volumes.map((volume) => {
      if (!volume || typeof volume !== "object" || Array.isArray(volume)) {
        throw new SandboxVolumeRewriteError("volume must be an object");
      }
      const item = volume as { host?: unknown } & Record<string, unknown>;
      if (!item.host || typeof item.host !== "object" || Array.isArray(item.host)) return volume;

      const host = item.host as { path?: unknown } & Record<string, unknown>;
      if (typeof host.path !== "string" || host.path.length === 0) {
        throw new SandboxVolumeRewriteError("host volume path is required");
      }

      return {
        ...item,
        host: {
          ...host,
          path: workspacePath(workspaceRoot, host.path),
        },
      };
    }),
  };
}

function isSandboxCreateRequest(method: string, path: string): boolean {
  return method.toUpperCase() === "POST" && path.replace(/^\/+|\/+$/g, "") === "v1/sandboxes";
}

// ── 测试 ──

describe("normalizeRelativePath", () => {
  test("正向 - 简单相对路径保持不变", () => {
    expect(normalizeRelativePath("data/file.txt")).toBe("data/file.txt");
  });

  test("正向 - 反斜杠转为正斜杠", () => {
    expect(normalizeRelativePath("data\\sub\\file.txt")).toBe("data/sub/file.txt");
  });

  test("正向 - 前导斜杠被去除", () => {
    expect(normalizeRelativePath("/data/file.txt")).toBe("data/file.txt");
  });

  test("异常 - NUL 字节拒绝", () => {
    expect(() => normalizeRelativePath("data\0/file")).toThrow("NUL byte");
  });

  test("异常 - Windows 绝对路径拒绝", () => {
    expect(() => normalizeRelativePath("C:/Windows/System32")).toThrow("must be relative");
  });

  test("异常 - 路径穿越拒绝", () => {
    expect(() => normalizeRelativePath("../../etc/passwd")).toThrow("escapes");
  });

  test("边界 - 纯 ../ 拒绝", () => {
    expect(() => normalizeRelativePath("..")).toThrow("escapes");
  });

  test("边界 - ./ 规范化为空字符串", () => {
    expect(normalizeRelativePath(".")).toBe("");
  });

  test("边界 - 空字符串返回空", () => {
    expect(normalizeRelativePath("")).toBe("");
  });
});

describe("workspacePath", () => {
  test("正向 - 拼接 workspace 根和相对路径", () => {
    expect(workspacePath("/workspace/sbx-1", "data/file.txt")).toBe("/workspace/sbx-1/data/file.txt");
  });

  test("正向 - 空相对路径返回 workspace 根", () => {
    expect(workspacePath("/workspace/sbx-1", "")).toBe("/workspace/sbx-1");
  });

  test("正向 - workspace 根尾部斜杠被去除", () => {
    expect(workspacePath("/workspace/sbx-1/", "data")).toBe("/workspace/sbx-1/data");
  });

  test("异常 - workspace 根非绝对路径拒绝", () => {
    expect(() => workspacePath("relative/path", "data")).toThrow("safe absolute path");
  });

  test("异常 - workspace 根含穿越拒绝", () => {
    expect(() => workspacePath("/workspace/../etc", "data")).toThrow("safe absolute path");
  });

  test("异常 - workspace 根含 NUL 拒绝", () => {
    expect(() => workspacePath("/workspace\0/evil", "data")).toThrow("safe absolute path");
  });
});

describe("rewriteSandboxCreateBody", () => {
  const root = "/workspace/sbx-1";

  test("正向 - volumes 中 host.path 被重写为 workspace 下的绝对路径", () => {
    const body = { volumes: [{ host: { path: "data" }, mount: "/mnt" }] };
    const result = rewriteSandboxCreateBody(body, root) as typeof body;
    expect(result.volumes[0].host.path).toBe("/workspace/sbx-1/data");
  });

  test("正向 - 无 volumes 字段时原样返回", () => {
    const body = { image: "alpine" };
    expect(rewriteSandboxCreateBody(body, root)).toBe(body);
  });

  test("正向 - volume 无 host 字段时保持不变", () => {
    const body = { volumes: [{ tmpfs: { size: 100 } }] };
    const result = rewriteSandboxCreateBody(body, root) as typeof body;
    expect(result.volumes[0]).toEqual({ tmpfs: { size: 100 } });
  });

  test("异常 - body 非对象抛错", () => {
    expect(() => rewriteSandboxCreateBody(null, root)).toThrow("must be an object");
    expect(() => rewriteSandboxCreateBody([], root)).toThrow("must be an object");
  });

  test("异常 - volumes 非数组抛错", () => {
    expect(() => rewriteSandboxCreateBody({ volumes: "bad" }, root)).toThrow("must be an array");
  });

  test("异常 - volume 非对象抛错", () => {
    expect(() => rewriteSandboxCreateBody({ volumes: ["bad"] }, root)).toThrow("volume must be an object");
  });

  test("异常 - host.path 为空字符串抛错", () => {
    expect(() => rewriteSandboxCreateBody({ volumes: [{ host: { path: "" } }] }, root)).toThrow("path is required");
  });

  test("异常 - host.path 穿越拒绝", () => {
    expect(() => rewriteSandboxCreateBody({ volumes: [{ host: { path: "../../etc" } }] }, root)).toThrow("escapes");
  });
});

describe("isSandboxCreateRequest", () => {
  test("正向 - POST v1/sandboxes 返回 true", () => {
    expect(isSandboxCreateRequest("POST", "v1/sandboxes")).toBe(true);
  });

  test("正向 - 带前导斜杠也返回 true", () => {
    expect(isSandboxCreateRequest("POST", "/v1/sandboxes")).toBe(true);
  });

  test("正向 - 大小写不敏感", () => {
    expect(isSandboxCreateRequest("post", "/v1/sandboxes")).toBe(true);
  });

  test("分支 - GET 返回 false", () => {
    expect(isSandboxCreateRequest("GET", "v1/sandboxes")).toBe(false);
  });

  test("分支 - 不同路径返回 false", () => {
    expect(isSandboxCreateRequest("POST", "v1/sandboxes/abc")).toBe(false);
  });

  test("边界 - 尾部斜杠不影响匹配", () => {
    expect(isSandboxCreateRequest("POST", "/v1/sandboxes/")).toBe(true);
  });
});
