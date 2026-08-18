import { describe, test, expect } from "bun:test";

// ── Pure function copies from packages/workflow-engine/src/secrets/secrets-resolver.ts ──
// Source version: FenixAgent/packages/workflow-engine/src/secrets/secrets-resolver.ts (commit f5ac00e, 2025-08)
// Only the pure redaction logic is copied (no file I/O for parseEnvFile).
//
// Test adaptation: In the source, redactValue is a private method of SecretsResolver class.
// Here it's extracted as a standalone function for direct unit testing without class instantiation.
// The logic is identical — exact string match replacement, recursive traversal of arrays/objects.

/**
 * Recursively redact secret values from metadata.
 * - Strings that exactly match a secret value are replaced with "***"
 * - Arrays and objects are traversed recursively
 * - Non-string primitives are returned as-is
 */
function redactValue(value: unknown, secretValues: Record<string, string>): unknown {
  if (typeof value === "string") {
    if (Object.values(secretValues).includes(value)) {
      return "***";
    }
    return value;
  }

  if (Array.isArray(value)) {
    return value.map((item) => redactValue(item, secretValues));
  }

  if (value !== null && typeof value === "object") {
    const result: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      result[k] = redactValue(v, secretValues);
    }
    return result;
  }

  return value;
}

function redactSecrets(
  metadata: Record<string, unknown>,
  secretValues: Record<string, string>,
): Record<string, unknown> {
  return redactValue(metadata, secretValues) as Record<string, unknown>;
}

// ── Tests ──

describe("redactValue", () => {
  const secrets = { API_KEY: "sk-secret-123", DB_PASS: "p@ssw0rd" };

  test("redacts string that exactly matches a secret value", () => {
    expect(redactValue("sk-secret-123", secrets)).toBe("***");
    expect(redactValue("p@ssw0rd", secrets)).toBe("***");
  });

  test("does NOT redact string that contains secret as substring", () => {
    expect(redactValue("my-key-is-sk-secret-123-here", secrets)).toBe("my-key-is-sk-secret-123-here");
  });

  test("does not redact non-matching strings", () => {
    expect(redactValue("hello world", secrets)).toBe("hello world");
    expect(redactValue("", secrets)).toBe("");
  });

  test("passes through numbers unchanged", () => {
    expect(redactValue(42, secrets)).toBe(42);
    expect(redactValue(3.14, secrets)).toBe(3.14);
  });

  test("passes through booleans unchanged", () => {
    expect(redactValue(true, secrets)).toBe(true);
    expect(redactValue(false, secrets)).toBe(false);
  });

  test("passes through null unchanged", () => {
    expect(redactValue(null, secrets)).toBeNull();
  });

  test("passes through undefined unchanged", () => {
    expect(redactValue(undefined, secrets)).toBeUndefined();
  });

  test("redacts secrets inside arrays", () => {
    const input = ["sk-secret-123", "safe-value", 42];
    const result = redactValue(input, secrets);
    expect(result).toEqual(["***", "safe-value", 42]);
  });

  test("redacts secrets inside nested objects", () => {
    const input = {
      key: "sk-secret-123",
      nested: {
        password: "p@ssw0rd",
        safe: "hello",
      },
    };
    const result = redactValue(input, secrets);
    expect(result).toEqual({
      key: "***",
      nested: {
        password: "***",
        safe: "hello",
      },
    });
  });

  test("redacts secrets in deeply nested arrays of objects", () => {
    const input = {
      items: [
        { token: "sk-secret-123", name: "item1" },
        { token: "safe-token", name: "item2" },
      ],
    };
    const result = redactValue(input, secrets);
    expect(result).toEqual({
      items: [
        { token: "***", name: "item1" },
        { token: "safe-token", name: "item2" },
      ],
    });
  });

  test("handles empty object", () => {
    expect(redactValue({}, secrets)).toEqual({});
  });

  test("handles empty array", () => {
    expect(redactValue([], secrets)).toEqual([]);
  });

  test("handles empty secrets — nothing is redacted", () => {
    expect(redactValue("any-value", {})).toBe("any-value");
  });

  // ── Boundary tests ──

  test("passes through falsy number 0 unchanged", () => {
    expect(redactValue(0, secrets)).toBe(0);
  });

  test("空字符串 secret 值仍然脱敏为 ***", () => {
    // Empty string as a secret value would match any empty string input
    expect(redactValue("", { KEY: "" })).toBe("***");
  });

  test("handles deeply nested null values", () => {
    const input = { a: { b: { c: null } } };
    expect(redactValue(input, secrets)).toEqual({ a: { b: { c: null } } });
  });
});

describe("redactSecrets", () => {
  test("redacts metadata top-level fields", () => {
    const metadata = {
      apiKey: "sk-secret-123",
      name: "my-agent",
      version: 2,
    };
    const secrets = { API_KEY: "sk-secret-123" };

    const result = redactSecrets(metadata, secrets);
    expect(result).toEqual({
      apiKey: "***",
      name: "my-agent",
      version: 2,
    });
  });

  test("does not mutate original metadata", () => {
    const metadata = {
      apiKey: "sk-secret-123",
      nested: { password: "p@ssw0rd", safe: "hello" },
      list: [1, "sk-secret-123"],
    };
    const secrets = { API_KEY: "sk-secret-123", DB_PASS: "p@ssw0rd" };
    const originalSnapshot = JSON.parse(JSON.stringify(metadata));

    redactSecrets(metadata, secrets);

    // 深度比较：整个原始对象未被修改
    expect(metadata).toEqual(originalSnapshot);
    expect(metadata.apiKey).toBe("sk-secret-123");
    expect(metadata.nested.password).toBe("p@ssw0rd");
    expect(metadata.list).toEqual([1, "sk-secret-123"]);
  });

  test("returns new object (not same reference)", () => {
    const metadata = { name: "test" };
    const result = redactSecrets(metadata, {});
    expect(result).not.toBe(metadata);
    expect(result).toEqual(metadata);
  });

  test("handles metadata with no secrets", () => {
    const metadata = { name: "agent", count: 5 };
    const result = redactSecrets(metadata, { KEY: "secret" });
    expect(result).toEqual({ name: "agent", count: 5 });
  });

  // ── Boundary tests ──

  test("handles empty metadata object", () => {
    const result = redactSecrets({}, { KEY: "secret" });
    expect(result).toEqual({});
  });

  test("redacts when multiple secrets have the same value", () => {
    const metadata = { key1: "shared-secret", key2: "shared-secret", key3: "other" };
    const dupSecrets = { A: "shared-secret", B: "shared-secret" };
    const result = redactSecrets(metadata, dupSecrets);
    expect(result).toEqual({ key1: "***", key2: "***", key3: "other" });
  });
});
