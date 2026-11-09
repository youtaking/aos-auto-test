// api-v1-provider.test.ts — v1 供应商/模型对外投影测试
// 测试目标：apiProviderActor / apiProviderListItem / apiProviderDetail / apiProviderWrite / apiModelDetail
// 业务意图：确保对外响应不含凭证原文，只暴露 hasApiKey，且 PATCH 只复制显式字段
// 源：packages/resources/model-management/src/server/services/api-v1-provider.ts（main a7f477a9e）

import { describe, expect, test } from "bun:test";

// ── 复制纯函数 ──

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

interface ActorContext {
  organizationId: string;
  userId: string;
}

interface AuthorizedProvider {
  id: string;
  name: string;
  displayName?: string | null;
  kind: string;
  gatewayType?: string | null;
  protocol: string;
  baseUrl?: string | null;
  apiKey?: string | null;
  scope: string;
  access: string;
  extraOptions?: Record<string, unknown> | null;
}

interface AuthorizedProviderListItem extends AuthorizedProvider {
  modelCount: number;
}

interface AuthorizedModel {
  id: string;
  providerId: string;
  modelId: string;
  displayName?: string | null;
  modalities?: unknown;
  limitConfig?: unknown;
  cost?: unknown;
  options?: unknown;
}

interface AuthorizedProviderDetail extends AuthorizedProvider {
  models: AuthorizedModel[];
}

interface ApiProviderUpdateBody {
  displayName?: string;
  protocol?: string;
  baseUrl?: string;
  apiKey?: string;
  extraOptions?: Record<string, unknown>;
}

function apiProviderActor(store: { actor?: ActorContext | null }): ActorContext {
  if (!store.actor) throw new AppError("请求缺少组织上下文", "UNAUTHORIZED", 401);
  return store.actor;
}

function providerBase(row: AuthorizedProvider) {
  return {
    id: row.id,
    name: row.name,
    displayName: row.displayName ?? null,
    kind: row.kind,
    gatewayType: row.gatewayType ?? null,
    protocol: row.protocol,
    baseUrl: row.baseUrl ?? null,
    hasApiKey: Boolean(row.apiKey),
    scope: row.scope,
    access: row.access,
  };
}

function apiProviderListItem(row: AuthorizedProviderListItem) {
  return { ...providerBase(row), modelCount: row.modelCount };
}

function apiProviderDetail(row: AuthorizedProviderDetail) {
  return { ...providerBase(row), extraOptions: row.extraOptions ?? null };
}

function apiProviderWrite(body: ApiProviderUpdateBody) {
  return {
    ...(body.displayName === undefined ? {} : { displayName: body.displayName }),
    ...(body.protocol === undefined ? {} : { protocol: body.protocol }),
    ...(body.baseUrl === undefined ? {} : { baseUrl: body.baseUrl }),
    ...(body.apiKey === undefined ? {} : { apiKey: body.apiKey }),
    ...(body.extraOptions === undefined ? {} : { extraOptions: body.extraOptions }),
  };
}

function apiModelDetail(row: AuthorizedModel) {
  const options = row.options && typeof row.options === "object" && !Array.isArray(row.options) ? row.options : null;
  return {
    id: row.id,
    providerId: row.providerId,
    modelId: row.modelId,
    displayName: row.displayName ?? null,
    modalities: row.modalities ?? null,
    limitConfig: row.limitConfig ?? null,
    cost: row.cost ?? null,
    options,
  };
}

// ── 测试辅助 ──

function providerRow(overrides: Partial<AuthorizedProvider> = {}): AuthorizedProvider {
  return {
    id: "prov-1",
    name: "openai-main",
    displayName: "OpenAI",
    kind: "openai",
    gatewayType: "direct",
    protocol: "openai",
    baseUrl: "https://api.example.com",
    apiKey: "sk-secret",
    scope: "organization",
    access: "write",
    ...overrides,
  };
}

function modelRow(overrides: Partial<AuthorizedModel> = {}): AuthorizedModel {
  return {
    id: "model-uid-1",
    providerId: "prov-1",
    modelId: "gpt-5",
    displayName: "GPT-5",
    modalities: ["text"],
    limitConfig: { context: 200000 },
    cost: { input: 1, output: 2 },
    options: {},
    ...overrides,
  };
}

// ── tests ──

describe("api-v1-provider 对外投影", () => {
  describe("apiProviderActor", () => {
    test("缺少组织上下文时返回 401 UNAUTHORIZED", () => {
      expect(() => apiProviderActor({})).toThrow("请求缺少组织上下文");
      try {
        apiProviderActor({ actor: null });
      } catch (error) {
        expect(error).toMatchObject({ code: "UNAUTHORIZED", statusCode: 401 });
      }
    });

    test("存在 actor 时原样返回", () => {
      const actor = { organizationId: "org-1", userId: "user-1" };
      expect(apiProviderActor({ actor })).toBe(actor);
    });
  });

  describe("providerBase 投影", () => {
    test("不暴露 apiKey 原文，只暴露 hasApiKey=true", () => {
      const projected = apiProviderListItem({ ...providerRow(), modelCount: 2 });
      expect(projected).not.toHaveProperty("apiKey");
      expect(projected.hasApiKey).toBe(true);
    });

    test("无凭证时 hasApiKey=false", () => {
      expect(apiProviderListItem({ ...providerRow({ apiKey: null }), modelCount: 0 }).hasApiKey).toBe(false);
    });

    test("可空字段统一输出 null", () => {
      const projected = apiProviderDetail({
        ...providerRow({ displayName: undefined, gatewayType: undefined, baseUrl: undefined }),
        models: [],
      });
      expect(projected.displayName).toBeNull();
      expect(projected.gatewayType).toBeNull();
      expect(projected.baseUrl).toBeNull();
    });
  });

  describe("apiProviderListItem", () => {
    test("附带授权模型数量", () => {
      expect(apiProviderListItem({ ...providerRow(), modelCount: 7 })).toMatchObject({
        id: "prov-1",
        name: "openai-main",
        modelCount: 7,
      });
    });
  });

  describe("apiProviderDetail", () => {
    test("不内嵌模型列表", () => {
      const projected = apiProviderDetail({ ...providerRow(), models: [modelRow()] });
      expect(projected).not.toHaveProperty("models");
    });

    test("extraOptions 缺省为 null", () => {
      expect(apiProviderDetail({ ...providerRow(), models: [] }).extraOptions).toBeNull();
    });

    test("extraOptions 原样透出", () => {
      const extraOptions = { timeoutMs: 30000 };
      expect(apiProviderDetail({ ...providerRow({ extraOptions }), models: [] }).extraOptions).toEqual(extraOptions);
    });
  });

  describe("apiProviderWrite", () => {
    test("空对象不复制任何字段", () => {
      expect(apiProviderWrite({})).toEqual({});
    });

    test("只复制显式提供的字段", () => {
      expect(apiProviderWrite({ displayName: "New", apiKey: "sk-new" })).toEqual({
        displayName: "New",
        apiKey: "sk-new",
      });
    });

    test("显式 null/空串仍被复制（允许清空）", () => {
      expect(apiProviderWrite({ baseUrl: "", displayName: "" })).toEqual({ baseUrl: "", displayName: "" });
    });

    test("未知字段不会被复制", () => {
      const body = { displayName: "x", scope: "public" } as unknown as ApiProviderUpdateBody;
      expect(apiProviderWrite(body)).toEqual({ displayName: "x" });
    });
  });

  describe("apiModelDetail", () => {
    test("数据库 id 与上游 modelId 分开暴露", () => {
      const projected = apiModelDetail(modelRow());
      expect(projected.id).toBe("model-uid-1");
      expect(projected.modelId).toBe("gpt-5");
      expect(projected.providerId).toBe("prov-1");
    });

    test("options 只接受普通对象", () => {
      expect(apiModelDetail(modelRow({ options: { temperature: 0.2 } })).options).toEqual({ temperature: 0.2 });
      expect(apiModelDetail(modelRow({ options: ["a"] })).options).toBeNull();
      expect(apiModelDetail(modelRow({ options: "text" })).options).toBeNull();
      expect(apiModelDetail(modelRow({ options: null })).options).toBeNull();
    });

    test("可空字段缺省为 null", () => {
      const projected = apiModelDetail(
        modelRow({ displayName: undefined, modalities: undefined, limitConfig: undefined, cost: undefined }),
      );
      expect(projected.displayName).toBeNull();
      expect(projected.modalities).toBeNull();
      expect(projected.limitConfig).toBeNull();
      expect(projected.cost).toBeNull();
    });
  });
});
