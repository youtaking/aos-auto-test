// api-v1-mcp.test.ts — v1 MCP 对外投影与服务编排测试
// 测试目标：toApiMcp 脱敏投影、ApiV1McpService 的 get/list/create/patch/remove
// 业务意图：确保对外响应永不泄露凭据，PATCH 的启用/改配置/改可见范围三条分支正确分流
// 源：packages/resources/mcp/src/server/services/api-v1-mcp.ts（main a7f477a9e）

import { beforeEach, describe, expect, mock, test } from "bun:test";

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

function parseMcpConfigValue(value: unknown): Record<string, unknown> | null {
  if (value == null) return null;
  if (typeof value !== "string") return value as Record<string, unknown>;
  try {
    const parsed: unknown = JSON.parse(value);
    if (typeof parsed === "string") {
      const nested: unknown = JSON.parse(parsed);
      return typeof nested === "object" && nested !== null ? (nested as Record<string, unknown>) : null;
    }
    return typeof parsed === "object" && parsed !== null ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function validateMcpConfig(config: unknown): string | null {
  if (typeof config !== "object" || config === null) return "INVALID_CONFIG";
  const cfg = config as Record<string, unknown>;

  if ("enabled" in cfg && cfg.enabled === false && Object.keys(cfg).length === 1) return null;

  if (!("type" in cfg) || typeof cfg.type !== "string") return "INVALID_CONFIG_TYPE";
  const type = cfg.type as string;

  if (type === "local") {
    if (
      !Array.isArray(cfg.command) ||
      cfg.command.length === 0 ||
      cfg.command.some((c: unknown) => typeof c !== "string")
    ) {
      return "INVALID_COMMAND";
    }
    if (cfg.environment !== undefined && (typeof cfg.environment !== "object" || cfg.environment === null)) {
      return "INVALID_ENVIRONMENT";
    }
    if (cfg.timeout !== undefined && (typeof cfg.timeout !== "number" || cfg.timeout <= 0)) {
      return "INVALID_TIMEOUT";
    }
  } else if (type === "remote" || type === "streamable-http") {
    if (typeof cfg.url !== "string" || cfg.url.length === 0) return "INVALID_URL";
    if (cfg.headers !== undefined && (typeof cfg.headers !== "object" || cfg.headers === null)) {
      return "INVALID_HEADERS";
    }
    if (cfg.timeout !== undefined && (typeof cfg.timeout !== "number" || cfg.timeout <= 0)) {
      return "INVALID_TIMEOUT";
    }
  } else {
    return "INVALID_CONFIG_TYPE";
  }
  return null;
}

function publicUrl(value: unknown): URL | undefined {
  if (typeof value !== "string") return;
  const url = URL.parse(value);
  if (!url || !["https:", "http:"].includes(url.protocol)) return;
  url.username = "";
  url.password = "";
  url.search = "";
  url.hash = "";
  return url;
}

interface ActorContext {
  organizationId: string;
  userId: string;
}

interface AuthorizedMcpServer {
  id: string;
  name: string;
  enabled?: boolean;
  config: unknown;
  toolsCount?: number;
  scope: { organizationId?: string; ownerUserId?: string; visibility: "public" | "private" };
  access: { actions: string[] };
}

function toApiMcp(server: AuthorizedMcpServer, toolsCount = 0) {
  const raw = parseMcpConfigValue(server.config) ?? {};
  const type = raw.type === "remote" || raw.type === "streamable-http" ? raw.type : "local";
  const oauth = raw.oauth && typeof raw.oauth === "object" ? (raw.oauth as Record<string, unknown>) : undefined;
  const url = publicUrl(raw.url);
  const summary =
    typeof raw.url === "string" ? (url?.origin ?? "") : Array.isArray(raw.command) ? String(raw.command[0] ?? "") : "";
  const config: Record<string, unknown> = { type, enabled: server.enabled ?? true };
  for (const key of ["command", "timeout"]) if (raw[key] !== undefined) config[key] = raw[key];
  if (url) config.url = url.toString();
  if (oauth) {
    config.oauth = Object.fromEntries(
      ["clientId", "scope"].filter((key) => typeof oauth[key] === "string").map((key) => [key, oauth[key]]),
    );
    const redirect = publicUrl(oauth.redirectUri);
    if (redirect) (config.oauth as Record<string, unknown>).redirectUri = redirect.toString();
  } else if (raw.oauth === false) config.oauth = false;
  return {
    id: server.id,
    name: server.name,
    type,
    enabled: server.enabled ?? true,
    summary,
    toolsCount,
    scope: server.scope,
    access: server.access,
    config,
    headerNames: Object.keys((raw.headers ?? {}) as object),
    environmentNames: Object.keys((raw.environment ?? {}) as object),
    hasClientSecret: typeof oauth?.clientSecret === "string" && oauth.clientSecret.length > 0,
  };
}

interface McpFacade {
  getById(actor: ActorContext, id: string): Promise<AuthorizedMcpServer | null>;
  getWritableById(actor: ActorContext, id: string): Promise<AuthorizedMcpServer>;
  list(
    actor: ActorContext,
    query: { limit: number; offset: number },
  ): Promise<{ items: AuthorizedMcpServer[]; total: number }>;
  create(actor: ActorContext, input: Record<string, unknown>): Promise<string>;
  updateById(
    actor: ActorContext,
    id: string,
    config: Record<string, unknown>,
    options: { publicReadable?: boolean },
  ): Promise<void>;
  setEnabledById(actor: ActorContext, id: string, enabled: boolean): Promise<void>;
  removeById(actor: ActorContext, id: string): Promise<void>;
}

class ApiV1McpService {
  constructor(private readonly facade: McpFacade) {}
  async get(actor: ActorContext, id: string) {
    const row = await this.facade.getById(actor, id);
    if (!row) throw new NotFoundError("MCP not found");
    return toApiMcp(row);
  }
  async list(actor: ActorContext, query: { page: number; pageSize: number }) {
    const result = await this.facade.list(actor, { limit: query.pageSize, offset: (query.page - 1) * query.pageSize });
    return {
      ...query,
      total: result.total,
      items: result.items.map((row) => {
        const { config, headerNames, environmentNames, hasClientSecret, ...item } = toApiMcp(row, row.toolsCount);
        return item;
      }),
    };
  }
  async create(actor: ActorContext, input: { name: string; config: Record<string, unknown>; publicReadable?: boolean }) {
    const id = await this.facade.create(actor, {
      name: input.name,
      type: input.config.type,
      config: input.config,
      publicReadable: input.publicReadable,
    });
    return this.get(actor, id);
  }
  async patch(
    actor: ActorContext,
    id: string,
    input: { enabled?: boolean; config?: Record<string, unknown>; publicReadable?: boolean },
  ) {
    if ("enabled" in input) {
      if (input.enabled) {
        const row = await this.facade.getWritableById(actor, id);
        const cfg = parseMcpConfigValue(row.config);
        if (!cfg || validateMcpConfig({ ...cfg, enabled: true }))
          throw new ValidationError("Complete connection configuration required");
      }
      await this.facade.setEnabledById(actor, id, input.enabled!);
    } else if ("config" in input)
      await this.facade.updateById(actor, id, input.config!, { publicReadable: input.publicReadable });
    else {
      const row = await this.facade.getWritableById(actor, id);
      await this.facade.updateById(actor, id, row.config as Record<string, unknown>, {
        publicReadable: input.publicReadable,
      });
    }
    return this.get(actor, id);
  }
  async remove(actor: ActorContext, id: string) {
    await this.facade.removeById(actor, id);
    return null;
  }
}

// ── 辅助 ──

const actor: ActorContext = { organizationId: "org-1", userId: "user-1" };

function server(overrides: Partial<AuthorizedMcpServer> = {}): AuthorizedMcpServer {
  return {
    id: "mcp-1",
    name: "demo",
    enabled: true,
    config: { type: "local", command: ["npx", "-y", "demo"] },
    scope: { organizationId: "org-1", visibility: "private" },
    access: { actions: ["read", "update", "delete"] },
    ...overrides,
  };
}

function facade(overrides: Partial<McpFacade> = {}): McpFacade {
  return {
    getById: mock(async () => server()),
    getWritableById: mock(async () => server()),
    list: mock(async () => ({ items: [server()], total: 1 })),
    create: mock(async () => "mcp-1"),
    updateById: mock(async () => {}),
    setEnabledById: mock(async () => {}),
    removeById: mock(async () => {}),
    ...overrides,
  };
}

// ── tests ──

describe("api-v1-mcp toApiMcp 投影", () => {
  test("local 配置：summary 取命令首项，保留 command/timeout", () => {
    const result = toApiMcp(
      server({ config: { type: "local", command: ["npx", "demo"], timeout: 30, environment: { A: "1" } } }),
      5,
    );
    expect(result.type).toBe("local");
    expect(result.summary).toBe("npx");
    expect(result.config).toEqual({ type: "local", enabled: true, command: ["npx", "demo"], timeout: 30 });
    expect(result.environmentNames).toEqual(["A"]);
    expect(result.headerNames).toEqual([]);
    expect(result.toolsCount).toBe(5);
  });

  test("remote 配置：URL 去除凭据/查询/片段，summary 为 origin", () => {
    const result = toApiMcp(
      server({
        config: {
          type: "remote",
          url: "https://user:pw@example.com/mcp?token=abc#x",
          headers: { Authorization: "Bearer x", "X-Trace": "1" },
        },
      }),
    );
    expect(result.type).toBe("remote");
    expect(result.summary).toBe("https://example.com");
    expect(result.config.url).toBe("https://example.com/mcp");
    expect(result.headerNames).toEqual(["Authorization", "X-Trace"]);
  });

  test("OAuth 只投影 clientId/scope/清洗后的 redirectUri，不泄露 clientSecret", () => {
    const result = toApiMcp(
      server({
        config: {
          type: "remote",
          url: "https://example.com/mcp",
          oauth: {
            clientId: "cid",
            clientSecret: "super-secret",
            scope: "read",
            redirectUri: "https://app.example.com/cb?code=1#frag",
          },
        },
      }),
    );
    expect(result.config.oauth).toEqual({
      clientId: "cid",
      scope: "read",
      redirectUri: "https://app.example.com/cb",
    });
    expect(result.hasClientSecret).toBe(true);
    expect(JSON.stringify(result)).not.toContain("super-secret");
  });

  test("oauth=false 保留为 false", () => {
    const result = toApiMcp(server({ config: { type: "remote", url: "https://e.com", oauth: false } }));
    expect(result.config.oauth).toBe(false);
    expect(result.hasClientSecret).toBe(false);
  });

  test("clientSecret 为空串时 hasClientSecret 为 false", () => {
    const result = toApiMcp(
      server({ config: { type: "remote", url: "https://e.com", oauth: { clientId: "c", clientSecret: "" } } }),
    );
    expect(result.hasClientSecret).toBe(false);
  });

  test("非 http(s) 的 url 不进入配置，summary 为空串", () => {
    const result = toApiMcp(server({ config: { type: "remote", url: "ws://example.com/socket" } }));
    expect(result.type).toBe("remote");
    expect(result.summary).toBe("");
    expect(result.config.url).toBeUndefined();
  });

  test("非法 URL 字符串不抛错", () => {
    const result = toApiMcp(server({ config: { type: "remote", url: "not a url" } }));
    expect(result.summary).toBe("");
  });

  test("未知 type 归入 local", () => {
    const result = toApiMcp(server({ config: { type: "legacy", command: ["x"] } }));
    expect(result.type).toBe("local");
  });

  test("配置为 JSON 字符串或双重编码字符串时可解析", () => {
    expect(toApiMcp(server({ config: JSON.stringify({ type: "local", command: ["a"] }) })).summary).toBe("a");
    expect(
      toApiMcp(server({ config: JSON.stringify(JSON.stringify({ type: "local", command: ["b"] })) })).summary,
    ).toBe("b");
  });

  test("配置不可解析时按空对象处理", () => {
    const result = toApiMcp(server({ config: "{{{" }));
    expect(result.type).toBe("local");
    expect(result.summary).toBe("");
  });

  test("enabled 缺省为 true", () => {
    const result = toApiMcp(server({ enabled: undefined, config: { type: "local", command: ["a"] } }));
    expect(result.enabled).toBe(true);
    expect(result.config.enabled).toBe(true);
  });
});

describe("ApiV1McpService", () => {
  beforeEach(() => {
    mock.restore();
  });

  test("get 不存在时抛 404", async () => {
    const service = new ApiV1McpService(facade({ getById: mock(async () => null) }));
    await expect(service.get(actor, "missing")).rejects.toMatchObject({ code: "NOT_FOUND", statusCode: 404 });
  });

  test("get 返回脱敏详情", async () => {
    const service = new ApiV1McpService(facade());
    const detail = await service.get(actor, "mcp-1");
    expect(detail).toMatchObject({ id: "mcp-1", name: "demo", summary: "npx" });
    expect(detail).toHaveProperty("config");
    expect(detail).toHaveProperty("hasClientSecret");
  });

  test("list 换算分页并剥掉详情字段", async () => {
    const list = mock(async () => ({ items: [server({ toolsCount: 3 })], total: 1 }));
    const service = new ApiV1McpService(facade({ list }));
    const result = await service.list(actor, { page: 3, pageSize: 10 });
    expect(list).toHaveBeenCalledWith(actor, { limit: 10, offset: 20 });
    expect(result).toEqual({
      page: 3,
      pageSize: 10,
      total: 1,
      items: [expect.objectContaining({ id: "mcp-1", toolsCount: 3 })],
    });
    expect(result.items[0]).not.toHaveProperty("config");
    expect(result.items[0]).not.toHaveProperty("headerNames");
    expect(result.items[0]).not.toHaveProperty("hasClientSecret");
  });

  test("create 映射 name/type/config 并返回详情", async () => {
    const create = mock(async () => "mcp-1");
    const service = new ApiV1McpService(facade({ create }));
    const result = await service.create(actor, {
      name: "demo",
      config: { type: "local", command: ["npx"] },
      publicReadable: true,
    });
    expect(create).toHaveBeenCalledWith(actor, {
      name: "demo",
      type: "local",
      config: { type: "local", command: ["npx"] },
      publicReadable: true,
    });
    expect(result.id).toBe("mcp-1");
  });

  test("patch 启用配置不完整时抛 VALIDATION_ERROR", async () => {
    const facadeStub = facade({
      getWritableById: mock(async () => server({ config: { type: "local" } })),
    });
    const service = new ApiV1McpService(facadeStub);
    await expect(service.patch(actor, "mcp-1", { enabled: true })).rejects.toMatchObject({
      code: "VALIDATION_ERROR",
      statusCode: 400,
    });
    expect(facadeStub.setEnabledById).toHaveBeenCalledTimes(0);
  });

  test("patch 启用且配置完整时走 setEnabledById", async () => {
    const facadeStub = facade();
    const service = new ApiV1McpService(facadeStub);
    await service.patch(actor, "mcp-1", { enabled: true });
    expect(facadeStub.setEnabledById).toHaveBeenCalledWith(actor, "mcp-1", true);
    expect(facadeStub.updateById).toHaveBeenCalledTimes(0);
  });

  test("patch 停用不校验配置", async () => {
    const facadeStub = facade({
      getWritableById: mock(async () => server({ config: { type: "local" } })),
    });
    const service = new ApiV1McpService(facadeStub);
    await service.patch(actor, "mcp-1", { enabled: false });
    expect(facadeStub.setEnabledById).toHaveBeenCalledWith(actor, "mcp-1", false);
    expect(facadeStub.getWritableById).toHaveBeenCalledTimes(0);
  });

  test("patch 带 config 时走 updateById 并透传 publicReadable", async () => {
    const facadeStub = facade();
    const service = new ApiV1McpService(facadeStub);
    const config = { type: "remote", url: "https://e.com" };
    await service.patch(actor, "mcp-1", { config, publicReadable: false });
    expect(facadeStub.updateById).toHaveBeenCalledWith(actor, "mcp-1", config, { publicReadable: false });
    expect(facadeStub.setEnabledById).toHaveBeenCalledTimes(0);
  });

  test("patch 仅 publicReadable 时复用现有配置", async () => {
    const facadeStub = facade({
      getWritableById: mock(async () => server({ config: { type: "local", command: ["x"] } })),
    });
    const service = new ApiV1McpService(facadeStub);
    await service.patch(actor, "mcp-1", { publicReadable: true });
    expect(facadeStub.updateById).toHaveBeenCalledWith(
      actor,
      "mcp-1",
      { type: "local", command: ["x"] },
      { publicReadable: true },
    );
  });

  test("remove 返回 null", async () => {
    const facadeStub = facade();
    const service = new ApiV1McpService(facadeStub);
    expect(await service.remove(actor, "mcp-1")).toBeNull();
    expect(facadeStub.removeById).toHaveBeenCalledWith(actor, "mcp-1");
  });
});
