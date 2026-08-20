// workspace-registry.test.ts — workspace 注册表测试
// 测试目标：getWorkspaceSync 的同步查询、registerWorkspace/unregisterWorkspace 的 CRUD
// 业务意图：确保 environmentId → workspace path 映射的正确管理

import { describe, test, expect, beforeEach } from "bun:test";

// ── 复制纯函数（简化自 packages/acp-link/src/client/workspace-registry.ts）──
// 去掉磁盘 IO，只测内存 CRUD 逻辑

const cache = new Map<string, string>();

function registerWorkspace(environmentId: string, workspace: string): void {
  cache.set(environmentId, workspace);
}

function unregisterWorkspace(environmentId: string): void {
  cache.delete(environmentId);
}

function getWorkspaceSync(environmentId: string): string | null {
  return cache.get(environmentId) ?? null;
}

// ── 测试 ──

describe("workspace-registry (内存逻辑)", () => {
  beforeEach(() => {
    cache.clear();
  });

  describe("getWorkspaceSync", () => {
    test("正向 - 已注册的返回 workspace 路径", () => {
      cache.set("env-1", "/workspace/env-1");
      expect(getWorkspaceSync("env-1")).toBe("/workspace/env-1");
    });

    test("分支 - 未注册返回 null", () => {
      expect(getWorkspaceSync("missing")).toBeNull();
    });
  });

  describe("registerWorkspace", () => {
    test("正向 - 注册后可查询", () => {
      registerWorkspace("env-1", "/workspace/env-1");
      expect(getWorkspaceSync("env-1")).toBe("/workspace/env-1");
    });

    test("正向 - 覆盖已有注册", () => {
      registerWorkspace("env-1", "/old-path");
      registerWorkspace("env-1", "/new-path");
      expect(getWorkspaceSync("env-1")).toBe("/new-path");
    });
  });

  describe("unregisterWorkspace", () => {
    test("正向 - 注销后返回 null", () => {
      registerWorkspace("env-1", "/workspace/env-1");
      unregisterWorkspace("env-1");
      expect(getWorkspaceSync("env-1")).toBeNull();
    });

    test("边界 - 注销不存在的 envId 不抛错", () => {
      expect(() => unregisterWorkspace("missing")).not.toThrow();
    });
  });

  describe("多环境隔离", () => {
    test("正向 - 不同 environmentId 独立", () => {
      registerWorkspace("env-1", "/ws-1");
      registerWorkspace("env-2", "/ws-2");
      expect(getWorkspaceSync("env-1")).toBe("/ws-1");
      expect(getWorkspaceSync("env-2")).toBe("/ws-2");
    });

    test("正向 - 注销一个不影响其他", () => {
      registerWorkspace("env-1", "/ws-1");
      registerWorkspace("env-2", "/ws-2");
      unregisterWorkspace("env-1");
      expect(getWorkspaceSync("env-1")).toBeNull();
      expect(getWorkspaceSync("env-2")).toBe("/ws-2");
    });
  });
});
