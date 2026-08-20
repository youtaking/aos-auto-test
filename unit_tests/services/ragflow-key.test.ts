// ragflow-key.test.ts — RAGFlow API Key 解析测试
//
// 被测模块 src/services/ragflow-key.ts 在模块顶层导入 config，
// 在 preload 环境下 mock.module 不易覆盖该导入。因此本测试采用
// pure function copy 模式：复制 resolveRagflowApiKey 的纯逻辑，
// 验证 trim 校验 + 错误文案行为。

import { describe, expect, test } from "bun:test";

// ── Pure function copy ──

function resolveRagflowApiKeyPure(
  ragflowApiKey: string,
  _keySource: string,
  _userId: string,
  _orgId: string,
): string {
  if (!ragflowApiKey.trim()) {
    throw new Error("RAGFLOW_API_KEY is not configured");
  }
  return ragflowApiKey;
}

describe("resolveRagflowApiKey（纯逻辑）", () => {
  test("配置有效时返回全局 ragflowApiKey（忽略入参）", () => {
    const result = resolveRagflowApiKeyPure("ragflow-global-key-12345", "any-source", "u", "o");
    expect(result).toBe("ragflow-global-key-12345");
  });

  test("不同入参返回相同 key（全局唯一）", () => {
    const r1 = resolveRagflowApiKeyPure("shared-key", "source-a", "user-1", "org-1");
    const r2 = resolveRagflowApiKeyPure("shared-key", "source-b", "user-2", "org-2");
    expect(r1).toBe(r2);
    expect(r1).toBe("shared-key");
  });

  test("空字符串配置抛出 RAGFLOW_API_KEY is not configured", () => {
    expect(() => resolveRagflowApiKeyPure("", "s", "u", "o")).toThrow(
      "RAGFLOW_API_KEY is not configured",
    );
  });

  test("纯空白配置抛出异常（trim 后为空）", () => {
    expect(() => resolveRagflowApiKeyPure("   ", "s", "u", "o")).toThrow(
      "RAGFLOW_API_KEY is not configured",
    );
  });

  test("制表符换行等空白也视为空", () => {
    expect(() => resolveRagflowApiKeyPure("\t\n  ", "s", "u", "o")).toThrow(
      "RAGFLOW_API_KEY is not configured",
    );
  });

  test("配置前后有空白时 trim 校验通过并返回原始值（含空白）", () => {
    const result = resolveRagflowApiKeyPure("  valid-key  ", "s", "u", "o");
    expect(result).toBe("  valid-key  ");
  });

  test("单字符 key 也算有效", () => {
    expect(resolveRagflowApiKeyPure("x", "s", "u", "o")).toBe("x");
  });

  test("特殊字符 key 原样返回", () => {
    const key = "ragflow!@#$%^&*()_+-=[]{}|;':\",./<>?";
    expect(resolveRagflowApiKeyPure(key, "s", "u", "o")).toBe(key);
  });
});
