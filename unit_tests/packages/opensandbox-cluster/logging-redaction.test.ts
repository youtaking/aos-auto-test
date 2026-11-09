// logging-redaction.test.ts — cluster 日志脱敏与正文预览测试
// 测试目标：redactLogValue、previewBody、previewValue
// 业务意图：部署密钥/凭据/数据库参数不落日志，响应正文读取有界且不消耗业务流
// 源：packages/opensandbox-cluster/src/logging/redact.ts、body-preview.ts（main a7f477a9e）

import { describe, expect, test } from "bun:test";
import { isSensitiveLogKey, sanitizeLogValue } from "@fenix/logger/sanitize";

// ── 复制 redactLogValue（共享脱敏规则直接复用真实实现） ──

function redactLogValue(value: unknown, secrets: readonly string[]): unknown {
  const masks = [...new Set(secrets.filter(Boolean).flatMap((secret) => [secret, encodeURIComponent(secret)]))];
  const mask = (text: string) => {
    for (const secret of masks) text = text.replaceAll(secret, "[REDACTED]");
    return text;
  };
  const seen = new WeakSet<object>();
  const visit = (item: unknown, key = "", depth = 0): unknown => {
    if (isSensitiveLogKey(key) || /^(?:env|environment|metadata|entrypoint|command|stdin)$/i.test(key))
      return "[REDACTED]";
    if (typeof item === "string") return mask(item);
    if (!item || typeof item !== "object") return item;
    if (seen.has(item)) return "[Circular]";
    if (depth >= 5) return "[DepthLimit]";
    seen.add(item);
    if (item instanceof Error) {
      const copy = new Error(mask(item.message));
      copy.name = mask(item.name);
      copy.stack = mask(item.stack ?? "");
      if ("query" in item) Object.assign(copy, { query: "[REDACTED]" });
      if ("params" in item) Object.assign(copy, { params: [] });
      if ("code" in item && typeof item.code === "string") Object.assign(copy, { code: mask(item.code) });
      return copy;
    }
    if (Array.isArray(item)) return item.slice(0, 32).map((entry) => visit(entry, "", depth + 1));
    return Object.fromEntries(
      Object.entries(item)
        .slice(0, 32)
        .map(([name, entry]) => [mask(name), visit(entry, name, depth + 1)]),
    );
  };
  return sanitizeLogValue(visit(value));
}

// ── 复制 body-preview ──

const MAX_BYTES = 8192;
const READ_TIMEOUT_MS = 75;

interface BodyPreview {
  data?: unknown;
  omitted?: string;
  bytes?: number;
}

interface PreviewReader {
  read(): Promise<{ done: true; value?: Uint8Array } | { done: false; value: Uint8Array }>;
  cancel(): Promise<unknown>;
}

interface BodySource {
  headers: Pick<Headers, "get">;
  body: unknown;
  clone(): { body: { getReader(): PreviewReader } | null };
}

async function previewBody(source: BodySource): Promise<BodyPreview> {
  if (!source.body) return { omitted: "empty" };
  if (source.headers.get("content-disposition")?.includes("attachment")) return { omitted: "file" };
  const mime = source.headers.get("content-type") ?? "";
  if (source.headers.get("transfer-encoding")?.toLowerCase().includes("chunked")) return { omitted: "stream" };
  if (!/^application\/(?:[a-z0-9!#$&^_.+-]+\+)?json(?:;|$)/i.test(mime)) return { omitted: "non_json_or_stream" };
  const length = Number(source.headers.get("content-length"));
  if (length > MAX_BYTES) return { omitted: "too_large", bytes: length };
  let reader: PreviewReader | undefined;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const expired = Symbol("expired");
  const deadline = new Promise<typeof expired>((resolve) => {
    timer = setTimeout(() => resolve(expired), READ_TIMEOUT_MS);
  });
  try {
    reader = source.clone().body?.getReader();
    if (!reader) return { omitted: "empty" };
    const chunks: Uint8Array[] = [];
    let bytes = 0;
    while (true) {
      const chunk = await Promise.race([reader.read(), deadline]);
      if (chunk === expired) return { omitted: "read_timeout" };
      if (chunk.done) break;
      bytes += chunk.value.byteLength;
      if (bytes > MAX_BYTES) return { omitted: "too_large", bytes };
      chunks.push(chunk.value);
    }
    if (!bytes) return { omitted: "empty" };
    const buffer = new Uint8Array(bytes);
    let offset = 0;
    for (const chunk of chunks) {
      buffer.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return { data: JSON.parse(new TextDecoder().decode(buffer)), bytes };
  } catch (error) {
    return { omitted: error instanceof SyntaxError ? "invalid_json" : "unreadable" };
  } finally {
    clearTimeout(timer);
    void reader?.cancel().catch(() => {});
  }
}

function previewValue(value: unknown): BodyPreview {
  if (value === undefined || value === null) return { omitted: "empty" };
  if (typeof value !== "object" || (!Array.isArray(value) && Object.getPrototypeOf(value) !== Object.prototype))
    return { omitted: "non_json_or_stream" };
  try {
    const text = JSON.stringify(value);
    const bytes = new TextEncoder().encode(text).byteLength;
    return bytes > MAX_BYTES ? { omitted: "too_large", bytes } : { data: value, bytes };
  } catch {
    return { omitted: "unreadable" };
  }
}

// ── 辅助 ──

function source(options: {
  headers?: Record<string, string>;
  body?: unknown;
  reader?: PreviewReader;
}): BodySource {
  return {
    headers: new Headers(options.headers ?? {}),
    body: "body" in options ? options.body : {},
    clone: () => ({ body: options.reader ? { getReader: () => options.reader! } : null }),
  };
}

function readerOf(chunks: Uint8Array[], overrides: Partial<PreviewReader> = {}): PreviewReader {
  let index = 0;
  return {
    read: async () => {
      if (index >= chunks.length) return { done: true };
      return { done: false, value: chunks[index++]! };
    },
    cancel: async () => {},
    ...overrides,
  };
}

const encoder = new TextEncoder();

// ── tests ──

describe("redactLogValue 部署密钥脱敏", () => {
  test("字符串中的部署密钥被遮蔽", () => {
    const secret = "abcdefghijklmnopqrstuvwxyz012345";
    const text = JSON.stringify(redactLogValue({ path: `/tmp/${secret}/x` }, [secret]));
    expect(text).not.toContain(secret);
    expect(text).toContain("[REDACTED]");
  });

  test("截断边界前的密钥同样先遮蔽", () => {
    const secret = "abcdefghijklmnopqrstuvwxyz012345";
    for (const value of [
      new Error("x".repeat(2017) + secret),
      { message: "x".repeat(2017) + secret },
      { value: "x".repeat(2017) + secret },
    ]) {
      const text = JSON.stringify(redactLogValue(value, [secret]));
      expect(text).not.toContain(secret.slice(0, 24));
      expect(text).toContain("[REDACTED]");
    }
  });

  test("URL 编码形式的密钥也被遮蔽", () => {
    const secret = "example/secret+value";
    expect(JSON.stringify(redactLogValue({ path: encodeURIComponent(secret) }, [secret]))).not.toContain(
      encodeURIComponent(secret),
    );
  });

  test("空密钥被忽略", () => {
    expect(redactLogValue({ value: "plain" }, ["", "  "])).toEqual({ value: "plain" });
  });

  test("敏感键与沙箱不透明输入被整体替换", () => {
    const result = redactLogValue(
      {
        api_key: "key-secret",
        environment: { CUSTOM: "env-secret" },
        metadata: { a: 1 },
        entrypoint: ["sh"],
        command: "run",
        stdin: "input",
      },
      [],
    ) as Record<string, unknown>;
    for (const key of ["api_key", "environment", "metadata", "entrypoint", "command", "stdin"])
      expect(result[key]).toBe("[REDACTED]");
  });

  test("嵌套对象中的敏感键被替换，普通字段保留", () => {
    expect(redactLogValue({ sandbox: { image: { auth: { password: "registry-secret" } }, cpu: 0.5 } }, [])).toEqual({
      sandbox: { image: { auth: { password: "[REDACTED]" } }, cpu: 0.5 },
    });
  });

  test("数据库错误的 SQL 与参数不泄露", () => {
    const error = Object.assign(new Error("INSERT INTO table VALUES(database-secret)"), {
      query: "INSERT",
      params: ["database-secret"],
    });
    const result = redactLogValue({ error }, []) as { error: Record<string, unknown> };
    const text = JSON.stringify(result);
    expect(text).not.toContain("database-secret");
    expect(result.error.message).toBe("Database operation failed");
    expect(result.error).not.toHaveProperty("query");
    expect(result.error).not.toHaveProperty("params");
  });

  test("错误对象携带的部署密钥在重建前被遮蔽", () => {
    const secret = "deploy-secret-value";
    const error = new Error(`connect failed with ${secret}`);
    const result = redactLogValue(error, [secret]) as Error;
    expect(result.message).not.toContain(secret);
    expect(result.message).toContain("[REDACTED]");
  });

  test("循环引用与深度上限", () => {
    const node: Record<string, unknown> = { value: "x" };
    node.self = node;
    expect(redactLogValue(node, [])).toEqual({ value: "x", self: "[Circular]" });

    const root: Record<string, unknown> = {};
    let cursor = root;
    for (let i = 0; i < 6; i++) {
      const next: Record<string, unknown> = {};
      cursor.child = next;
      cursor = next;
    }
    let value: unknown = redactLogValue(root, []);
    let depth = 0;
    while (value && typeof value === "object" && "child" in (value as object)) {
      value = (value as Record<string, unknown>).child;
      depth++;
    }
    expect(depth).toBe(5);
    expect(value).toBe("[DepthLimit]");
  });

  test("对象键名中的密钥也被遮蔽", () => {
    const secret = "key-name-secret";
    const result = redactLogValue({ [`prefix-${secret}`]: 1 }, [secret]) as Record<string, unknown>;
    expect(Object.keys(result)).toEqual(["prefix-[REDACTED]"]);
  });
});

describe("previewBody 正文预览", () => {
  test("无 body 时 omitted=empty", async () => {
    expect(await previewBody(source({ body: null }))).toEqual({ omitted: "empty" });
  });

  test("附件响应 omitted=file", async () => {
    expect(
      await previewBody(source({ headers: { "content-disposition": "attachment; filename=x" } })),
    ).toEqual({ omitted: "file" });
  });

  test("分块传输 omitted=stream", async () => {
    expect(await previewBody(source({ headers: { "transfer-encoding": "Chunked" } }))).toEqual({
      omitted: "stream",
    });
  });

  test("非 JSON 媒体类型 omitted=non_json_or_stream", async () => {
    for (const contentType of ["text/event-stream", "application/toml", "text/plain", ""]) {
      expect(await previewBody(source({ headers: { "content-type": contentType } }))).toEqual({
        omitted: "non_json_or_stream",
      });
    }
  });

  test("JSON 后缀媒体类型被接受", async () => {
    const reader = readerOf([encoder.encode('{"a":1}')]);
    expect(
      await previewBody(
        source({ headers: { "content-type": "application/problem+json; charset=utf-8" }, reader }),
      ),
    ).toEqual({ data: { a: 1 }, bytes: 7 });
  });

  test("content-length 超限直接 omitted=too_large", async () => {
    expect(
      await previewBody(
        source({
          headers: { "content-type": "application/json", "content-length": String(MAX_BYTES + 1) },
          reader: readerOf([encoder.encode("{}")]),
        }),
      ),
    ).toEqual({ omitted: "too_large", bytes: MAX_BYTES + 1 });
  });

  test("分块读取后拼接为完整 JSON", async () => {
    const reader = readerOf([encoder.encode('{"a":'), encoder.encode("1}")]);
    expect(await previewBody(source({ headers: { "content-type": "application/json" }, reader }))).toEqual({
      data: { a: 1 },
      bytes: 7,
    });
  });

  test("无克隆 body 时 omitted=empty", async () => {
    expect(await previewBody(source({ headers: { "content-type": "application/json" } }))).toEqual({
      omitted: "empty",
    });
  });

  test("读取到零字节时 omitted=empty", async () => {
    expect(
      await previewBody(source({ headers: { "content-type": "application/json" }, reader: readerOf([]) })),
    ).toEqual({ omitted: "empty" });
  });

  test("流式累计超限 omitted=too_large", async () => {
    const chunk = new Uint8Array(5000).fill(97);
    const result = await previewBody(
      source({ headers: { "content-type": "application/json" }, reader: readerOf([chunk, chunk]) }),
    );
    expect(result).toEqual({ omitted: "too_large", bytes: 10000 });
  });

  test("非法 JSON omitted=invalid_json", async () => {
    const reader = readerOf([encoder.encode("{not json")]);
    expect(await previewBody(source({ headers: { "content-type": "application/json" }, reader }))).toEqual({
      omitted: "invalid_json",
    });
  });

  test("读取异常 omitted=unreadable", async () => {
    const reader = readerOf([], {
      read: async () => {
        throw new Error("network");
      },
    });
    expect(await previewBody(source({ headers: { "content-type": "application/json" }, reader }))).toEqual({
      omitted: "unreadable",
    });
  });

  test("读取超时 omitted=read_timeout", async () => {
    const reader: PreviewReader = {
      read: () => new Promise(() => {}),
      cancel: async () => {},
    };
    expect(await previewBody(source({ headers: { "content-type": "application/json" }, reader }))).toEqual({
      omitted: "read_timeout",
    });
  });

  test("总是取消克隆读取器，避免挂起原流", async () => {
    let cancelled = 0;
    const reader = readerOf([encoder.encode("{}")], {
      cancel: async () => {
        cancelled++;
      },
    });
    await previewBody(source({ headers: { "content-type": "application/json" }, reader }));
    expect(cancelled).toBe(1);
  });
});

describe("previewValue 内存值预览", () => {
  test("undefined/null omitted=empty", () => {
    expect(previewValue(undefined)).toEqual({ omitted: "empty" });
    expect(previewValue(null)).toEqual({ omitted: "empty" });
  });

  test("普通对象与数组返回数据与字节数", () => {
    expect(previewValue({ a: 1 })).toEqual({ data: { a: 1 }, bytes: 7 });
    expect(previewValue([1, 2])).toEqual({ data: [1, 2], bytes: 5 });
  });

  test("非普通对象 omitted=non_json_or_stream", () => {
    for (const value of [new Date(), new Map(), new (class X {})(), "text", 42]) {
      expect(previewValue(value)).toEqual({ omitted: "non_json_or_stream" });
    }
  });

  test("超过上限 omitted=too_large 并给出字节数", () => {
    const value = { text: "x".repeat(9000) };
    const result = previewValue(value);
    expect(result.omitted).toBe("too_large");
    expect(result.bytes).toBeGreaterThan(MAX_BYTES);
  });

  test("无法序列化 omitted=unreadable", () => {
    const value: Record<string, unknown> = {};
    value.self = value;
    expect(previewValue(value)).toEqual({ omitted: "unreadable" });
  });
});
