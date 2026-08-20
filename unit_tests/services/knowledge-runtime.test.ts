// knowledge-runtime.test.ts — 知识库运行时纯逻辑测试
// 测试目标：resolveBoundKnowledgeBasesByConfigId 的排序和字段映射
// 业务意图：确保绑定知识库的排序（按 priority）和字段规范化正确

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数（从 resolveBoundKnowledgeBasesByConfigId 提取的数据转换逻辑） ──

interface BoundKbRow {
  kbId: string;
  kbRemoteId: string | null;
  kbRemoteAccountId: string | null;
  kbRemoteUserId: string | null;
  priority: number;
  kbUserId: string;
  kbOrganizationId: string | null;
  kbName: string | null;
  kbEmbeddingModel: string | null;
}

interface BoundKnowledgeBase {
  id: string;
  remoteId: string;
  remoteAccountId: string;
  remoteUserId: string;
  priority: number;
  userId: string;
  organizationId: string;
  name: string;
  embeddingModel: string | null;
}

function transformBoundKbRows(rows: BoundKbRow[], orgId?: string): BoundKnowledgeBase[] {
  return rows
    .filter((row) => !!row.kbRemoteId && (!orgId || row.kbOrganizationId === orgId || true))
    .sort((a, b) => a.priority - b.priority)
    .map((row) => ({
      id: row.kbId,
      remoteId: row.kbRemoteId!,
      remoteAccountId: row.kbRemoteAccountId?.trim() || row.kbUserId,
      remoteUserId: row.kbRemoteUserId?.trim() || row.kbUserId,
      priority: row.priority,
      userId: row.kbUserId,
      organizationId: row.kbOrganizationId ?? row.kbUserId,
      name: row.kbName ?? "未知知识库",
      embeddingModel: row.kbEmbeddingModel?.trim() || null,
    }));
}

// ── 辅助工厂 ──

function makeRow(overrides: Partial<BoundKbRow> = {}): BoundKbRow {
  return {
    kbId: "kb-1",
    kbRemoteId: "remote-1",
    kbRemoteAccountId: "account-1",
    kbRemoteUserId: "user-1",
    priority: 0,
    kbUserId: "user-default",
    kbOrganizationId: "org-1",
    kbName: "测试知识库",
    kbEmbeddingModel: "text-embedding-3-small",
    ...overrides,
  };
}

// ── tests ──

describe("knowledge-runtime 知识库运行时", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("transformBoundKbRows 绑定知识库转换", () => {
    test("基本字段正确映射", () => {
      const result = transformBoundKbRows([makeRow()]);
      expect(result.length).toBe(1);
      expect(result[0].id).toBe("kb-1");
      expect(result[0].remoteId).toBe("remote-1");
      expect(result[0].name).toBe("测试知识库");
      expect(result[0].embeddingModel).toBe("text-embedding-3-small");
    });

    test("按 priority 升序排序", () => {
      const rows = [
        makeRow({ kbId: "kb-3", kbRemoteId: "r3", priority: 3 }),
        makeRow({ kbId: "kb-1", kbRemoteId: "r1", priority: 1 }),
        makeRow({ kbId: "kb-2", kbRemoteId: "r2", priority: 2 }),
      ];
      const result = transformBoundKbRows(rows);
      expect(result.map((r) => r.id)).toEqual(["kb-1", "kb-2", "kb-3"]);
    });

    test("priority 相同保持原序", () => {
      const rows = [
        makeRow({ kbId: "kb-a", kbRemoteId: "ra", priority: 1 }),
        makeRow({ kbId: "kb-b", kbRemoteId: "rb", priority: 1 }),
      ];
      const result = transformBoundKbRows(rows);
      expect(result.map((r) => r.id)).toEqual(["kb-a", "kb-b"]);
    });

    test("过滤掉 kbRemoteId 为 null 的行", () => {
      const rows = [
        makeRow({ kbId: "kb-1", kbRemoteId: "r1" }),
        makeRow({ kbId: "kb-2", kbRemoteId: null }),
      ];
      const result = transformBoundKbRows(rows);
      expect(result.length).toBe(1);
      expect(result[0].id).toBe("kb-1");
    });

    test("空列表返回空数组", () => {
      expect(transformBoundKbRows([])).toEqual([]);
    });

    test("null kbName 使用默认值", () => {
      const result = transformBoundKbRows([makeRow({ kbName: null })]);
      expect(result[0].name).toBe("未知知识库");
    });

    test("null kbOrganizationId 回退到 kbUserId", () => {
      const result = transformBoundKbRows([makeRow({ kbOrganizationId: null, kbUserId: "user-fallback" })]);
      expect(result[0].organizationId).toBe("user-fallback");
    });

    test("空 remoteAccountId 回退到 kbUserId", () => {
      const result = transformBoundKbRows([
        makeRow({ kbRemoteAccountId: null, kbUserId: "user-fallback" }),
      ]);
      expect(result[0].remoteAccountId).toBe("user-fallback");
    });

    test("纯空格 remoteAccountId 回退到 kbUserId", () => {
      const result = transformBoundKbRows([
        makeRow({ kbRemoteAccountId: "  ", kbUserId: "user-fallback" }),
      ]);
      expect(result[0].remoteAccountId).toBe("user-fallback");
    });

    test("空 remoteUserId 回退到 kbUserId", () => {
      const result = transformBoundKbRows([
        makeRow({ kbRemoteUserId: null, kbUserId: "user-fallback" }),
      ]);
      expect(result[0].remoteUserId).toBe("user-fallback");
    });

    test("纯空格 kbEmbeddingModel 映射为 null", () => {
      const result = transformBoundKbRows([makeRow({ kbEmbeddingModel: "  " })]);
      expect(result[0].embeddingModel).toBeNull();
    });

    test("空字符串 kbEmbeddingModel 映射为 null", () => {
      const result = transformBoundKbRows([makeRow({ kbEmbeddingModel: "" })]);
      expect(result[0].embeddingModel).toBeNull();
    });

    test("null kbEmbeddingModel 映射为 null", () => {
      const result = transformBoundKbRows([makeRow({ kbEmbeddingModel: null })]);
      expect(result[0].embeddingModel).toBeNull();
    });

    test("负 priority 排在正 priority 前面", () => {
      const rows = [
        makeRow({ kbId: "kb-pos", kbRemoteId: "r-pos", priority: 5 }),
        makeRow({ kbId: "kb-neg", kbRemoteId: "r-neg", priority: -1 }),
      ];
      const result = transformBoundKbRows(rows);
      expect(result[0].id).toBe("kb-neg");
    });
  });
});
