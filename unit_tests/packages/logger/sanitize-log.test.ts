// sanitize-log.test.ts — 日志脱敏纯函数测试
// 测试目标：isSensitiveLogKey / sanitizeLogText / sanitizeLogValue
// 业务意图：确保凭据、连接串、查询参数、数据库错误与深层结构不会出现在日志中
// 源：packages/logger/src/sanitize.ts（main a7f477a9e）

import { describe, expect, test } from "bun:test";

// ── 复制实现 ──

const DIAGNOSTIC_KEYS = new Set([
  "payload_bytes",
  "payload_type",
  "payload_size",
  "payload_count",
  "payload_length",
  "payload_duration_ms",
  "body_size",
  "content_length",
  "query_duration_ms",
  "token_count",
  "error_count",
  "retry_delay_ms",
]);

const DIAGNOSTIC_KEYS_COMPACT = new Set([...DIAGNOSTIC_KEYS].map((key) => key.replaceAll("_", "")));

const SENSITIVE_CONTAINS =
  /(?:authorization|cookie|credential|password|passwd|pwd|passphrase|secret|token|apikey|(?:access|account|private|signing|encryption|sharedaccess)key|prompt|completion|payload|bodies|body|param|query|statement|sql|dsn|args|content|connectionstring|(?:database|redis|mongo(?:db)?|mysql|postgres(?:ql)?|amqp|rabbitmq)(?:url|uri))/;

function isSensitiveLogKey(key: string): boolean {
  const normalized = key
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1_$2")
    .replace(/[^A-Za-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase();
  if (!normalized) return false;
  const compact = normalized.replaceAll("_", "");
  if (DIAGNOSTIC_KEYS.has(normalized) || DIAGNOSTIC_KEYS_COMPACT.has(compact)) return false;
  return SENSITIVE_CONTAINS.test(compact);
}

function sanitizeLogText(value: string, limit = 2048): string {
  const clean = value
    .replace(/(?:postgres(?:ql)?|redis|rediss):\/\/[^\s"'<>]+/gi, "[REDACTED_CONNECTION]")
    .replace(/(\b[a-z][a-z0-9+.-]*:\/\/)[^\s/@:]+:[^\s/@]+@/gi, "$1[REDACTED]@")
    .replace(/(https?:\/\/)(?:[^\s/@]+@)?([^\s/?#]+)([^\s?#]*)(?:\?[^\s#]*)?(?:#[^\s]*)?/gi, "$1$2$3")
    .replace(
      /\{env:[A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASSWD|API_?KEY|CREDENTIAL|PRIVATE_KEY)[A-Z0-9_]*\}/gi,
      "[REDACTED_ENV_REF]",
    )
    .replace(/\b(Bearer|Basic)\s+[A-Za-z0-9+/=_\-.]+/gi, "$1 [REDACTED]")
    .replace(/((?:set-cookie|cookie)\s*[=:]\s*)[^\n]+/gi, "$1[REDACTED]")
    .replace(
      /((?:authorization|proxy-authorization|token|access[_-]?token|refresh[_-]?token|id[_-]?token|password|passwd|pwd|passphrase|secret|client[_-]?secret|api[_-]?key|apikey|(?:access|account|private|secret|signing|shared[_-]?access)_?key|credential|connection[_-]?string|dsn|cookie)["']?\s*[=:]\s*["']?)[^\s"',;]+/gi,
      "$1[REDACTED]",
    )
    .replace(
      /(\b[A-Z][A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASSWD|API_?KEY|CREDENTIAL|PRIVATE_KEY)[A-Z0-9_]*\s*[=:]\s*)[^\s"',;]+/g,
      "$1[REDACTED]",
    );
  return clean.length > limit ? `${clean.slice(0, limit)}…[truncated:${clean.length}]` : clean;
}

function sanitizeLogValue(value: unknown, key = "", depth = 0, seen = new WeakSet<object>()): unknown {
  if (isSensitiveLogKey(key)) return "[REDACTED]";
  if (typeof value === "string")
    return sanitizeLogText(value, key === "msg" || key === "message" || key === "stack" ? 8192 : 2048);
  if (value === null || typeof value === "number" || typeof value === "boolean") return value;
  if (value === undefined) return;
  if (typeof value !== "object") return sanitizeLogText(String(value));
  if (seen.has(value)) return "[Circular]";
  if (depth >= 5) return "[DepthLimit]";
  seen.add(value);
  if (value instanceof Error) {
    const dbError = value.name === "DrizzleQueryError" || "query" in value || "params" in value;
    return {
      type: value.name,
      message: dbError ? "Database operation failed" : sanitizeLogText(value.message),
      stack: dbError ? undefined : sanitizeLogText(value.stack ?? "", 8192),
      code:
        "code" in value && typeof value.code === "string" && /^[A-Z0-9_]{1,32}$/.test(value.code)
          ? value.code
          : undefined,
    };
  }
  if (Array.isArray(value)) return value.slice(0, 32).map((item) => sanitizeLogValue(item, "", depth + 1, seen));
  return Object.fromEntries(
    Object.entries(value)
      .slice(0, 32)
      .map(([name, item]) => [name.slice(0, 128), sanitizeLogValue(item, name, depth + 1, seen)]),
  );
}

// ── tests ──

describe("isSensitiveLogKey 字段名识别", () => {
  test("凭据类字段命中", () => {
    for (const key of ["password", "passwd", "pwd", "secret", "token", "apiKey", "authorization", "cookie"]) {
      expect(isSensitiveLogKey(key)).toBe(true);
    }
  });

  test("camelCase 与缩写边界被拆分后识别", () => {
    expect(isSensitiveLogKey("DBPassword")).toBe(true);
    expect(isSensitiveLogKey("clientSecret")).toBe(true);
  });

  test("正文/查询类字段命中", () => {
    for (const key of ["prompt", "completion", "payload", "sql", "dsn", "args", "content"]) {
      expect(isSensitiveLogKey(key)).toBe(true);
    }
  });

  test("连接串类字段命中", () => {
    expect(isSensitiveLogKey("databaseUrl")).toBe(true);
    expect(isSensitiveLogKey("redisURI")).toBe(true);
    expect(isSensitiveLogKey("postgresql_url")).toBe(true);
  });

  test("诊断字段白名单不误伤", () => {
    for (const key of ["payload_bytes", "body_size", "content_length", "token_count", "error_count", "query_duration_ms"]) {
      expect(isSensitiveLogKey(key)).toBe(false);
    }
  });

  test("紧凑形式诊断字段同样放行", () => {
    expect(isSensitiveLogKey("PAYLOADBYTES")).toBe(false);
    expect(isSensitiveLogKey("TOKENCOUNT")).toBe(false);
    expect(isSensitiveLogKey("bodySize")).toBe(false);
  });

  test("普通字段不命中", () => {
    for (const key of ["name", "status", "duration", "method", "requestId"]) {
      expect(isSensitiveLogKey(key)).toBe(false);
    }
  });

  test("空键与纯符号键不命中", () => {
    expect(isSensitiveLogKey("")).toBe(false);
    expect(isSensitiveLogKey("---")).toBe(false);
  });
});

describe("sanitizeLogText 自由文本脱敏", () => {
  test("数据库连接串整体替换", () => {
    expect(sanitizeLogText("connect postgres://u:p@db:5432/x now")).toBe(
      "connect [REDACTED_CONNECTION] now",
    );
    expect(sanitizeLogText("redis://user:pass@cache:6379")).toBe("[REDACTED_CONNECTION]");
  });

  test("其它 scheme 的 user:password@ 保留 scheme", () => {
    expect(sanitizeLogText("amqp://bob:hunter2@mq:5672/vhost")).toBe("amqp://[REDACTED]@mq:5672/vhost");
  });

  test("HTTP URL 去掉查询串与用户信息", () => {
    expect(sanitizeLogText("https://alice:pw@example.com/path?token=abc#frag")).toBe(
      "https://example.com/path",
    );
  });

  test("环境变量密钥占位符被替换", () => {
    expect(sanitizeLogText("key={env:RCS_SECRET_KEY}")).toBe("key=[REDACTED_ENV_REF]");
    expect(sanitizeLogText("{env:LANGFUSE_API_KEY}")).toBe("[REDACTED_ENV_REF]");
  });

  test("Bearer/Basic 认证值被替换", () => {
    expect(sanitizeLogText("Bearer abc.def-123")).toBe("Bearer [REDACTED]");
    expect(sanitizeLogText("Basic dXNlcjpwYXNz")).toBe("Basic [REDACTED]");
  });

  test("Cookie 头整行被替换", () => {
    expect(sanitizeLogText("cookie: session=abc; theme=dark")).toBe("cookie: [REDACTED]");
  });

  test("key=value 形式的敏感值被替换", () => {
    expect(sanitizeLogText("password=hunter2 user=bob")).toBe("password=[REDACTED] user=bob");
    expect(sanitizeLogText('api_key="sk-123"')).toBe('api_key="[REDACTED]"');
  });

  test("大写环境变量赋值被替换", () => {
    expect(sanitizeLogText("RCS_SECRET_KEY=abc123 next=1")).toBe("RCS_SECRET_KEY=[REDACTED] next=1");
  });

  test("普通短文本原样返回", () => {
    expect(sanitizeLogText("HTTP 响应 method=GET status=200")).toBe("HTTP 响应 method=GET status=200");
  });

  test("超长文本按 limit 截断并标注原长", () => {
    const value = "a".repeat(30);
    expect(sanitizeLogText(value, 10)).toBe(`aaaaaaaaaa…[truncated:30]`);
  });

  test("恰好等于 limit 不截断", () => {
    const value = "a".repeat(10);
    expect(sanitizeLogText(value, 10)).toBe(value);
  });
});

describe("sanitizeLogValue 结构脱敏", () => {
  test("敏感键直接替换为 [REDACTED]", () => {
    expect(sanitizeLogValue({ password: "x", name: "ok" })).toEqual({ password: "[REDACTED]", name: "ok" });
  });

  test("字符串值按 msg/message/stack 使用更大上限", () => {
    const long = "a".repeat(3000);
    const result = sanitizeLogValue({ msg: long, detail: long }) as Record<string, string>;
    expect(result.msg.length).toBe(3000);
    expect(result.detail).toContain("…[truncated:3000]");
  });

  test("基础类型原样返回", () => {
    expect(sanitizeLogValue(null)).toBeNull();
    expect(sanitizeLogValue(42)).toBe(42);
    expect(sanitizeLogValue(false)).toBe(false);
  });

  test("undefined 返回 undefined", () => {
    expect(sanitizeLogValue(undefined)).toBeUndefined();
  });

  test("非对象原始值转为脱敏字符串", () => {
    expect(sanitizeLogValue(10n)).toBe("10");
    expect(sanitizeLogValue(Symbol("s"))).toBe("Symbol(s)");
  });

  test("循环引用标记为 [Circular]", () => {
    const node: Record<string, unknown> = {};
    node.self = node;
    expect(sanitizeLogValue(node)).toEqual({ self: "[Circular]" });
  });

  test("超过 5 层返回 [DepthLimit]", () => {
    const root: Record<string, unknown> = {};
    let cursor = root;
    for (let i = 0; i < 6; i++) {
      const next: Record<string, unknown> = {};
      cursor.child = next;
      cursor = next;
    }
    let value: unknown = sanitizeLogValue(root);
    let depth = 0;
    while (value && typeof value === "object" && "child" in (value as object)) {
      value = (value as Record<string, unknown>).child;
      depth++;
    }
    expect(depth).toBe(5);
    expect(value).toBe("[DepthLimit]");
  });

  test("普通 Error 保留 type/message/stack", () => {
    const err = new Error("boom");
    err.name = "CustomError";
    expect(sanitizeLogValue(err)).toEqual({
      type: "CustomError",
      message: "boom",
      stack: expect.any(String),
      code: undefined,
    });
  });

  test("大写错误码保留，小写丢弃", () => {
    const upper = Object.assign(new Error("x"), { code: "PASSWORD_AUTH_FAILED" });
    const lower = Object.assign(new Error("y"), { code: "err_123" });
    expect((sanitizeLogValue(upper) as { code?: string }).code).toBe("PASSWORD_AUTH_FAILED");
    expect((sanitizeLogValue(lower) as { code?: string }).code).toBeUndefined();
  });

  test("数据库错误脱敏为固定文案且不含 stack", () => {
    const err = Object.assign(new Error('select * from users where password="p"'), {
      name: "DrizzleQueryError",
      query: "select 1",
      params: ["x"],
    });
    expect(sanitizeLogValue(err)).toEqual({
      type: "DrizzleQueryError",
      message: "Database operation failed",
      stack: undefined,
      code: undefined,
    });
  });

  test("带 query 属性的错误同样按数据库错误处理", () => {
    const err = Object.assign(new Error("query failed: select 1"), { query: "select 1" });
    expect((sanitizeLogValue(err) as { message: string }).message).toBe("Database operation failed");
  });

  test("Error 的 message 中的连接串被脱敏", () => {
    const err = new Error("cannot connect postgres://u:p@h/db");
    expect((sanitizeLogValue(err) as { message: string }).message).toBe("cannot connect [REDACTED_CONNECTION]");
  });

  test("数组最多保留 32 项", () => {
    const result = sanitizeLogValue(Array.from({ length: 40 }, (_, i) => i)) as number[];
    expect(result).toHaveLength(32);
    expect(result[31]).toBe(31);
  });

  test("对象最多保留 32 个字段且键名截断到 128", () => {
    const obj: Record<string, unknown> = {};
    for (let i = 0; i < 40; i++) obj[`k${i}`] = i;
    expect(Object.keys(sanitizeLogValue(obj) as object)).toHaveLength(32);

    const longKey = "x".repeat(200);
    const sanitized = sanitizeLogValue({ [longKey]: 1 }) as Record<string, unknown>;
    expect(Object.keys(sanitized)[0]!.length).toBe(128);
  });

  test("嵌套对象中的敏感键也被替换", () => {
    expect(sanitizeLogValue({ outer: { token: "abc", ok: 1 } })).toEqual({
      outer: { token: "[REDACTED]", ok: 1 },
    });
  });
});
