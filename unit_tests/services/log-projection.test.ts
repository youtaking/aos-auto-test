// log-projection.test.ts — 日志投影字段裁剪与凭据脱敏测试
// 测试目标：redactLogText 的规则表与 projectLogLine 的字段投影/裁剪/裸文本回退
// 业务意图：对外日志只暴露六个字段，任何凭据形状的内容与超长字段都必须在出站前被处理，不存在解析失败旁路
// 源：packages/resources/observer/src/server/services/log-projection.ts（main a7f477a9e）

import { describe, expect, test } from "bun:test";

// ── 复制实现 ──

const REDACTION_MARKER = "[REDACTED]";
const TRUNCATION_SUFFIX = "…[truncated]";
const MAX_LINE_LENGTH = 8_000;
const SHORT_FIELD_LIMIT = 200;
const MESSAGE_FIELD_LIMIT = 2_000;
const STACK_FIELD_LIMIT = 4_000;

interface ProjectedLogEntry {
  timestamp: string | null;
  level: string | null;
  module: string | null;
  requestId: string | null;
  message: string;
  error: { type: string | null; message: string | null; stack: string | null } | null;
}

const REDACTION_RULES: readonly [RegExp, string][] = [
  [/(\b(?:set-cookie|cookie)\b\s*[:=]\s*)([^\n]+)/gi, `$1${REDACTION_MARKER}`],
  [/(\bbearer\s+|\bbasic\s+)[A-Za-z0-9._~+/=-]+/gi, `$1${REDACTION_MARKER}`],
  [/(\b[a-z][a-z0-9+.-]*:\/\/)[^\s/@:]+:[^\s/@]+@/gi, `$1${REDACTION_MARKER}@`],
  [
    /(\b(?:authorization|proxy-authorization|password|passwd|pwd|passphrase|secret|token|access[_-]?token|refresh[_-]?token|api[_-]?key|apikey|client[_-]?secret|private[_-]?key|credential)\b["']?\s*[:=]\s*["']?)([^\s"',;&)}\]]+)/gi,
    `$1${REDACTION_MARKER}`,
  ],
  [/\b(?:sk|pk|rk|ghp|gho|ghs|github_pat|xox[abpsr])[-_][A-Za-z0-9_-]{12,}/g, REDACTION_MARKER],
  [/\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}/g, REDACTION_MARKER],
];

function redactLogText(text: string): string {
  let redacted = text;
  for (const [pattern, replacement] of REDACTION_RULES) redacted = redacted.replace(pattern, replacement);
  return redacted;
}

function crop(text: string, limit: number): string {
  return text.length <= limit ? text : `${text.slice(0, limit)}${TRUNCATION_SUFFIX}`;
}

function projectedField(value: unknown, limit: number): string | null {
  if (typeof value !== "string" || value.length === 0) return null;
  return crop(redactLogText(value), limit);
}

function toRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function parseJsonObject(line: string): Record<string, unknown> | null {
  try {
    return toRecord(JSON.parse(line));
  } catch {
    return null;
  }
}

function projectLogLine(line: string): ProjectedLogEntry {
  const raw = line.slice(0, MAX_LINE_LENGTH);
  const record = parseJsonObject(raw);

  if (!record) {
    return {
      timestamp: null,
      level: null,
      module: null,
      requestId: null,
      message: crop(redactLogText(raw), MESSAGE_FIELD_LIMIT),
      error: null,
    };
  }

  const errorRecord = toRecord(record.err);

  return {
    timestamp: projectedField(record.time, SHORT_FIELD_LIMIT),
    level: projectedField(record.levelLabel ?? record.level, SHORT_FIELD_LIMIT),
    module: projectedField(record.module, SHORT_FIELD_LIMIT),
    requestId: projectedField(record.requestId, SHORT_FIELD_LIMIT),
    message: crop(redactLogText(typeof record.msg === "string" ? record.msg : raw), MESSAGE_FIELD_LIMIT),
    error: errorRecord
      ? {
          type: projectedField(errorRecord.type, SHORT_FIELD_LIMIT),
          message: projectedField(errorRecord.message, MESSAGE_FIELD_LIMIT),
          stack: projectedField(errorRecord.stack, STACK_FIELD_LIMIT),
        }
      : null,
  };
}

// ── tests ──

describe("redactLogText 凭据脱敏", () => {
  test("Cookie 整行值被抹掉", () => {
    expect(redactLogText("Cookie: a=1; b=2")).toBe("Cookie: [REDACTED]");
    expect(redactLogText("set-cookie=session=abc; path=/")).toBe("set-cookie=[REDACTED]");
  });

  test("Bearer / Basic 凭据被抹掉", () => {
    expect(redactLogText("Authorization: Bearer abc.def-123")).not.toContain("abc.def-123");
    expect(redactLogText("Authorization: Basic dXNlcjpwYXNz")).not.toContain("dXNlcjpwYXNz");
    expect(redactLogText("Bearer abc.def-123")).toBe("Bearer [REDACTED]");
  });

  test("URL 内 user:password 被抹掉并保留 scheme/host", () => {
    expect(redactLogText("connect postgres://user:pw@db:5432/x")).toBe("connect postgres://[REDACTED]@db:5432/x");
    expect(redactLogText("redis://user:secret@cache:6379")).toBe("redis://[REDACTED]@cache:6379");
  });

  test("键值形态凭据被抹掉", () => {
    for (const text of [
      "password=hunter2",
      "pwd: abc",
      'client_secret="s3cr3t"',
      "access_token=xyz",
      "?token=abc123",
      '"apiKey":"key-value"',
      "private-key=private-value",
    ]) {
      expect(redactLogText(text)).toContain(REDACTION_MARKER);
    }
  });

  test("已知前缀密钥与 JWT 按形状抹掉", () => {
    expect(redactLogText("key sk-abcdefghijklmnop")).toBe("key [REDACTED]");
    expect(redactLogText("token ghp_abcdefghijklmnop")).toContain(REDACTION_MARKER);
    expect(redactLogText("xoxb-1234567890-abcdef")).toBe("[REDACTED]");
    expect(
      redactLogText("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefgh"),
    ).toBe("[REDACTED]");
  });

  test("普通文本不误伤", () => {
    const text = "server started on port 8080, module=cluster";
    expect(redactLogText(text)).toBe(text);
  });
});

describe("projectLogLine 裸文本回退", () => {
  test("非 JSON 行进 message，其余字段为 null", () => {
    expect(projectLogLine("warn retry")).toEqual({
      timestamp: null,
      level: null,
      module: null,
      requestId: null,
      message: "warn retry",
      error: null,
    });
  });

  test("裸文本同样脱敏与裁剪", () => {
    const entry = projectLogLine(`token=secret-value ${"x".repeat(2100)}`);
    expect(entry.message).not.toContain("secret-value");
    expect(entry.message.length).toBe(MESSAGE_FIELD_LIMIT + TRUNCATION_SUFFIX.length);
  });

  test("JSON 数组与标量回退为裸文本", () => {
    for (const line of ["[1,2]", '"text"', "42", "null", "{broken"]) {
      const entry = projectLogLine(line);
      expect(entry.timestamp).toBeNull();
      expect(entry.message).toBe(line);
    }
  });
});

describe("projectLogLine 字段投影", () => {
  test("只输出六个字段且丢弃其它负载", () => {
    const entry = projectLogLine(
      JSON.stringify({
        time: "2026-01-01T00:00:00Z",
        levelLabel: "warn",
        level: 30,
        module: "cluster",
        requestId: "req-1",
        msg: "done",
        prompt: "user content",
        headers: { authorization: "Bearer secret" },
      }),
    );
    expect(entry).toEqual({
      timestamp: "2026-01-01T00:00:00Z",
      level: "warn",
      module: "cluster",
      requestId: "req-1",
      message: "done",
      error: null,
    });
    expect(Object.keys(entry).sort()).toEqual(["error", "level", "message", "module", "requestId", "timestamp"]);
  });

  test("levelLabel 缺失时取 level，非字符串归 null", () => {
    expect(projectLogLine(JSON.stringify({ level: "info" })).level).toBe("info");
    expect(projectLogLine(JSON.stringify({ level: 30 })).level).toBeNull();
    expect(projectLogLine(JSON.stringify({ level: "" })).level).toBeNull();
  });

  test("msg 缺失或非字符串时用原始行兜底", () => {
    const line = JSON.stringify({ level: "info", extra: 1 });
    expect(projectLogLine(line).message).toBe(redactLogText(line));
    const nonString = JSON.stringify({ msg: { nested: true } });
    expect(projectLogLine(nonString).message).toBe(nonString);
  });

  test("空串字段归 null", () => {
    const entry = projectLogLine(JSON.stringify({ time: "", module: "", requestId: "", msg: "" }));
    expect(entry.timestamp).toBeNull();
    expect(entry.module).toBeNull();
    expect(entry.requestId).toBeNull();
    expect(entry.message).toBe("");
  });

  test("错误对象投影三个字段并各自裁剪", () => {
    const entry = projectLogLine(
      JSON.stringify({
        msg: "failed",
        err: { type: "TypeError", message: "boom", stack: "s".repeat(STACK_FIELD_LIMIT + 10) },
      }),
    );
    expect(entry.error).toEqual({
      type: "TypeError",
      message: "boom",
      stack: `${"s".repeat(STACK_FIELD_LIMIT)}${TRUNCATION_SUFFIX}`,
    });
  });

  test("err 非对象时 error 为 null", () => {
    for (const err of [null, "text", 42, []]) {
      expect(projectLogLine(JSON.stringify({ msg: "x", err })).error).toBeNull();
    }
  });

  test("错误字段同样脱敏", () => {
    const entry = projectLogLine(
      JSON.stringify({ msg: "failed", err: { type: "Error", message: "password=hunter2" } }),
    );
    expect(entry.error!.message).not.toContain("hunter2");
    expect(entry.error!.message).toContain(REDACTION_MARKER);
  });

  test("超长行先截断到 8000 再解析", () => {
    const line = `{"msg":"${"a".repeat(MAX_LINE_LENGTH)}"}`;
    const entry = projectLogLine(line);
    expect(entry.message.length).toBe(MESSAGE_FIELD_LIMIT + TRUNCATION_SUFFIX.length);
  });

  test("短字段超过 200 字符被裁剪", () => {
    const entry = projectLogLine(JSON.stringify({ module: "m".repeat(250), msg: "x" }));
    expect(entry.module).toBe(`${"m".repeat(SHORT_FIELD_LIMIT)}${TRUNCATION_SUFFIX}`);
  });
});
