// api-v1-skill.test.ts — v1 Skill 对外服务与投影测试
// 测试目标：toApiSkill / ApiV1SkillService 的 get/list/import/patch/remove
// 业务意图：确保对外投影不含文件系统路径，覆盖导入冲突、PATCH 分流与删除返回 null
// 源：packages/resources/skill/src/server/services/api-v1-skill.ts（main a7f477a9e）

import { describe, expect, mock, test } from "bun:test";

// ── 复制实现 ──

class AppError extends Error {
  code: string;
  statusCode: number;
  constructor(message: string, code: string, statusCode: number) {
    super(message);
    this.name = "AppError";
    this.code = code;
    this.statusCode = statusCode;
  }
}

class ValidationError extends AppError {
  constructor(message: string) {
    super(message, "VALIDATION_ERROR", 400);
  }
}

class NotFoundError extends AppError {
  constructor(message: string) {
    super(message, "NOT_FOUND", 404);
  }
}

class ConflictError extends AppError {
  constructor(message: string) {
    super(message, "ALREADY_EXISTS", 409);
  }
}

interface ActorContext {
  organizationId: string;
  userId: string;
}

interface SkillListItem {
  id: string;
  name: string;
  description?: string | null;
  scope: string;
  access: string;
}

interface SkillDetailView extends SkillListItem {
  content: string;
  metadata: Record<string, string>;
}

interface UploadSkillFile {
  skillName?: string;
  relativePath: string;
  content: string;
}

function toApiSkill(row: SkillListItem | SkillDetailView) {
  const summary = { id: row.id, name: row.name, description: row.description, scope: row.scope, access: row.access };
  return "content" in row ? { ...summary, content: row.content, metadata: row.metadata } : summary;
}

interface SkillFacade {
  readDetailById(actor: ActorContext, id: string): Promise<SkillDetailView | null>;
  list(
    actor: ActorContext,
    query: { limit: number; offset: number },
  ): Promise<{ items: SkillListItem[]; total: number }>;
  importSingleSkill(
    actor: ActorContext,
    files: UploadSkillFile[],
    options: { overwrite: boolean },
  ): Promise<
    | { status: "conflict" }
    | { status: "ok"; created?: boolean; detail: SkillDetailView }
  >;
  setPublicReadableById(actor: ActorContext, id: string, publicReadable: boolean): Promise<void>;
  updateById(
    actor: ActorContext,
    id: string,
    data: Record<string, unknown>,
    options: { publicReadable?: boolean; replaceMetadata: boolean },
  ): Promise<void>;
  removeById(actor: ActorContext, id: string): Promise<void>;
}

class ApiV1SkillService {
  constructor(private readonly facade: SkillFacade) {}
  async get(actor: ActorContext, id: string) {
    const row = await this.facade.readDetailById(actor, id);
    if (!row) throw new NotFoundError("Skill not found");
    return { ...toApiSkill(row), content: row.content, metadata: row.metadata };
  }
  async list(actor: ActorContext, query: { page: number; pageSize: number }) {
    const result = await this.facade.list(actor, { limit: query.pageSize, offset: (query.page - 1) * query.pageSize });
    return { ...query, total: result.total, items: result.items.map(toApiSkill) };
  }
  async import(actor: ActorContext, files: UploadSkillFile[], overwrite: boolean) {
    const name = files[0]?.skillName;
    if (!name) throw new ValidationError("Skill files required");
    const result = await this.facade.importSingleSkill(actor, files, { overwrite });
    if (result.status === "conflict") throw new ConflictError("Skill already exists");
    return {
      created: result.created ?? true,
      data: { ...toApiSkill(result.detail), content: result.detail.content, metadata: result.detail.metadata },
    };
  }
  async patch(
    actor: ActorContext,
    id: string,
    input: { content?: string; description?: string; metadata?: Record<string, string>; publicReadable?: boolean },
  ) {
    const { publicReadable, ...data } = input;
    if (Object.keys(data).length === 0 && publicReadable !== undefined)
      await this.facade.setPublicReadableById(actor, id, publicReadable);
    else
      await this.facade.updateById(actor, id, data, { publicReadable, replaceMetadata: input.metadata !== undefined });
    return this.get(actor, id);
  }
  async remove(actor: ActorContext, id: string) {
    await this.facade.removeById(actor, id);
    return null;
  }
}

// ── 测试辅助 ──

const actor: ActorContext = { organizationId: "org-1", userId: "user-1" };

function detail(overrides: Partial<SkillDetailView> = {}): SkillDetailView {
  return {
    id: "skill-1",
    name: "demo-skill",
    description: "demo",
    scope: "organization",
    access: "write",
    content: "# Demo",
    metadata: { owner: "test" },
    ...overrides,
  };
}

function facade(overrides: Partial<SkillFacade> = {}): SkillFacade {
  return {
    readDetailById: mock(async () => detail()),
    list: mock(async () => ({
      items: [{ id: "skill-1", name: "demo-skill", description: "demo", scope: "organization", access: "write" }],
      total: 1,
    })),
    importSingleSkill: mock(async () => ({ status: "ok" as const, created: true, detail: detail() })),
    setPublicReadableById: mock(async () => {}),
    updateById: mock(async () => {}),
    removeById: mock(async () => {}),
    ...overrides,
  };
}

// ── tests ──

describe("api-v1-skill v1 Skill 对外服务", () => {
  describe("toApiSkill 投影", () => {
    test("列表项只含摘要字段，不暴露 content/metadata", () => {
      const summary = toApiSkill({
        id: "skill-1",
        name: "demo-skill",
        description: "demo",
        scope: "organization",
        access: "write",
      });
      expect(summary).toEqual({
        id: "skill-1",
        name: "demo-skill",
        description: "demo",
        scope: "organization",
        access: "write",
      });
      expect(summary).not.toHaveProperty("content");
    });

    test("详情包含正文与元数据", () => {
      expect(toApiSkill(detail())).toMatchObject({ content: "# Demo", metadata: { owner: "test" } });
    });

    test("description 缺省保持 undefined", () => {
      expect(toApiSkill(detail({ description: undefined })).description).toBeUndefined();
    });
  });

  describe("get", () => {
    test("不存在时抛 404", async () => {
      const service = new ApiV1SkillService(facade({ readDetailById: mock(async () => null) }));
      await expect(service.get(actor, "missing")).rejects.toMatchObject({ code: "NOT_FOUND", statusCode: 404 });
    });

    test("存在时返回详情正文与元数据", async () => {
      const service = new ApiV1SkillService(facade());
      expect(await service.get(actor, "skill-1")).toMatchObject({ id: "skill-1", content: "# Demo" });
    });
  });

  describe("list", () => {
    test("分页参数换算为 limit/offset", async () => {
      const list = mock(async () => ({ items: [], total: 0 }));
      const service = new ApiV1SkillService(facade({ list }));
      await service.list(actor, { page: 3, pageSize: 10 });
      expect(list).toHaveBeenCalledWith(actor, { limit: 10, offset: 20 });
    });

    test("返回分页结构并投影列表项", async () => {
      const service = new ApiV1SkillService(facade());
      const result = await service.list(actor, { page: 1, pageSize: 5 });
      expect(result).toEqual({
        page: 1,
        pageSize: 5,
        total: 1,
        items: [
          {
            id: "skill-1",
            name: "demo-skill",
            description: "demo",
            scope: "organization",
            access: "write",
          },
        ],
      });
    });
  });

  describe("import", () => {
    const files: UploadSkillFile[] = [{ skillName: "demo-skill", relativePath: "SKILL.md", content: "# Demo" }];

    test("缺少 skillName 时抛 VALIDATION_ERROR", async () => {
      const service = new ApiV1SkillService(facade());
      await expect(service.import(actor, [{ relativePath: "SKILL.md", content: "x" }], false)).rejects.toMatchObject({
        code: "VALIDATION_ERROR",
        statusCode: 400,
      });
    });

    test("冲突时抛 409 ALREADY_EXISTS", async () => {
      const service = new ApiV1SkillService(
        facade({ importSingleSkill: mock(async () => ({ status: "conflict" as const })) }),
      );
      await expect(service.import(actor, files, false)).rejects.toMatchObject({
        code: "ALREADY_EXISTS",
        statusCode: 409,
      });
    });

    test("透传 overwrite 并返回 created 标记", async () => {
      const importSingleSkill = mock(async () => ({ status: "ok" as const, created: false, detail: detail() }));
      const service = new ApiV1SkillService(facade({ importSingleSkill }));
      const result = await service.import(actor, files, true);
      expect(importSingleSkill).toHaveBeenCalledWith(actor, files, { overwrite: true });
      expect(result.created).toBe(false);
      expect(result.data).toMatchObject({ content: "# Demo" });
    });

    test("结果未给出 created 时视为新建", async () => {
      const service = new ApiV1SkillService(
        facade({ importSingleSkill: mock(async () => ({ status: "ok" as const, detail: detail() })) }),
      );
      expect((await service.import(actor, files, false)).created).toBe(true);
    });
  });

  describe("patch", () => {
    test("仅 publicReadable 时走可见范围接口", async () => {
      const f = facade();
      const service = new ApiV1SkillService(f);
      await service.patch(actor, "skill-1", { publicReadable: true });
      expect(f.setPublicReadableById).toHaveBeenCalledWith(actor, "skill-1", true);
      expect(f.updateById).toHaveBeenCalledTimes(0);
    });

    test("内容字段走更新接口并替换元数据", async () => {
      const f = facade();
      const service = new ApiV1SkillService(f);
      await service.patch(actor, "skill-1", { content: "# New", metadata: { a: "b" } });
      expect(f.updateById).toHaveBeenCalledWith(
        actor,
        "skill-1",
        { content: "# New", metadata: { a: "b" } },
        { publicReadable: undefined, replaceMetadata: true },
      );
    });

    test("未传 metadata 时不替换元数据", async () => {
      const f = facade();
      const service = new ApiV1SkillService(f);
      await service.patch(actor, "skill-1", { description: "new desc" });
      expect(f.updateById).toHaveBeenCalledWith(
        actor,
        "skill-1",
        { description: "new desc" },
        { publicReadable: undefined, replaceMetadata: false },
      );
    });

    test("内容与可见范围同时提交时一并更新", async () => {
      const f = facade();
      const service = new ApiV1SkillService(f);
      await service.patch(actor, "skill-1", { description: "d", publicReadable: false });
      expect(f.updateById).toHaveBeenCalledWith(
        actor,
        "skill-1",
        { description: "d" },
        { publicReadable: false, replaceMetadata: false },
      );
    });

    test("返回更新后的详情", async () => {
      const service = new ApiV1SkillService(facade());
      expect(await service.patch(actor, "skill-1", { description: "d" })).toMatchObject({ id: "skill-1" });
    });
  });

  describe("remove", () => {
    test("删除后返回 null", async () => {
      const f = facade();
      const service = new ApiV1SkillService(f);
      expect(await service.remove(actor, "skill-1")).toBeNull();
      expect(f.removeById).toHaveBeenCalledWith(actor, "skill-1");
    });
  });
});
