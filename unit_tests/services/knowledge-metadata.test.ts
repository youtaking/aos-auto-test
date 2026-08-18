import { describe, test, expect } from "bun:test";

// ── Pure function copies from src/services/knowledge-metadata.ts ──

type KnowledgeBaseParseMethod = "builtin" | "pipeline";

interface KnowledgeBaseMetadataShape {
  embeddingModel: string | null;
  parseMethod: KnowledgeBaseParseMethod | null;
  chunkMethod: string | null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeOptionalString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function normalizeParseMethod(value: unknown): KnowledgeBaseParseMethod | null {
  return value === "builtin" || value === "pipeline" ? value : null;
}

function readKnowledgeBaseMetadata(metadata: unknown): KnowledgeBaseMetadataShape {
  const raw = isRecord(metadata) ? metadata : {};
  return {
    embeddingModel: normalizeOptionalString(raw.embeddingModel),
    parseMethod: normalizeParseMethod(raw.parseMethod),
    chunkMethod: normalizeOptionalString(raw.chunkMethod),
  };
}

function mergeKnowledgeBaseMetadata(
  current: unknown,
  patch: {
    embeddingModel?: unknown;
    parseMethod?: unknown;
    chunkMethod?: unknown;
  },
): Record<string, unknown> | null {
  const next = isRecord(current) ? { ...current } : {};

  if ("embeddingModel" in patch) {
    const value = normalizeOptionalString(patch.embeddingModel);
    if (value) next.embeddingModel = value;
    else delete next.embeddingModel;
  }

  if ("parseMethod" in patch) {
    const value = normalizeParseMethod(patch.parseMethod);
    if (value) next.parseMethod = value;
    else delete next.parseMethod;
  }

  if ("chunkMethod" in patch) {
    const value = normalizeOptionalString(patch.chunkMethod);
    if (value) next.chunkMethod = value;
    else delete next.chunkMethod;
  }

  return Object.keys(next).length > 0 ? next : null;
}

// ── Tests ──

describe("isRecord", () => {
  test("plain object returns true", () => {
    expect(isRecord({ a: 1 })).toBe(true);
  });

  test("null returns false", () => {
    expect(isRecord(null)).toBe(false);
  });

  test("array returns false", () => {
    expect(isRecord([1, 2])).toBe(false);
  });

  test("string returns false", () => {
    expect(isRecord("hello")).toBe(false);
  });

  test("number returns false", () => {
    expect(isRecord(42)).toBe(false);
  });

  test("empty object returns true", () => {
    expect(isRecord({})).toBe(true);
  });
});

describe("normalizeOptionalString", () => {
  test("valid string returns trimmed", () => {
    expect(normalizeOptionalString("  hello  ")).toBe("hello");
  });

  test("empty string returns null", () => {
    expect(normalizeOptionalString("")).toBeNull();
  });

  test("whitespace-only returns null", () => {
    expect(normalizeOptionalString("   ")).toBeNull();
  });

  test("non-string returns null", () => {
    expect(normalizeOptionalString(42)).toBeNull();
    expect(normalizeOptionalString(null)).toBeNull();
    expect(normalizeOptionalString(undefined)).toBeNull();
    expect(normalizeOptionalString(true)).toBeNull();
  });
});

describe("normalizeParseMethod", () => {
  test("'builtin' returns 'builtin'", () => {
    expect(normalizeParseMethod("builtin")).toBe("builtin");
  });

  test("'pipeline' returns 'pipeline'", () => {
    expect(normalizeParseMethod("pipeline")).toBe("pipeline");
  });

  test("invalid string returns null", () => {
    expect(normalizeParseMethod("unknown")).toBeNull();
  });

  test("non-string returns null", () => {
    expect(normalizeParseMethod(123)).toBeNull();
    expect(normalizeParseMethod(null)).toBeNull();
  });
});

describe("readKnowledgeBaseMetadata", () => {
  test("extracts all fields from valid metadata", () => {
    const result = readKnowledgeBaseMetadata({
      embeddingModel: "text-embedding-ada-002",
      parseMethod: "builtin",
      chunkMethod: "recursive",
    });

    expect(result).toEqual({
      embeddingModel: "text-embedding-ada-002",
      parseMethod: "builtin",
      chunkMethod: "recursive",
    });
  });

  test("returns nulls for missing fields", () => {
    const result = readKnowledgeBaseMetadata({});
    expect(result).toEqual({
      embeddingModel: null,
      parseMethod: null,
      chunkMethod: null,
    });
  });

  test("handles null input gracefully", () => {
    const result = readKnowledgeBaseMetadata(null);
    expect(result).toEqual({
      embeddingModel: null,
      parseMethod: null,
      chunkMethod: null,
    });
  });

  test("handles non-object input gracefully", () => {
    expect(readKnowledgeBaseMetadata("string")).toEqual({
      embeddingModel: null,
      parseMethod: null,
      chunkMethod: null,
    });
    expect(readKnowledgeBaseMetadata(42)).toEqual({
      embeddingModel: null,
      parseMethod: null,
      chunkMethod: null,
    });
  });

  test("handles array input gracefully", () => {
    const result = readKnowledgeBaseMetadata([1, 2, 3]);
    expect(result).toEqual({
      embeddingModel: null,
      parseMethod: null,
      chunkMethod: null,
    });
  });

  test("trims whitespace in string fields", () => {
    const result = readKnowledgeBaseMetadata({
      embeddingModel: "  model-name  ",
      chunkMethod: "  fixed  ",
    });
    expect(result.embeddingModel).toBe("model-name");
    expect(result.chunkMethod).toBe("fixed");
  });

  test("empty string fields become null", () => {
    const result = readKnowledgeBaseMetadata({
      embeddingModel: "",
      chunkMethod: "   ",
    });
    expect(result.embeddingModel).toBeNull();
    expect(result.chunkMethod).toBeNull();
  });

  test("invalid parseMethod becomes null", () => {
    const result = readKnowledgeBaseMetadata({
      parseMethod: "invalid_method",
    });
    expect(result.parseMethod).toBeNull();
  });

  test("ignores extra unknown fields", () => {
    const result = readKnowledgeBaseMetadata({
      embeddingModel: "model",
      unknownField: "value",
    });
    expect(result.embeddingModel).toBe("model");
    expect((result as Record<string, unknown>).unknownField).toBeUndefined();
  });
});

describe("mergeKnowledgeBaseMetadata", () => {
  test("sets new field from patch", () => {
    const result = mergeKnowledgeBaseMetadata({}, { embeddingModel: "new-model" });
    expect(result).toEqual({ embeddingModel: "new-model" });
  });

  test("overwrites existing field", () => {
    const result = mergeKnowledgeBaseMetadata(
      { embeddingModel: "old-model" },
      { embeddingModel: "new-model" },
    );
    expect(result).toEqual({ embeddingModel: "new-model" });
  });

  test("deletes field when patch value is empty string", () => {
    const result = mergeKnowledgeBaseMetadata(
      { embeddingModel: "model" },
      { embeddingModel: "" },
    );
    expect(result).toBeNull();
  });

  test("deletes field when patch value is null", () => {
    const result = mergeKnowledgeBaseMetadata(
      { embeddingModel: "model" },
      { embeddingModel: null },
    );
    expect(result).toBeNull();
  });

  test("preserves unknown fields in current", () => {
    const result = mergeKnowledgeBaseMetadata(
      { embeddingModel: "model", customField: "keep" },
      { embeddingModel: "new-model" },
    );
    expect(result).toEqual({ embeddingModel: "new-model", customField: "keep" });
  });

  test("returns null when result is empty", () => {
    const result = mergeKnowledgeBaseMetadata({}, { embeddingModel: "" });
    expect(result).toBeNull();
  });

  test("handles non-object current gracefully", () => {
    const result = mergeKnowledgeBaseMetadata(null, { embeddingModel: "model" });
    expect(result).toEqual({ embeddingModel: "model" });
  });

  test("handles non-object current with string", () => {
    const result = mergeKnowledgeBaseMetadata("invalid", { parseMethod: "builtin" });
    expect(result).toEqual({ parseMethod: "builtin" });
  });

  test("sets parseMethod with valid value", () => {
    const result = mergeKnowledgeBaseMetadata({}, { parseMethod: "pipeline" });
    expect(result).toEqual({ parseMethod: "pipeline" });
  });

  test("deletes parseMethod when patch has invalid value", () => {
    const result = mergeKnowledgeBaseMetadata(
      { parseMethod: "builtin" },
      { parseMethod: "invalid" },
    );
    expect(result).toBeNull();
  });

  test("sets chunkMethod", () => {
    const result = mergeKnowledgeBaseMetadata({}, { chunkMethod: "recursive" });
    expect(result).toEqual({ chunkMethod: "recursive" });
  });

  test("patch without a field does not affect that field", () => {
    const result = mergeKnowledgeBaseMetadata(
      { embeddingModel: "model", chunkMethod: "fixed" },
      { embeddingModel: "new-model" },
    );
    expect(result).toEqual({ embeddingModel: "new-model", chunkMethod: "fixed" });
  });

  test("merging multiple fields at once", () => {
    const result = mergeKnowledgeBaseMetadata(
      { embeddingModel: "old" },
      { embeddingModel: "new", parseMethod: "builtin", chunkMethod: "fixed" },
    );
    expect(result).toEqual({
      embeddingModel: "new",
      parseMethod: "builtin",
      chunkMethod: "fixed",
    });
  });

  test("does not mutate original current object", () => {
    const current = { embeddingModel: "original" };
    mergeKnowledgeBaseMetadata(current, { embeddingModel: "changed" });
    expect(current.embeddingModel).toBe("original");
  });
});
