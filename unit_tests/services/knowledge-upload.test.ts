// knowledge-upload.test.ts — 知识库上传纯逻辑测试
// 测试目标：sanitizeResource、isRemoteKnowledgeResourceMissingError
// 业务意图：确保资源数据清洗和远端缺失错误判断正确

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数 ──

type KnowledgeResourceStatus = "pending" | "indexing" | "ready" | "error";

interface KnowledgeResourceRow {
  id: string;
  knowledgeBaseId: string;
  sourceName: string;
  sourceType: string;
  sourcePath: string | null;
  remoteId: string | null;
  status: string;
  lastError: string | null;
  createdAt: Date;
  updatedAt: Date;
}

function sanitizeResource(row: KnowledgeResourceRow) {
  return {
    id: row.id,
    knowledgeBaseId: row.knowledgeBaseId,
    sourceName: row.sourceName,
    sourceType: row.sourceType,
    sourcePath: row.sourcePath ?? null,
    remoteId: row.remoteId ?? null,
    status: row.status as KnowledgeResourceStatus,
    lastError: row.lastError ?? null,
    createdAt: Math.floor(row.createdAt.getTime() / 1000),
    updatedAt: Math.floor(row.updatedAt.getTime() / 1000),
  };
}

function isRemoteKnowledgeResourceMissingError(err: unknown): boolean {
  const message = err instanceof Error ? err.message.toLowerCase() : String(err).toLowerCase();
  return (
    message.includes("not found") ||
    message.includes("not exist") ||
    message.includes("nonexistent") ||
    message.includes("document not found") ||
    message.includes("http 404")
  );
}

// ── 辅助工厂 ──

function makeRow(overrides: Partial<KnowledgeResourceRow> = {}): KnowledgeResourceRow {
  return {
    id: "res-1",
    knowledgeBaseId: "kb-1",
    sourceName: "test.pdf",
    sourceType: "upload",
    sourcePath: "/data/test.pdf",
    remoteId: "remote-1",
    status: "ready",
    lastError: null,
    createdAt: new Date("2024-01-15T10:30:00Z"),
    updatedAt: new Date("2024-01-15T11:00:00Z"),
    ...overrides,
  };
}

// ── tests ──

describe("knowledge-upload 知识库上传", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("sanitizeResource 资源数据清洗", () => {
    test("基本字段正确映射", () => {
      const result = sanitizeResource(makeRow());
      expect(result.id).toBe("res-1");
      expect(result.knowledgeBaseId).toBe("kb-1");
      expect(result.sourceName).toBe("test.pdf");
      expect(result.sourceType).toBe("upload");
      expect(result.status).toBe("ready");
    });

    test("Date 字段转为 Unix 时间戳", () => {
      const createdAt = new Date("2024-01-15T10:30:00Z");
      const updatedAt = new Date("2024-01-15T11:00:00Z");
      const result = sanitizeResource(makeRow({ createdAt, updatedAt }));
      expect(result.createdAt).toBe(Math.floor(createdAt.getTime() / 1000));
      expect(result.updatedAt).toBe(Math.floor(updatedAt.getTime() / 1000));
    });

    test("null sourcePath 保持 null", () => {
      const result = sanitizeResource(makeRow({ sourcePath: null }));
      expect(result.sourcePath).toBeNull();
    });

    test("null remoteId 保持 null", () => {
      const result = sanitizeResource(makeRow({ remoteId: null }));
      expect(result.remoteId).toBeNull();
    });

    test("null lastError 保持 null", () => {
      const result = sanitizeResource(makeRow({ lastError: null }));
      expect(result.lastError).toBeNull();
    });

    test("undefined sourcePath 映射为 null", () => {
      const row = makeRow();
      (row as any).sourcePath = undefined;
      const result = sanitizeResource(row);
      expect(result.sourcePath).toBeNull();
    });

    test("undefined remoteId 映射为 null", () => {
      const row = makeRow();
      (row as any).remoteId = undefined;
      const result = sanitizeResource(row);
      expect(result.remoteId).toBeNull();
    });

    test("undefined lastError 映射为 null", () => {
      const row = makeRow();
      (row as any).lastError = undefined;
      const result = sanitizeResource(row);
      expect(result.lastError).toBeNull();
    });

    test("status 为 error 时保留", () => {
      const result = sanitizeResource(makeRow({ status: "error", lastError: "failed" }));
      expect(result.status).toBe("error");
      expect(result.lastError).toBe("failed");
    });

    test("status 为 pending 时保留", () => {
      const result = sanitizeResource(makeRow({ status: "pending" }));
      expect(result.status).toBe("pending");
    });
  });

  describe("isRemoteKnowledgeResourceMissingError 远端缺失错误判断", () => {
    test("'not found' 匹配", () => {
      expect(isRemoteKnowledgeResourceMissingError(new Error("Document not found"))).toBe(true);
    });

    test("'not exist' 匹配", () => {
      expect(isRemoteKnowledgeResourceMissingError(new Error("Resource does not exist"))).toBe(true);
    });

    test("'nonexistent' 匹配", () => {
      expect(isRemoteKnowledgeResourceMissingError(new Error("Target is nonexistent"))).toBe(true);
    });

    test("'document not found' 匹配", () => {
      expect(isRemoteKnowledgeResourceMissingError(new Error("document not found in ragflow"))).toBe(true);
    });

    test("'HTTP 404' 匹配", () => {
      expect(isRemoteKnowledgeResourceMissingError(new Error("HTTP 404 response"))).toBe(true);
    });

    test("大小写不敏感", () => {
      expect(isRemoteKnowledgeResourceMissingError(new Error("NOT FOUND"))).toBe(true);
      expect(isRemoteKnowledgeResourceMissingError(new Error("Not Found"))).toBe(true);
    });

    test("不匹配的错误返回 false", () => {
      expect(isRemoteKnowledgeResourceMissingError(new Error("Connection timeout"))).toBe(false);
    });

    test("空错误消息返回 false", () => {
      expect(isRemoteKnowledgeResourceMissingError(new Error(""))).toBe(false);
    });

    test("字符串错误也支持", () => {
      expect(isRemoteKnowledgeResourceMissingError("not found")).toBe(true);
    });

    test("非 Error 非字符串也支持", () => {
      expect(isRemoteKnowledgeResourceMissingError(42)).toBe(false);
    });
  });
});
