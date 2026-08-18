import { describe, test, expect } from "bun:test";

// --- Pure functions copied from source ---

function configSuccess<T>(data: T) {
  return { success: true as const, data };
}
function configError(code: string, message: string, data?: unknown) {
  return { success: false as const, error: { code, message }, ...(data !== undefined ? { data } : {}) };
}
function configNotFound(resource: string) {
  return configError("NOT_FOUND", resource);
}
function configValidationError(message: string) {
  return configError("VALIDATION_ERROR", message);
}
function isValidResourceName(name: string): boolean {
  return (
    typeof name === "string" &&
    name.length >= 1 &&
    name.length <= 64 &&
    !name.includes("--") &&
    /^[\p{L}0-9][\p{L}0-9 -]*[\p{L}0-9]$|^[\p{L}0-9]$/u.test(name)
  );
}
function resolveApiKey(raw: string | undefined | null): string | null {
  if (!raw) return null;
  const envMatch = raw.match(/^\{env:(.+)\}$/);
  return envMatch ? (process.env[envMatch[1]] ?? null) : raw;
}
function toKeyHint(apiKey: string | undefined | null): string | null {
  const realKey = resolveApiKey(apiKey);
  if (!realKey || realKey.length < 4) return "*******";
  return `***${realKey.slice(-4)}`;
}
function safeJsonStringify(value: unknown): string | undefined {
  return value != null ? JSON.stringify(value) : undefined;
}
function safeJsonParse<T>(value: string | null | undefined): T | null {
  if (!value) return null;
  try { return JSON.parse(value) as T; } catch { return null; }
}

// --- Tests ---

describe("configSuccess", () => {
  test("returns correct shape with data", () => {
    const result = configSuccess({ id: 1, name: "test" });
    expect(result.success).toBe(true);
    expect(result.data).toEqual({ id: 1, name: "test" });
  });

  test("works with primitive data", () => {
    const result = configSuccess("hello");
    expect(result.success).toBe(true);
    expect(result.data).toBe("hello");
  });

  test("works with array data", () => {
    const result = configSuccess([1, 2, 3]);
    expect(result.success).toBe(true);
    expect(result.data).toEqual([1, 2, 3]);
  });

  test("works with null data", () => {
    const result = configSuccess(null);
    expect(result.success).toBe(true);
    expect(result.data).toBeNull();
  });
});

describe("configError", () => {
  test("returns correct shape without data", () => {
    const result = configError("ERR_CODE", "something went wrong");
    expect(result.success).toBe(false);
    expect(result.error).toEqual({ code: "ERR_CODE", message: "something went wrong" });
    expect((result as Record<string, unknown>).data).toBeUndefined();
  });

  test("returns correct shape with data", () => {
    const result = configError("ERR_CODE", "something went wrong", { field: "name" });
    expect(result.success).toBe(false);
    expect(result.error).toEqual({ code: "ERR_CODE", message: "something went wrong" });
    expect((result as Record<string, unknown>).data).toEqual({ field: "name" });
  });

  test("includes data key when data is explicitly provided as null", () => {
    const result = configError("ERR_CODE", "msg", null);
    expect((result as Record<string, unknown>).data).toBeNull();
  });

  test("includes data key when data is explicitly provided as undefined", () => {
    // undefined means "not provided" in the spread, so data key should be absent
    const result = configError("ERR_CODE", "msg", undefined);
    expect((result as Record<string, unknown>).data).toBeUndefined();
  });
});

describe("configNotFound", () => {
  test("returns NOT_FOUND error with resource name", () => {
    const result = configNotFound("Agent not found");
    expect(result.success).toBe(false);
    expect(result.error.code).toBe("NOT_FOUND");
    expect(result.error.message).toBe("Agent not found");
  });
});

describe("configValidationError", () => {
  test("returns VALIDATION_ERROR with message", () => {
    const result = configValidationError("Name is required");
    expect(result.success).toBe(false);
    expect(result.error.code).toBe("VALIDATION_ERROR");
    expect(result.error.message).toBe("Name is required");
  });
});

describe("isValidResourceName", () => {
  test("accepts simple alphanumeric names", () => {
    expect(isValidResourceName("my-agent")).toBe(true);
    expect(isValidResourceName("agent1")).toBe(true);
    expect(isValidResourceName("Test Agent")).toBe(true);
  });

  test("accepts single character", () => {
    expect(isValidResourceName("a")).toBe(true);
    expect(isValidResourceName("1")).toBe(true);
  });

  test("accepts unicode letters", () => {
    expect(isValidResourceName("智能助手")).toBe(true);
    expect(isValidResourceName("エージェント")).toBe(true);
    expect(isValidResourceName("café")).toBe(true);
  });

  test("accepts names with spaces and hyphens", () => {
    expect(isValidResourceName("my agent name")).toBe(true);
    expect(isValidResourceName("my-agent-v2")).toBe(true);
    expect(isValidResourceName("agent v2-prod")).toBe(true);
  });

  test("rejects empty string", () => {
    expect(isValidResourceName("")).toBe(false);
  });

  test("rejects names longer than 64 characters", () => {
    const longName = "a".repeat(65);
    expect(isValidResourceName(longName)).toBe(false);
  });

  test("accepts names exactly 64 characters", () => {
    const name64 = "a".repeat(64);
    expect(isValidResourceName(name64)).toBe(true);
  });

  test("rejects names containing double hyphens", () => {
    expect(isValidResourceName("my--agent")).toBe(false);
    expect(isValidResourceName("a--b")).toBe(false);
  });

  test("rejects names starting with space or hyphen", () => {
    expect(isValidResourceName(" agent")).toBe(false);
    expect(isValidResourceName("-agent")).toBe(false);
  });

  test("rejects names ending with space or hyphen", () => {
    expect(isValidResourceName("agent ")).toBe(false);
    expect(isValidResourceName("agent-")).toBe(false);
  });

  test("rejects non-string input", () => {
    expect(isValidResourceName(null as unknown as string)).toBe(false);
    expect(isValidResourceName(undefined as unknown as string)).toBe(false);
    expect(isValidResourceName(123 as unknown as string)).toBe(false);
  });
});

describe("resolveApiKey", () => {
  test("returns plain key as-is", () => {
    expect(resolveApiKey("sk-abc123")).toBe("sk-abc123");
  });

  test("resolves env reference when env var is set", () => {
    const original = process.env.TEST_API_KEY_123;
    try {
      process.env.TEST_API_KEY_123 = "resolved-key";
      expect(resolveApiKey("{env:TEST_API_KEY_123}")).toBe("resolved-key");
    } finally {
      if (original === undefined) delete process.env.TEST_API_KEY_123;
      else process.env.TEST_API_KEY_123 = original;
    }
  });

  test("returns null for env reference when env var is not set", () => {
    delete process.env.NONEXISTENT_KEY_XYZ;
    expect(resolveApiKey("{env:NONEXISTENT_KEY_XYZ}")).toBeNull();
  });

  test("returns null for null input", () => {
    expect(resolveApiKey(null)).toBeNull();
  });

  test("returns null for undefined input", () => {
    expect(resolveApiKey(undefined)).toBeNull();
  });

  test("returns null for empty string", () => {
    expect(resolveApiKey("")).toBeNull();
  });

  test("does not resolve partial env pattern", () => {
    expect(resolveApiKey("{env:")).toBe("{env:");
    expect(resolveApiKey("env:KEY}")).toBe("env:KEY}");
  });
});

describe("toKeyHint", () => {
  test("shows last 4 chars for normal key", () => {
    expect(toKeyHint("sk-abc1234")).toBe("***1234");
  });

  test("shows masked hint for short key (less than 4 chars)", () => {
    expect(toKeyHint("ab")).toBe("*******");
    expect(toKeyHint("abc")).toBe("*******");
  });

  test("shows masked hint for exactly 4-char key", () => {
    // length is 4, so realKey.length < 4 is false, should show last 4
    expect(toKeyHint("abcd")).toBe("***abcd");
  });

  test("returns masked hint for null", () => {
    expect(toKeyHint(null)).toBe("*******");
  });

  test("returns masked hint for undefined", () => {
    expect(toKeyHint(undefined)).toBe("*******");
  });

  test("resolves env reference before hinting", () => {
    const original = process.env.TEST_HINT_KEY;
    try {
      process.env.TEST_HINT_KEY = "my-secret-key-abcd";
      expect(toKeyHint("{env:TEST_HINT_KEY}")).toBe("***abcd");
    } finally {
      if (original === undefined) delete process.env.TEST_HINT_KEY;
      else process.env.TEST_HINT_KEY = original;
    }
  });
});

describe("safeJsonStringify", () => {
  test("stringifies an object", () => {
    expect(safeJsonStringify({ a: 1 })).toBe('{"a":1}');
  });

  test("stringifies a string", () => {
    expect(safeJsonStringify("hello")).toBe('"hello"');
  });

  test("stringifies a number", () => {
    expect(safeJsonStringify(42)).toBe("42");
  });

  test("stringifies an array", () => {
    expect(safeJsonStringify([1, 2])).toBe("[1,2]");
  });

  test("stringifies boolean false", () => {
    expect(safeJsonStringify(false)).toBe("false");
  });

  test("stringifies zero", () => {
    expect(safeJsonStringify(0)).toBe("0");
  });

  test("returns undefined for null", () => {
    expect(safeJsonStringify(null)).toBeUndefined();
  });

  test("returns undefined for undefined", () => {
    expect(safeJsonStringify(undefined)).toBeUndefined();
  });
});

describe("safeJsonParse", () => {
  test("parses valid JSON object", () => {
    expect(safeJsonParse('{"a":1}')).toEqual({ a: 1 });
  });

  test("parses valid JSON array", () => {
    expect(safeJsonParse("[1,2,3]")).toEqual([1, 2, 3]);
  });

  test("parses valid JSON string", () => {
    expect(safeJsonParse('"hello"')).toBe("hello");
  });

  test("parses valid JSON number", () => {
    expect(safeJsonParse("42")).toBe(42);
  });

  test("returns null for invalid JSON", () => {
    expect(safeJsonParse("{invalid}")).toBeNull();
  });

  test("returns null for null input", () => {
    expect(safeJsonParse(null)).toBeNull();
  });

  test("returns null for undefined input", () => {
    expect(safeJsonParse(undefined)).toBeNull();
  });

  test("returns null for empty string", () => {
    expect(safeJsonParse("")).toBeNull();
  });
});
