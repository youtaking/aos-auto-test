// prod-view.test.ts — ProdView 服务层 CRUD 测试
// 测试目标：create/get/list/update/delete/load 各路径的响应格式和 repo 调用
// 业务意图：确保 ProdView 服务层正确转发 repo 调用、处理 NOT_FOUND/DISABLED 分支
//
// 采用 active-stub + Proxy 模式：prodViewRepo 通过 Proxy 实时转发到当前测试的
// stub 对象，避免 Bun mock.restore() 不清理 call count 导致的跨测试污染。

import { describe, expect, test, mock, beforeEach, afterEach } from "bun:test";
import { CreateProdViewSchema } from "@fenix/schemas/prod-view.schema";

// ── Active stub 注册表 ──

type RepoMock = {
  create: ReturnType<typeof mock>;
  getById: ReturnType<typeof mock>;
  listByOrg: ReturnType<typeof mock>;
  update: ReturnType<typeof mock>;
  delete: ReturnType<typeof mock>;
};

type EnvMock = {
  createWebEnvironment: ReturnType<typeof mock>;
};

let activeRepo: RepoMock;
let activeEnv: EnvMock;

function freshRepo(): RepoMock {
  return {
    create: mock(async (input: any) => ({ id: "pv-new", ...input })),
    getById: mock(async (_orgId: string, _id: string): Promise<any> => null),
    listByOrg: mock(async (_orgId: string, _filters?: unknown): Promise<any[]> => []),
    update: mock(async (_orgId: string, _id: string, input: any) => ({ id: "pv-1", ...input })),
    delete: mock(async (_orgId: string, _id: string): Promise<boolean> => true),
  };
}

function freshEnv(): EnvMock {
  return {
    createWebEnvironment: mock(async (_input: unknown) => ({ id: "env-created-id" })),
  };
}

// ── Mock 依赖（Proxy 实时转发到 active stub）──

const repoProxy = new Proxy({} as RepoMock, {
  get: (_t, prop) => (activeRepo as any)[prop as string],
});

mock.module("@fenix/repositories/prod-view", () => {
  const obj: Record<string, unknown> = {};
  Object.defineProperty(obj, "prodViewRepo", {
    enumerable: true,
    configurable: true,
    get: () => repoProxy,
  });
  return obj;
});

mock.module("@fenix/services/environment", () => ({
  // ESM 导出在导入时求值，必须保留稳定函数，在调用时取当前 stub。
  createWebEnvironment: (input: unknown) => activeEnv.createWebEnvironment(input),
}));

import {
  createProdView,
  getProdView,
  listProdViews,
  updateProdView,
  deleteProdView,
  loadProdView,
  setProdViewDeps,
} from "@fenix/services/prod-view";

const ctx = { organizationId: "org-1", userId: "user-1", role: "owner" as const };

const sampleRow = {
  id: "pv-1",
  name: "My View",
  description: "A test view",
  agentId: "agent-config-1",
  modulesConfig: { chat: true },
  enabled: true,
  createdBy: "user-1",
};

describe("prod-view 服务", () => {
  const findInstance = mock(async (_envId: string, _userId: string) => ({ id: "instance-created-id" }) as any);
  beforeEach(() => {
    mock.restore();
    activeRepo = freshRepo();
    activeEnv = freshEnv();
    findInstance.mockClear();
    setProdViewDeps({ findOrCreateDefaultInstance: findInstance });
  });
  afterEach(() => setProdViewDeps(null));

  // ── createProdView ──

  describe("createProdView", () => {
    test("正常创建返回 success + 数据", async () => {
      const input = { name: "New View", description: "desc", agentId: "agent-1", modulesConfig: {} };
      const result = await createProdView(ctx, input);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual(
          expect.objectContaining({
            name: "New View",
            description: "desc",
            agentId: "agent-1",
          }),
        );
      }
    });

    test("repo.create 接收 organizationId 和 createdBy 等字段", async () => {
      const input = { name: "V", description: "d", agentId: "a", modulesConfig: {} };
      await createProdView(ctx, input);
      expect(activeRepo.create).toHaveBeenCalledWith(
        expect.objectContaining({
          organizationId: "org-1",
          createdBy: "user-1",
          name: "V",
        }),
      );
    });
  });

  // ── getProdView ──

  describe("getProdView", () => {
    test("存在时返回 success + 数据", async () => {
      activeRepo.getById.mockImplementation(async () => sampleRow);
      const result = await getProdView(ctx, "pv-1");
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual(sampleRow);
      }
    });

    test("不存在时返回 NOT_FOUND", async () => {
      activeRepo.getById.mockImplementation(async () => null);
      const result = await getProdView(ctx, "pv-missing");
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe("NOT_FOUND");
        expect(result.error.message).toBe("ProdView not found");
      }
    });

    test("repo.getById 使用正确的 orgId + id", async () => {
      activeRepo.getById.mockImplementation(async () => sampleRow);
      await getProdView(ctx, "pv-1");
      expect(activeRepo.getById).toHaveBeenCalledWith("org-1", "pv-1");
    });
  });

  // ── listProdViews ──

  describe("listProdViews", () => {
    test("无过滤器返回空列表", async () => {
      activeRepo.listByOrg.mockImplementation(async () => []);
      const result = await listProdViews(ctx);
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual([]);
      }
    });

    test("返回 repo 结果列表", async () => {
      const rows = [sampleRow, { ...sampleRow, id: "pv-2" }];
      activeRepo.listByOrg.mockImplementation(async () => rows);
      const result = await listProdViews(ctx);
      if (result.success) {
        expect(result.data).toHaveLength(2);
        expect(result.data[0].id).toBe("pv-1");
        expect(result.data[1].id).toBe("pv-2");
      }
    });

    test("按 agentId 过滤", async () => {
      activeRepo.listByOrg.mockImplementation(async () => [sampleRow]);
      await listProdViews(ctx, { agentId: "agent-config-1" });
      expect(activeRepo.listByOrg).toHaveBeenCalledWith("org-1", { agentId: "agent-config-1" });
    });

    test("按 enabled 过滤", async () => {
      activeRepo.listByOrg.mockImplementation(async () => [sampleRow]);
      await listProdViews(ctx, { enabled: true });
      expect(activeRepo.listByOrg).toHaveBeenCalledWith("org-1", { enabled: true });
    });

    test("同时按 agentId + enabled 过滤", async () => {
      activeRepo.listByOrg.mockImplementation(async () => []);
      await listProdViews(ctx, { agentId: "a", enabled: false });
      expect(activeRepo.listByOrg).toHaveBeenCalledWith("org-1", { agentId: "a", enabled: false });
    });
  });

  // ── updateProdView ──

  describe("updateProdView", () => {
    test("存在时更新成功", async () => {
      activeRepo.getById.mockImplementation(async () => sampleRow);
      activeRepo.update.mockImplementation(async () => ({ ...sampleRow, name: "Updated" }));

      const result = await updateProdView(ctx, "pv-1", {
        name: "Updated",
        description: "new desc",
        modulesConfig: { chat: false },
        enabled: false,
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.name).toBe("Updated");
      }
    });

    test("repo.update 接收正确的更新字段", async () => {
      activeRepo.getById.mockImplementation(async () => sampleRow);
      const input = { name: "X", description: "Y", modulesConfig: {}, enabled: true };
      await updateProdView(ctx, "pv-1", input);

      expect(activeRepo.update).toHaveBeenCalledWith("org-1", "pv-1", {
        name: "X",
        description: "Y",
        modulesConfig: {},
        enabled: true,
      });
    });

    test("不存在时返回 NOT_FOUND", async () => {
      activeRepo.getById.mockImplementation(async () => null);
      const result = await updateProdView(ctx, "pv-missing", {
        name: "X",
        description: "Y",
        modulesConfig: {},
        enabled: true,
      });
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe("NOT_FOUND");
      }
    });

    test("不存在时不调用 repo.update", async () => {
      activeRepo.getById.mockImplementation(async () => null);
      await updateProdView(ctx, "pv-missing", {
        name: "X",
        description: "Y",
        modulesConfig: {},
        enabled: true,
      });
      expect(activeRepo.update).not.toHaveBeenCalled();
    });
  });

  // ── deleteProdView ──

  describe("deleteProdView", () => {
    test("存在且删除成功返回 { ok: true }", async () => {
      activeRepo.getById.mockImplementation(async () => sampleRow);
      activeRepo.delete.mockImplementation(async () => true);

      const result = await deleteProdView(ctx, "pv-1");
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual({ ok: true });
      }
    });

    test("不存在时返回 NOT_FOUND 且不调用 delete", async () => {
      activeRepo.getById.mockImplementation(async () => null);
      const result = await deleteProdView(ctx, "pv-missing");
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe("NOT_FOUND");
      }
      expect(activeRepo.delete).not.toHaveBeenCalled();
    });

    test("repo.delete 返回 false 时返回 DELETE_FAILED", async () => {
      activeRepo.getById.mockImplementation(async () => sampleRow);
      activeRepo.delete.mockImplementation(async () => false);

      const result = await deleteProdView(ctx, "pv-1");
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe("DELETE_FAILED");
        expect(result.error.message).toBe("Failed to delete");
      }
    });
  });

  // ── loadProdView ──

  describe("loadProdView", () => {
    test("不存在返回 NOT_FOUND", async () => {
      activeRepo.getById.mockImplementation(async () => null);
      const result = await loadProdView(ctx, "pv-missing");
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe("NOT_FOUND");
      }
    });

    test("已禁用返回 DISABLED", async () => {
      activeRepo.getById.mockImplementation(async () => ({ ...sampleRow, enabled: false }));
      const result = await loadProdView(ctx, "pv-1");
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.code).toBe("DISABLED");
        expect(result.error.message).toBe("ProdView is disabled");
      }
    });

    test("启用视图为当前用户创建环境并返回持久实例", async () => {
      activeRepo.getById.mockImplementation(async () => ({ ...sampleRow }));
      const result = await loadProdView(ctx, "pv-1");
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual({
          agentConfigId: sampleRow.agentId,
          environmentId: "env-created-id",
          instanceUid: "instance-created-id",
          name: sampleRow.name,
          modulesConfig: sampleRow.modulesConfig,
        });
        expect(activeEnv.createWebEnvironment).toHaveBeenCalledWith({
          name: `env-${sampleRow.agentId.slice(0, 8)}`,
          description: sampleRow.description,
          agentConfigId: sampleRow.agentId,
          autoStart: true,
          userId: ctx.userId,
          organizationId: ctx.organizationId,
        });
        expect(findInstance).toHaveBeenCalledWith("env-created-id", ctx.userId);
      }
    });

    test("创建视图必须绑定合法 agentId，不接受空值或缺失", () => {
      expect(CreateProdViewSchema.safeParse({ name: "View", agentId: null }).success).toBe(false);
      expect(CreateProdViewSchema.safeParse({ name: "View" }).success).toBe(false);
      expect(CreateProdViewSchema.safeParse({ name: "View", agentId: "invalid" }).success).toBe(false);
      expect(CreateProdViewSchema.safeParse({
        name: "View", agentId: "01d1ac89-2c49-46ac-8b8c-a8493df4cc97",
      }).success).toBe(true);
    });
  });
});
