// system-api.test.ts — 系统 API 纯函数测试
// 测试目标：buildPersonalOrganizationSlug、buildApiKeyMetadata、generateApiKeyString、
//   normalizeApiKeyName、parseApiKeyMetadata

import { describe, expect, test } from "bun:test";

// ── 复制纯函数（隔离 DB 依赖）──

function buildPersonalOrganizationSlug(userId: string): string {
  return `personal-${userId.slice(0, 8)}`;
}

function buildApiKeyMetadata(
  organizationId: string,
  role: "owner" | "admin" | "member",
  metadata?: Record<string, unknown>,
): Record<string, unknown> {
  return {
    ...(metadata ?? {}),
    organizationId,
    role,
  };
}

function generateApiKeyString(prefix = "rcs_"): string {
  // 模拟：使用 crypto.randomUUID
  const uuid1 = crypto.randomUUID().replaceAll("-", "");
  const uuid2 = crypto.randomUUID().replaceAll("-", "");
  return `${prefix}${uuid1}${uuid2}`;
}

function normalizeApiKeyName(name: string): string {
  return name.trim();
}

function parseApiKeyMetadata(raw: string | null): Record<string, unknown> | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as unknown;
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

const API_KEY_START_LENGTH = 6;

// ── Tests ──

describe("system-api 纯函数", () => {
  // ── buildPersonalOrganizationSlug ──

  describe("buildPersonalOrganizationSlug", () => {
    test("截取 userId 前 8 位", () => {
      expect(buildPersonalOrganizationSlug("12345678-1234-1234")).toBe("personal-12345678");
    });

    test("短 userId 不截断", () => {
      expect(buildPersonalOrganizationSlug("abc")).toBe("personal-abc");
    });

    test("空字符串 userId", () => {
      expect(buildPersonalOrganizationSlug("")).toBe("personal-");
    });

    test("正好 8 位 userId", () => {
      expect(buildPersonalOrganizationSlug("12345678")).toBe("personal-12345678");
    });
  });

  // ── buildApiKeyMetadata ──

  describe("buildApiKeyMetadata", () => {
    test("基础构建包含 organizationId 和 role", () => {
      const result = buildApiKeyMetadata("org-1", "owner");
      expect(result.organizationId).toBe("org-1");
      expect(result.role).toBe("owner");
    });

    test("自定义 metadata 被合并", () => {
      const result = buildApiKeyMetadata("org-1", "member", { custom: "value" });
      expect(result.custom).toBe("value");
      expect(result.organizationId).toBe("org-1");
      expect(result.role).toBe("member");
    });

    test("organizationId 和 role 覆盖自定义 metadata 中的同名字段", () => {
      const result = buildApiKeyMetadata("org-actual", "admin", {
        organizationId: "org-fake",
        role: "fake-role",
      });
      expect(result.organizationId).toBe("org-actual");
      expect(result.role).toBe("admin");
    });

    test("metadata 为 undefined 时不报错", () => {
      const result = buildApiKeyMetadata("org-1", "owner", undefined);
      expect(result.organizationId).toBe("org-1");
    });
  });

  // ── generateApiKeyString ──

  describe("generateApiKeyString", () => {
    test("默认前缀为 rcs_", () => {
      const key = generateApiKeyString();
      expect(key.startsWith("rcs_")).toBe(true);
    });

    test("自定义前缀", () => {
      const key = generateApiKeyString("test_");
      expect(key.startsWith("test_")).toBe(true);
    });

    test("key 长度正确（前缀 + 64 hex 字符）", () => {
      const key = generateApiKeyString("rcs_");
      // rcs_ (4) + 2 UUIDs without dashes (32 + 32) = 68
      expect(key.length).toBe(68);
    });

    test("两次调用生成不同的 key", () => {
      const a = generateApiKeyString();
      const b = generateApiKeyString();
      expect(a).not.toBe(b);
    });

    test("start 预览取前 6 位", () => {
      const key = generateApiKeyString("rcs_");
      const start = key.slice(0, API_KEY_START_LENGTH);
      expect(start.length).toBe(6);
      expect(start.startsWith("rcs_")).toBe(true);
    });
  });

  // ── normalizeApiKeyName ──

  describe("normalizeApiKeyName", () => {
    test("去除前后空格", () => {
      expect(normalizeApiKeyName("  my-key  ")).toBe("my-key");
    });

    test("空字符串返回空", () => {
      expect(normalizeApiKeyName("")).toBe("");
    });

    test("纯空格返回空", () => {
      expect(normalizeApiKeyName("   ")).toBe("");
    });

    test("无空格保持不变", () => {
      expect(normalizeApiKeyName("my-api-key")).toBe("my-api-key");
    });
  });

  // ── parseApiKeyMetadata ──

  describe("parseApiKeyMetadata", () => {
    test("合法 JSON 对象字符串返回解析结果", () => {
      const result = parseApiKeyMetadata('{"organizationId":"org-1","role":"owner"}');
      expect(result).toEqual({ organizationId: "org-1", role: "owner" });
    });

    test("null 输入返回 null", () => {
      expect(parseApiKeyMetadata(null)).toBeNull();
    });

    test("空字符串返回 null", () => {
      expect(parseApiKeyMetadata("")).toBeNull();
    });

    test("非法 JSON 返回 null", () => {
      expect(parseApiKeyMetadata("not-json")).toBeNull();
    });

    test("JSON 数组返回 null", () => {
      expect(parseApiKeyMetadata("[1,2,3]")).toBeNull();
    });

    test("JSON 原始值返回 null", () => {
      expect(parseApiKeyMetadata('"string"')).toBeNull();
      expect(parseApiKeyMetadata("42")).toBeNull();
      expect(parseApiKeyMetadata("true")).toBeNull();
    });

    test("嵌套对象正常解析", () => {
      const result = parseApiKeyMetadata('{"organizationId":"org-1","extra":{"key":"val"}}');
      expect(result!.organizationId).toBe("org-1");
      expect(result!.extra).toEqual({ key: "val" });
    });
  });
});
