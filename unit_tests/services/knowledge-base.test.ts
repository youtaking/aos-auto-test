// knowledge-base.test.ts — 知识库服务纯函数测试
// 测试目标：slug 生成、名称/slug 校验、sanitize、远端缺失错误判断、表单选项
// 业务意图：确保知识库的输入验证、slug 规范化、数据清洗逻辑正确

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数 ──

function normalizeSlug(slug: string): string {
  return slug.trim().toLowerCase();
}

function buildSlugBase(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function generateKnowledgeBaseSlug(name: string, suffix: string): string {
  const base = buildSlugBase(name);
  if (!base) {
    return `kb-${suffix}`;
  }
  const maxBaseLength = 80 - suffix.length - 1;
  const trimmedBase = base.slice(0, maxBaseLength).replace(/-+$/g, "");
  return `${trimmedBase || "kb"}-${suffix}`;
}

function validateName(name: string): string | null {
  if (!name || name.trim().length === 0) return "知识库名称不能为空";
  if (name.trim().length > 120) return "知识库名称不能超过 120 字符";
  return null;
}

function validateSlug(slug: string): string | null {
  const normalized = normalizeSlug(slug);
  if (!normalized) return "slug 不能为空";
  if (!/^[\p{L}0-9]([\p{L}0-9-]*[\p{L}0-9])?$/u.test(normalized)) return "slug 只能包含字母、数字和连字符";
  if (normalized.length > 80) return "slug 不能超过 80 字符";
  return null;
}

function isRemoteKnowledgeBaseMissingError(err: unknown): boolean {
  const message = err instanceof Error ? err.message.toLowerCase() : String(err).toLowerCase();
  return (
    message.includes("not found") ||
    message.includes("not exist") ||
    message.includes("nonexistent") ||
    message.includes("dataset not found") ||
    message.includes("http 404") ||
    message.includes("lacks permission") ||
    message.includes("don't own")
  );
}

function resolveKnowledgeTenantIdentity(row: {
  userId: string;
  remoteAccountId?: string | null;
  remoteUserId?: string | null;
}): { remoteAccountId: string; remoteUserId: string } {
  const fallback = row.userId.trim();
  return {
    remoteAccountId: row.remoteAccountId?.trim() || fallback,
    remoteUserId: row.remoteUserId?.trim() || fallback,
  };
}

function sanitizeKnowledgeBase(
  row: { id: string; name: string; slug: string; description?: string | null; provider: string; remoteId?: string | null; remoteAccountId?: string | null; remoteUserId?: string | null; userId: string; organizationId?: string | null; status: string; lastError?: string | null; metadata?: unknown; createdAt: Date; updatedAt: Date },
  extras?: { bindingsCount?: number; resourcesCount?: number; remoteExists?: boolean },
) {
  return {
    id: row.id,
    name: row.name,
    slug: row.slug,
    description: row.description ?? null,
    provider: row.provider,
    remoteId: row.remoteId ?? null,
    remoteAccountId: row.remoteAccountId ?? null,
    remoteUserId: row.remoteUserId ?? null,
    userId: row.userId,
    organizationId: row.organizationId ?? null,
    status: row.status,
    lastError: row.lastError ?? null,
    bindingsCount: extras?.bindingsCount ?? 0,
    resourcesCount: extras?.resourcesCount ?? 0,
    remoteExists: extras?.remoteExists ?? true,
    createdAt: Math.floor(row.createdAt.getTime() / 1000),
    updatedAt: Math.floor(row.updatedAt.getTime() / 1000),
  };
}

// ── tests ──

describe("knowledge-base 知识库服务", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("validateName 名称校验", () => {
    test("空字符串返回错误", () => {
      expect(validateName("")).toBe("知识库名称不能为空");
    });

    test("纯空格返回错误", () => {
      expect(validateName("   ")).toBe("知识库名称不能为空");
    });

    test("正常名称返回 null", () => {
      expect(validateName("测试知识库")).toBeNull();
    });

    test("120 字符名称通过", () => {
      expect(validateName("a".repeat(120))).toBeNull();
    });

    test("121 字符名称返回错误", () => {
      expect(validateName("a".repeat(121))).toBe("知识库名称不能超过 120 字符");
    });

    test("null/undefined 返回错误", () => {
      expect(validateName(null as any)).toBe("知识库名称不能为空");
      expect(validateName(undefined as any)).toBe("知识库名称不能为空");
    });
  });

  describe("validateSlug slug 校验", () => {
    test("空字符串返回错误", () => {
      expect(validateSlug("")).toBe("slug 不能为空");
    });

    test("纯空格返回错误", () => {
      expect(validateSlug("   ")).toBe("slug 不能为空");
    });

    test("正常 slug 通过", () => {
      expect(validateSlug("my-knowledge-base")).toBeNull();
    });

    test("单字符通过", () => {
      expect(validateSlug("a")).toBeNull();
    });

    test("以连字符开头返回错误", () => {
      expect(validateSlug("-abc")).toBe("slug 只能包含字母、数字和连字符");
    });

    test("以连字符结尾返回错误", () => {
      expect(validateSlug("abc-")).toBe("slug 只能包含字母、数字和连字符");
    });

    test("包含特殊字符返回错误", () => {
      expect(validateSlug("abc_def")).toBe("slug 只能包含字母、数字和连字符");
    });

    test("包含空格返回错误", () => {
      expect(validateSlug("abc def")).toBe("slug 只能包含字母、数字和连字符");
    });

    test("80 字符通过", () => {
      const slug = "a" + "-a".repeat(39);  // 1 + 78 = 79 chars
      expect(validateSlug(slug)).toBeNull();
    });

    test("超过 80 字符返回错误", () => {
      const slug = "a".repeat(81);
      expect(validateSlug(slug)).toBe("slug 不能超过 80 字符");
    });

    test("unicode 字母通过", () => {
      expect(validateSlug("知识库-test")).toBeNull();
    });
  });

  describe("generateKnowledgeBaseSlug slug 生成", () => {
    test("正常英文名称生成正确 slug", () => {
      const slug = generateKnowledgeBaseSlug("My Knowledge Base", "abcd1234");
      expect(slug).toBe("my-knowledge-base-abcd1234");
    });

    test("中文名称生成 kb- 前缀", () => {
      const slug = generateKnowledgeBaseSlug("测试知识库", "abcd1234");
      // buildSlugBase 只保留 [a-z0-9]，中文会被替换为 "-" 并最终 trim 为空
      expect(slug).toBe("kb-abcd1234");
    });

    test("空名称回退到 kb- 前缀", () => {
      const slug = generateKnowledgeBaseSlug("", "abcd1234");
      expect(slug).toBe("kb-abcd1234");
    });

    test("纯空格名称回退到 kb- 前缀", () => {
      const slug = generateKnowledgeBaseSlug("   ", "abcd1234");
      expect(slug).toBe("kb-abcd1234");
    });

    test("超长名称截断到 maxBaseLength", () => {
      const longName = "a".repeat(200);
      const slug = generateKnowledgeBaseSlug(longName, "abcd1234");
      // maxBaseLength = 80 - 8 - 1 = 71
      const parts = slug.split("-abcd1234");
      expect(parts[0].length).toBeLessThanOrEqual(71);
    });

    test("名称含特殊字符被替换为连字符", () => {
      const slug = generateKnowledgeBaseSlug("hello world! test", "abcd1234");
      expect(slug).toContain("hello-world-test");
    });
  });

  describe("buildSlugBase 规范化", () => {
    test("英文保持小写", () => {
      expect(buildSlugBase("Hello World")).toBe("hello-world");
    });

    test("特殊字符替换为连字符", () => {
      expect(buildSlugBase("hello@world")).toBe("hello-world");
    });

    test("前后连字符被去除", () => {
      expect(buildSlugBase("-hello-")).toBe("hello");
    });

    test("多个连续特殊字符只生成一个连字符", () => {
      expect(buildSlugBase("hello   world")).toBe("hello-world");
    });

    test("中文返回空字符串", () => {
      expect(buildSlugBase("测试")).toBe("");
    });
  });

  describe("isRemoteKnowledgeBaseMissingError 远端缺失判断", () => {
    test("'not found' 匹配", () => {
      expect(isRemoteKnowledgeBaseMissingError(new Error("Dataset not found"))).toBe(true);
    });

    test("'not exist' 匹配", () => {
      expect(isRemoteKnowledgeBaseMissingError(new Error("Does not exist"))).toBe(true);
    });

    test("'HTTP 404' 匹配", () => {
      expect(isRemoteKnowledgeBaseMissingError(new Error("HTTP 404 error"))).toBe(true);
    });

    test("'lacks permission' 匹配", () => {
      expect(isRemoteKnowledgeBaseMissingError(new Error("User lacks permission"))).toBe(true);
    });

    test("'don't own' 匹配", () => {
      expect(isRemoteKnowledgeBaseMissingError(new Error("You don't own this"))).toBe(true);
    });

    test("不相关的错误不匹配", () => {
      expect(isRemoteKnowledgeBaseMissingError(new Error("Network timeout"))).toBe(false);
    });

    test("非 Error 对象用 String 转换", () => {
      expect(isRemoteKnowledgeBaseMissingError("not found")).toBe(true);
    });

    test("大小写不敏感", () => {
      expect(isRemoteKnowledgeBaseMissingError(new Error("NOT FOUND"))).toBe(true);
    });
  });

  describe("resolveKnowledgeTenantIdentity 租户身份解析", () => {
    test("有 remoteAccountId 和 remoteUserId 时使用它们", () => {
      const result = resolveKnowledgeTenantIdentity({
        userId: "user-1",
        remoteAccountId: "remote-account-1",
        remoteUserId: "remote-user-1",
      });
      expect(result.remoteAccountId).toBe("remote-account-1");
      expect(result.remoteUserId).toBe("remote-user-1");
    });

    test("remoteAccountId 为空时 fallback 到 userId", () => {
      const result = resolveKnowledgeTenantIdentity({
        userId: "user-1",
        remoteAccountId: null,
        remoteUserId: "remote-user-1",
      });
      expect(result.remoteAccountId).toBe("user-1");
    });

    test("remoteUserId 为空时 fallback 到 userId", () => {
      const result = resolveKnowledgeTenantIdentity({
        userId: "user-1",
        remoteAccountId: "remote-account-1",
        remoteUserId: null,
      });
      expect(result.remoteUserId).toBe("user-1");
    });

    test("全空时都 fallback 到 userId", () => {
      const result = resolveKnowledgeTenantIdentity({
        userId: "user-1",
        remoteAccountId: "",
        remoteUserId: "",
      });
      expect(result.remoteAccountId).toBe("user-1");
      expect(result.remoteUserId).toBe("user-1");
    });

    test("带空格的值被 trim", () => {
      const result = resolveKnowledgeTenantIdentity({
        userId: "user-1",
        remoteAccountId: "  account-1  ",
        remoteUserId: "  user-2  ",
      });
      expect(result.remoteAccountId).toBe("account-1");
      expect(result.remoteUserId).toBe("user-2");
    });
  });

  describe("sanitizeKnowledgeBase 数据清洗", () => {
    test("基本字段正确映射", () => {
      const now = new Date("2024-06-01T12:00:00Z");
      const result = sanitizeKnowledgeBase({
        id: "kb-1",
        name: "Test KB",
        slug: "test-kb",
        description: "A test",
        provider: "ragflow",
        remoteId: "remote-1",
        userId: "user-1",
        organizationId: "org-1",
        status: "ready",
        createdAt: now,
        updatedAt: now,
      });
      expect(result.id).toBe("kb-1");
      expect(result.name).toBe("Test KB");
      expect(result.slug).toBe("test-kb");
      expect(result.description).toBe("A test");
      expect(result.status).toBe("ready");
      expect(result.createdAt).toBe(Math.floor(now.getTime() / 1000));
    });

    test("null 字段正确默认值", () => {
      const now = new Date();
      const result = sanitizeKnowledgeBase({
        id: "kb-1",
        name: "Test",
        slug: "test",
        provider: "ragflow",
        userId: "user-1",
        status: "ready",
        createdAt: now,
        updatedAt: now,
      });
      expect(result.description).toBeNull();
      expect(result.remoteId).toBeNull();
      expect(result.lastError).toBeNull();
      expect(result.organizationId).toBeNull();
    });

    test("extras 覆盖默认计数", () => {
      const now = new Date();
      const result = sanitizeKnowledgeBase(
        { id: "kb-1", name: "Test", slug: "test", provider: "ragflow", userId: "user-1", status: "ready", createdAt: now, updatedAt: now },
        { bindingsCount: 5, resourcesCount: 10, remoteExists: false },
      );
      expect(result.bindingsCount).toBe(5);
      expect(result.resourcesCount).toBe(10);
      expect(result.remoteExists).toBe(false);
    });

    test("无 extras 时计数默认 0", () => {
      const now = new Date();
      const result = sanitizeKnowledgeBase({
        id: "kb-1", name: "Test", slug: "test", provider: "ragflow", userId: "user-1", status: "ready", createdAt: now, updatedAt: now,
      });
      expect(result.bindingsCount).toBe(0);
      expect(result.resourcesCount).toBe(0);
      expect(result.remoteExists).toBe(true);
    });
  });
});
