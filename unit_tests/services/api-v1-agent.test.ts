// api-v1-agent.test.ts — v1 Agent 对外 facade 编排测试
// 测试目标：ApiV1AgentFacade 的 get/list/create/patch/remove 与绑定校验、事务错误映射
// 业务意图：确保对外创建/更新严格校验名称与绑定、只读资源不可改、知识库竞态错误仍按 v1 语义返回
// 源：packages/resources/agent-config/src/server/facades/api-v1-agent-facade.ts（main a7f477a9e）

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制实现（模块与事务函数以依赖注入） ──

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

class ForbiddenError extends AppError {
  constructor(message: string) {
    super(message, "FORBIDDEN", 403);
  }
}

class InvalidKnowledgeBindingError extends Error {}

interface ActorContext {
  organizationId: string;
  userId: string;
  activeOrganizationId?: string;
}

interface AuthorizedAgentConfig {
  id: string;
  name: string;
  description?: string | null;
  modelId?: string | null;
  agentNode?: unknown;
  machineId: string | null;
  prompt?: string | null;
  extra?: Record<string, unknown> | null;
  scope: { organizationId?: string; visibility: "public" | "private" };
  access: { actions: string[] };
}

interface AgentConfigSaveCommand<T> {
  organizationId: string;
  resourceId?: string;
  write: () => Promise<T>;
  bindings: Record<string, unknown>;
  enableMemory?: boolean;
  associations: Record<string, unknown>;
}

interface AgentConfigServerModule {
  facade: {
    getById(actor: ActorContext, id: string): Promise<AuthorizedAgentConfig | null>;
    list(
      actor: ActorContext,
      query: { limit: number; offset: number },
    ): Promise<{ items: AuthorizedAgentConfig[]; total: number }>;
    create(actor: ActorContext, input: Record<string, unknown>): Promise<AuthorizedAgentConfig>;
    updateById(actor: ActorContext, id: string, data: unknown, options: unknown): Promise<AuthorizedAgentConfig>;
    removeById(actor: ActorContext, id: string): Promise<void>;
  };
  associations: {
    getKnowledge(id: string): Promise<unknown>;
    listSkillIds(id: string): Promise<string[]>;
    listMcpIds(id: string): Promise<string[]>;
    isMemoryEnabled(id: string): Promise<boolean>;
    listKnowledgeBindings(id: string): Promise<unknown[]>;
  };
}

const BUILT_IN = new Set(["assistant", "sales-assistant"]);

function isBuiltInAgent(name: string): boolean {
  return BUILT_IN.has(name);
}

function isValidAgentName(name: string): boolean {
  return (
    typeof name === "string" &&
    name.length >= 1 &&
    name.length <= 64 &&
    !name.includes("--") &&
    /^[\p{L}0-9][\p{L}0-9 -]*[\p{L}0-9]$|^[\p{L}0-9]$/u.test(name)
  );
}

function resolveAgentNode(row: { agentNode?: unknown; machineId: string | null }) {
  if (row.agentNode !== null && row.agentNode !== undefined) return row.agentNode;
  return row.machineId ? { kind: "machine", machineId: row.machineId } : {};
}

function toAgentConfigWriteData(data: Record<string, unknown>) {
  const write: Record<string, unknown> = {};
  for (const field of ["model", "modelId", "prompt", "description", "extra", "agentNode"]) {
    if (data[field] !== undefined) write[field] = data[field] ?? null;
  }
  return write;
}

function validateAgentData(data: Record<string, unknown>): string | null {
  if (data.name !== undefined && (typeof data.name !== "string" || !isValidAgentName(data.name)))
    return "INVALID_AGENT_NAME";
  if (data.temperature !== undefined) {
    if (typeof data.temperature !== "number" || data.temperature < 0 || data.temperature > 2)
      return "INVALID_TEMPERATURE";
  }
  return null;
}

interface FacadeDeps {
  module: AgentConfigServerModule;
  saveAgentConfig: <T>(command: AgentConfigSaveCommand<T>) => Promise<T>;
  authorizeAgentBindings: (
    actor: ActorContext,
    organizationId: string,
    input: Record<string, unknown>,
    modelId?: string | null,
  ) => Promise<void>;
}

class ApiV1AgentFacade {
  constructor(private readonly deps: FacadeDeps) {}

  private async require(actor: ActorContext, id: string) {
    const row = await this.deps.module.facade.getById(actor, id);
    if (!row) throw new NotFoundError("Agent not found");
    return row;
  }

  private summary(row: AuthorizedAgentConfig) {
    return {
      id: row.id,
      name: row.name,
      description: row.description ?? null,
      modelId: row.modelId ?? null,
      agentNode: resolveAgentNode(row) ?? {},
      scope: row.scope,
      access: row.access,
    };
  }

  private async detail(row: AuthorizedAgentConfig) {
    const { associations } = this.deps.module;
    const [knowledge, skillIds, mcpIds, enableMemory] = await Promise.all([
      associations.getKnowledge(row.id),
      associations.listSkillIds(row.id),
      associations.listMcpIds(row.id),
      associations.isMemoryEnabled(row.id),
    ]);
    return {
      ...this.summary(row),
      builtIn: isBuiltInAgent(row.name),
      prompt: row.prompt ?? null,
      extra: row.extra ?? null,
      knowledge,
      skillIds,
      mcpIds,
      enableMemory,
      publicReadable: row.scope.visibility === "public",
    };
  }

  async get(actor: ActorContext, id: string) {
    return this.detail(await this.require(actor, id));
  }

  async list(actor: ActorContext, query: { page: number; pageSize: number }) {
    const { page, pageSize } = query;
    const result = await this.deps.module.facade.list(actor, { limit: pageSize, offset: (page - 1) * pageSize });
    const items = await Promise.all(
      result.items.map(async (row) => ({
        ...this.summary(row),
        knowledgeBaseCount: (await this.deps.module.associations.listKnowledgeBindings(row.id)).length,
      })),
    );
    return { items, total: result.total, page, pageSize };
  }

  private async validate(actor: ActorContext, organizationId: string, input: Record<string, unknown>) {
    const error = validateAgentData(input);
    if (error) throw new ValidationError(error);
    try {
      await this.deps.authorizeAgentBindings(actor, organizationId, input, input.modelId as string | null | undefined);
    } catch (error) {
      if (error instanceof AppError && error.statusCode === 404) throw new ValidationError("绑定资源不存在或不可访问");
      throw error;
    }
  }

  private async save(command: AgentConfigSaveCommand<AuthorizedAgentConfig>) {
    try {
      return await this.deps.saveAgentConfig(command);
    } catch (error) {
      if (error instanceof InvalidKnowledgeBindingError)
        throw new AppError("知识库不存在或不可访问", "INVALID_KNOWLEDGE_BINDINGS", 400);
      throw error;
    }
  }

  async create(actor: ActorContext, input: Record<string, unknown>) {
    if (!isValidAgentName(input.name as string)) throw new ValidationError("Invalid agent name");
    const organizationId = actor.activeOrganizationId;
    if (!organizationId) throw new AppError("Organization context required", "UNAUTHORIZED", 401);
    await this.validate(actor, organizationId, input);
    const row = await this.save({
      organizationId,
      write: () =>
        this.deps.module.facade.create(actor, {
          name: input.name,
          data: toAgentConfigWriteData(input),
          rejectConflict: true,
          publicReadable: input.publicReadable,
        }),
      bindings: input,
      enableMemory: input.enableMemory as boolean | undefined,
      associations: this.deps.module.associations,
    });
    return this.detail(row);
  }

  async patch(actor: ActorContext, id: string, input: Record<string, unknown>) {
    const current = await this.require(actor, id);
    if (!current.access.actions.includes("update")) throw new ForbiddenError("Agent is read-only");
    const organizationId = current.scope.organizationId;
    if (!organizationId) throw new Error("Agent organization missing");
    await this.validate(actor, organizationId, input);
    const row = await this.save({
      organizationId,
      resourceId: id,
      write: () =>
        this.deps.module.facade.updateById(actor, id, toAgentConfigWriteData(input), {
          publicReadable: input.publicReadable,
        }),
      bindings: input,
      enableMemory: input.enableMemory as boolean | undefined,
      associations: this.deps.module.associations,
    });
    return this.detail(row);
  }

  async remove(actor: ActorContext, id: string) {
    await this.deps.module.facade.removeById(actor, id);
    return null;
  }
}

// ── 辅助 ──

const actor: ActorContext = { organizationId: "org-1", userId: "user-1", activeOrganizationId: "org-1" };

function row(overrides: Partial<AuthorizedAgentConfig> = {}): AuthorizedAgentConfig {
  return {
    id: "agent-1",
    name: "my-agent",
    description: "demo",
    modelId: "model-1",
    machineId: null,
    prompt: "hi",
    extra: { temperature: 0.5 },
    scope: { organizationId: "org-1", visibility: "private" },
    access: { actions: ["read", "update", "delete"] },
    ...overrides,
  };
}

function makeDeps(overrides: Partial<FacadeDeps> = {}, moduleOverrides: Partial<AgentConfigServerModule["facade"]> = {}) {
  const module: AgentConfigServerModule = {
    facade: {
      getById: mock(async () => row()),
      list: mock(async () => ({ items: [row()], total: 1 })),
      create: mock(async () => row()),
      updateById: mock(async () => row()),
      removeById: mock(async () => {}),
      ...moduleOverrides,
    },
    associations: {
      getKnowledge: mock(async () => ({ knowledgeBaseId: "kb-1" })),
      listSkillIds: mock(async () => ["skill-1"]),
      listMcpIds: mock(async () => ["mcp-1"]),
      isMemoryEnabled: mock(async () => true),
      listKnowledgeBindings: mock(async () => [{ knowledgeBaseId: "kb-1" }]),
    },
  };
  const deps: FacadeDeps = {
    module,
    saveAgentConfig: mock(async (command) => command.write()),
    authorizeAgentBindings: mock(async () => {}),
    ...overrides,
  };
  return { deps, module };
}

// ── tests ──

describe("ApiV1AgentFacade", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("get / detail", () => {
    test("不存在时抛 404", async () => {
      const { deps } = makeDeps({}, { getById: mock(async () => null) });
      await expect(new ApiV1AgentFacade(deps).get(actor, "missing")).rejects.toMatchObject({
        code: "NOT_FOUND",
        statusCode: 404,
      });
    });

    test("汇总关联数据并派生 builtIn/publicReadable", async () => {
      const { deps } = makeDeps({}, {
        getById: mock(async () => row({ name: "assistant", scope: { organizationId: "org-1", visibility: "public" } })),
      });
      const detail = await new ApiV1AgentFacade(deps).get(actor, "agent-1");
      expect(detail).toMatchObject({
        id: "agent-1",
        builtIn: true,
        publicReadable: true,
        knowledge: { knowledgeBaseId: "kb-1" },
        skillIds: ["skill-1"],
        mcpIds: ["mcp-1"],
        enableMemory: true,
      });
    });

    test("可空字段补 null，machineId 参与 agentNode 推导", async () => {
      const { deps } = makeDeps({}, {
        getById: mock(async () =>
          row({ description: null, modelId: null, prompt: null, extra: null, machineId: "m-1", agentNode: undefined }),
        ),
      });
      const detail = await new ApiV1AgentFacade(deps).get(actor, "agent-1");
      expect(detail).toMatchObject({
        description: null,
        modelId: null,
        prompt: null,
        extra: null,
        agentNode: { kind: "machine", machineId: "m-1" },
      });
    });
  });

  describe("list", () => {
    test("换算分页并附加知识库绑定数", async () => {
      const { deps, module } = makeDeps();
      const result = await new ApiV1AgentFacade(deps).list(actor, { page: 3, pageSize: 10 });
      expect(module.facade.list).toHaveBeenCalledWith(actor, { limit: 10, offset: 20 });
      expect(result).toEqual({
        total: 1,
        page: 3,
        pageSize: 10,
        items: [expect.objectContaining({ id: "agent-1", knowledgeBaseCount: 1 })],
      });
    });
  });

  describe("create", () => {
    test("名称非法时抛 VALIDATION_ERROR", async () => {
      const { deps } = makeDeps();
      await expect(new ApiV1AgentFacade(deps).create(actor, { name: "-bad-" })).rejects.toMatchObject({
        code: "VALIDATION_ERROR",
      });
    });

    test("缺少活跃组织时抛 401 UNAUTHORIZED", async () => {
      const { deps } = makeDeps();
      await expect(
        new ApiV1AgentFacade(deps).create({ organizationId: "org-1", userId: "u" }, { name: "ok" }),
      ).rejects.toMatchObject({ code: "UNAUTHORIZED", statusCode: 401 });
    });

    test("字段校验失败时抛 VALIDATION_ERROR", async () => {
      const { deps } = makeDeps();
      await expect(new ApiV1AgentFacade(deps).create(actor, { name: "ok", temperature: 3 })).rejects.toMatchObject({
        code: "VALIDATION_ERROR",
      });
    });

    test("绑定资源 404 转为 VALIDATION_ERROR", async () => {
      const { deps } = makeDeps({
        authorizeAgentBindings: mock(async () => {
          throw new AppError("missing", "NOT_FOUND", 404);
        }),
      });
      await expect(new ApiV1AgentFacade(deps).create(actor, { name: "ok" })).rejects.toMatchObject({
        code: "VALIDATION_ERROR",
        message: "绑定资源不存在或不可访问",
      });
    });

    test("非 404 的绑定错误原样抛出", async () => {
      const { deps } = makeDeps({
        authorizeAgentBindings: mock(async () => {
          throw new ForbiddenError("denied");
        }),
      });
      await expect(new ApiV1AgentFacade(deps).create(actor, { name: "ok" })).rejects.toMatchObject({
        code: "FORBIDDEN",
      });
    });

    test("严格创建并写入显式绑定", async () => {
      const { deps, module } = makeDeps();
      const save = deps.saveAgentConfig as ReturnType<typeof mock>;
      const detail = await new ApiV1AgentFacade(deps).create(actor, {
        name: "ok",
        prompt: "p",
        knowledge: ["kb-1"],
        enableMemory: true,
        publicReadable: false,
      });
      expect(module.facade.create).toHaveBeenCalledWith(actor, {
        name: "ok",
        data: { prompt: "p" },
        rejectConflict: true,
        publicReadable: false,
      });
      expect(save).toHaveBeenCalledWith(
        expect.objectContaining({
          organizationId: "org-1",
          bindings: expect.objectContaining({ knowledge: ["kb-1"] }),
          enableMemory: true,
        }),
      );
      expect(detail.id).toBe("agent-1");
    });

    test("知识库竞态错误映射为 INVALID_KNOWLEDGE_BINDINGS 400", async () => {
      const { deps } = makeDeps({
        saveAgentConfig: mock(async () => {
          throw new InvalidKnowledgeBindingError("gone");
        }),
      });
      await expect(new ApiV1AgentFacade(deps).create(actor, { name: "ok" })).rejects.toMatchObject({
        code: "INVALID_KNOWLEDGE_BINDINGS",
        statusCode: 400,
      });
    });
  });

  describe("patch", () => {
    test("不存在时抛 404", async () => {
      const { deps } = makeDeps({}, { getById: mock(async () => null) });
      await expect(new ApiV1AgentFacade(deps).patch(actor, "missing", {})).rejects.toMatchObject({
        code: "NOT_FOUND",
      });
    });

    test("无 update 权限时抛 FORBIDDEN", async () => {
      const { deps } = makeDeps({}, { getById: mock(async () => row({ access: { actions: ["read"] } })) });
      await expect(new ApiV1AgentFacade(deps).patch(actor, "agent-1", {})).rejects.toMatchObject({
        code: "FORBIDDEN",
        statusCode: 403,
      });
    });

    test("资源缺少组织归属时抛错", async () => {
      const { deps } = makeDeps({}, {
        getById: mock(async () => row({ scope: { visibility: "private" } })),
      });
      await expect(new ApiV1AgentFacade(deps).patch(actor, "agent-1", {})).rejects.toThrow(
        "Agent organization missing",
      );
    });

    test("使用资源自身组织做绑定校验并更新", async () => {
      const { deps, module } = makeDeps({}, {
        getById: mock(async () => row({ scope: { organizationId: "org-9", visibility: "private" } })),
      });
      const authorize = deps.authorizeAgentBindings as ReturnType<typeof mock>;
      await new ApiV1AgentFacade(deps).patch(actor, "agent-1", { description: "new" });
      expect(authorize).toHaveBeenCalledWith(actor, "org-9", expect.objectContaining({ description: "new" }), undefined);
      expect(module.facade.updateById).toHaveBeenCalledWith(actor, "agent-1", { description: "new" }, {
        publicReadable: undefined,
      });
    });

    test("保存命令携带资源 ID 与绑定", async () => {
      const { deps } = makeDeps();
      const save = deps.saveAgentConfig as ReturnType<typeof mock>;
      await new ApiV1AgentFacade(deps).patch(actor, "agent-1", { skillIds: ["s-1"] });
      expect(save).toHaveBeenCalledWith(
        expect.objectContaining({ resourceId: "agent-1", bindings: expect.objectContaining({ skillIds: ["s-1"] }) }),
      );
    });
  });

  test("remove 委托删除并返回 null", async () => {
    const { deps, module } = makeDeps();
    expect(await new ApiV1AgentFacade(deps).remove(actor, "agent-1")).toBeNull();
    expect(module.facade.removeById).toHaveBeenCalledWith(actor, "agent-1");
  });
});
