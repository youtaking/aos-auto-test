import { describe, expect, test, mock, beforeEach } from "bun:test";

// ── Mock 依赖 ──

let mockEnsureSystemAdmin: ReturnType<typeof mock>;
let mockSyncSkills: ReturnType<typeof mock>;

// 新版源码的依赖入口（apps/server/src/services/sync-builtin.ts 顶部静态导入）：
// ensureSystemAdmin 来自 @fenix/identity/server，builtin skill 同步来自 @fenix/agent-config/server。
mock.module("@fenix/identity/server", () => ({
  ensureSystemAdmin: mockEnsureSystemAdmin,
}));

mock.module("@fenix/agent-config/server", () => ({
  syncBuiltinSkillsToSystemAdmin: mockSyncSkills,
}));

import { syncBuiltin } from "@fenix/services/sync-builtin";

const systemAdminResult = {
  organization: { id: "system-org-id" },
  userId: "system-user-id",
};

const expectedCtx = {
  organizationId: "system-org-id",
  userId: "system-user-id",
  role: "owner" as const,
};

describe("syncBuiltin", () => {
  beforeEach(() => {
    mock.restore();
    mockEnsureSystemAdmin = mock(async () => systemAdminResult);
    mockSyncSkills = mock(async () => {});
  });

  test("正常流程：先引导系统 admin 再同步 builtin skills", async () => {
    await syncBuiltin({
      ensureSystemAdmin: mockEnsureSystemAdmin as any,
      syncBuiltinSkillsToSystemAdmin: mockSyncSkills,
    });

    expect(mockEnsureSystemAdmin).toHaveBeenCalledTimes(1);
    expect(mockSyncSkills).toHaveBeenCalledTimes(1);
  });

  test("传递给 skill 同步的上下文包含正确的 org/user/role", async () => {
    await syncBuiltin({
      ensureSystemAdmin: mockEnsureSystemAdmin as any,
      syncBuiltinSkillsToSystemAdmin: mockSyncSkills,
    });

    expect(mockSyncSkills).toHaveBeenCalledWith(expectedCtx);
  });

  test("ensureSystemAdmin 失败时向上传播错误", async () => {
    mockEnsureSystemAdmin = mock(async () => {
      throw new Error("DB connection refused");
    });

    await expect(
      syncBuiltin({
        ensureSystemAdmin: mockEnsureSystemAdmin as any,
        syncBuiltinSkillsToSystemAdmin: mockSyncSkills,
      }),
    ).rejects.toThrow("DB connection refused");

    // skill 同步不应被调用
    expect(mockSyncSkills).not.toHaveBeenCalled();
  });

  test("syncBuiltinSkillsToSystemAdmin 失败时向上传播错误", async () => {
    mockSyncSkills = mock(async () => {
      throw new Error("skill sync failed");
    });

    await expect(
      syncBuiltin({
        ensureSystemAdmin: mockEnsureSystemAdmin as any,
        syncBuiltinSkillsToSystemAdmin: mockSyncSkills,
      }),
    ).rejects.toThrow("skill sync failed");
  });

  test("ensureSystemAdmin 先于 syncBuiltinSkills 调用（顺序保证）", async () => {
    const callOrder: string[] = [];
    mockEnsureSystemAdmin = mock(async () => {
      callOrder.push("ensureSystemAdmin");
      return systemAdminResult;
    });
    mockSyncSkills = mock(async () => {
      callOrder.push("syncBuiltinSkills");
    });

    await syncBuiltin({
      ensureSystemAdmin: mockEnsureSystemAdmin as any,
      syncBuiltinSkillsToSystemAdmin: mockSyncSkills,
    });

    expect(callOrder).toEqual(["ensureSystemAdmin", "syncBuiltinSkills"]);
  });
});
