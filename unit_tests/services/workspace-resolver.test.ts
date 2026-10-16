// 根的语义已变更（FenixAgent 1.7 C1）：resolveWorkspacePath 不再直读 process.env.WORKSPACE_ROOT，
// 改读 agent-runtime 模块配置里的 workspaceRoot（宿主在装配期解析好的绝对路径）。
// 用例因此经 initializeAgentRuntimeModuleConfig() 装配配置，而不是改环境变量——
// 沿用「改 env」的写法在配置未装进基础设施时也会静默通过，测不到真正的取数路径；
// 而 WORKSPACE_ROOT 这个 env 现在根本不参与解析，改它只会让期望值恒为夹具默认根。

import { describe, expect, test, beforeEach } from "bun:test";
import { join } from "node:path";
import { initializeAgentRuntimeModuleConfig } from "@fenix/agent-runtime/server/testing";
import { resolveWorkspacePath } from "@src/agent-runtime/server/services/workspace-resolver";

describe("resolveWorkspacePath", () => {
  beforeEach(() => {
    // 夹具缺省根是 cwd/workspaces，与宿主对空 env 的解析结果同形。
    initializeAgentRuntimeModuleConfig();
  });

  test("默认使用 cwd/workspaces 作为根目录", () => {
    const result = resolveWorkspacePath("org-1", "user-1", "env-1");
    expect(result).toBe(join(process.cwd(), "workspaces", "org-1", "user-1", "env-1"));
  });

  test("模块配置的 workspaceRoot 生效", () => {
    initializeAgentRuntimeModuleConfig({ workspaceRoot: "/data/rcs" });

    const result = resolveWorkspacePath("org-1", "user-1", "env-1");
    expect(result).toBe(join("/data/rcs", "org-1", "user-1", "env-1"));
  });

  test("不同 orgId + userId + envId 产生不同路径", () => {
    initializeAgentRuntimeModuleConfig({ workspaceRoot: "/data/rcs" });

    const path1 = resolveWorkspacePath("org-a", "user-1", "env-1");
    const path2 = resolveWorkspacePath("org-a", "user-1", "env-2");
    const path3 = resolveWorkspacePath("org-a", "user-2", "env-1");
    const path4 = resolveWorkspacePath("org-b", "user-1", "env-1");

    expect(path1).not.toBe(path2);
    expect(path1).not.toBe(path3);
    expect(path1).not.toBe(path4);
    expect(path2).not.toBe(path3);
    expect(path2).not.toBe(path4);
    expect(path3).not.toBe(path4);
  });

  test("相同 org/user 下不同 envId 产生不同路径", () => {
    initializeAgentRuntimeModuleConfig({ workspaceRoot: "/data" });

    const pathA = resolveWorkspacePath("org-1", "user-1", "env-aaa");
    const pathB = resolveWorkspacePath("org-1", "user-1", "env-bbb");

    expect(pathA).toBe(join("/data", "org-1", "user-1", "env-aaa"));
    expect(pathB).toBe(join("/data", "org-1", "user-1", "env-bbb"));
    expect(pathA).not.toBe(pathB);
  });

  test("空标识被原样拼接，不产生额外路径层级", () => {
    initializeAgentRuntimeModuleConfig({ workspaceRoot: "/data" });

    expect(resolveWorkspacePath("", "", "")).toBe(join("/data", "", "", ""));
  });
});
