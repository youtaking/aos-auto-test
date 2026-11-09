// body-preview.test.ts — opensandbox-cluster HTTP 日志正文预览测试
// 测试目标：previewValue / previewBody 的大小上限、类型门控与不完整读取
// 业务意图：日志只记录有界且完整的 JSON；文件、流、超限正文与不可读响应一律省略，绝不半截输出
// 源：packages/opensandbox-cluster/src/logging/body-preview.ts（main 37ba68877）

import { describe, expect, test } from "bun:test";

// ── 复制实现 ──

const MAX_BYTES = 8192;

interface BodyPreview {
  data?: unknown;
  omitted?: string;
  bytes?: number;
}

interface BodySource {
  headers: Pick<Headers, "get">;
  body: unknown;
  clone(): { body: { getReader(): PreviewReader } | null };
}
interface PreviewReader {
  read(): Promise<{ done: true; value?: Uint8Array } | { done: false; value: Uint8Array }>;
  cancel(): Promise<unknown>;
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
  try {
    reader = source.clone().body?.getReader();
    if (!reader) return { omitted: "empty" };
    const chunks: Uint8Array[] = [];
    let bytes = 0;
    while (true) {
      const chunk = await reader.read();
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

const encoder = new TextEncoder();

function source(
  options: { headers?: Record<string, string>; chunks?: string[]; hasBody?: boolean } = {},
): BodySource {
  const headers = new Map(Object.entries(options.headers ?? {}).map(([key, value]) => [key.toLowerCase(), value]));
  return {
    headers: { get: (name) => headers.get(name.toLowerCase()) ?? null },
    body: options.hasBody === false ? null : {},
    clone() {
      let index = 0;
      const chunks = options.chunks ?? [];
      return {
        body: {
          getReader: () => ({
            read: async () =>
              index < chunks.length ? { done: false as const, value: encoder.encode(chunks[index++]) } : { done: true as const },
            cancel: async () => {},
          }),
        },
      };
    },
  };
}

// ── tests ──

describe("previewValue 类型门控", () => {
  test("null / undefined 视为空正文", () => {
    expect(previewValue(null)).toEqual({ omitted: "empty" });
    expect(previewValue(undefined)).toEqual({ omitted: "empty" });
  });

  test("普通对象与数组按 JSON 记录字节数", () => {
    expect(previewValue({ ok: true })).toEqual({ data: { ok: true }, bytes: 11 });
    expect(previewValue([1, 2])).toEqual({ data: [1, 2], bytes: 5 });
  });

  test("非普通对象与标量不当作 JSON 正文", () => {
    expect(previewValue("text")).toEqual({ omitted: "non_json_or_stream" });
    expect(previewValue(new Date(0))).toEqual({ omitted: "non_json_or_stream" });
    expect(previewValue(new Uint8Array(2))).toEqual({ omitted: "non_json_or_stream" });
  });

  test("序列化失败标记为不可读", () => {
    const circular: Record<string, unknown> = {};
    circular.self = circular;
    expect(previewValue(circular)).toEqual({ omitted: "unreadable" });
  });

  test("超过 8192 字节时只报告大小，不返回正文", () => {
    const preview = previewValue({ text: "x".repeat(MAX_BYTES) });
    expect(preview.omitted).toBe("too_large");
    expect(preview.bytes).toBeGreaterThan(MAX_BYTES);
    expect(preview.data).toBeUndefined();
  });
});

describe("previewBody 读取门控", () => {
  test("无正文返回 empty", async () => {
    expect(await previewBody(source({ hasBody: false }))).toEqual({ omitted: "empty" });
  });

  test("附件、分块流与非 JSON 正文全部省略", async () => {
    expect(
      await previewBody(source({ headers: { "content-disposition": "attachment; filename=a.json" } })),
    ).toEqual({ omitted: "file" });
    expect(await previewBody(source({ headers: { "transfer-encoding": "chunked" } }))).toEqual({
      omitted: "stream",
    });
    expect(await previewBody(source({ headers: { "content-type": "text/plain" } }))).toEqual({
      omitted: "non_json_or_stream",
    });
  });

  test("content-length 超限时不读取正文", async () => {
    expect(
      await previewBody(source({ headers: { "content-type": "application/json", "content-length": "9000" } })),
    ).toEqual({ omitted: "too_large", bytes: 9000 });
  });

  test("合法 JSON 正文按真实字节数返回", async () => {
    const preview = await previewBody(
      source({ headers: { "content-type": "application/json; charset=utf-8" }, chunks: ['{"ok":true}'] }),
    );
    expect(preview).toEqual({ data: { ok: true }, bytes: 11 });
  });

  test("JSON 语法错误返回 invalid_json，空正文返回 empty", async () => {
    expect(
      await previewBody(source({ headers: { "content-type": "application/json" }, chunks: ["not-json"] })),
    ).toEqual({ omitted: "invalid_json" });
    expect(await previewBody(source({ headers: { "content-type": "application/json" } }))).toEqual({
      omitted: "empty",
    });
  });
});
