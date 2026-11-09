// native-create-error.test.ts — 原生创建失败诊断脱敏测试
// 测试目标：nativeCreateError 的消息提取优先级、密钥/URL/控制字符处理与长度上限
// 业务意图：节点错误可能带认证 URL 或凭据参数，回给调用方的诊断不得泄露，也不得按措辞分类失败
// 源：packages/opensandbox-cluster/src/services/native-create-error.ts（main a7f477a9e）

import { describe, expect, test } from "bun:test";

// ── 复制实现 ──

async function nativeCreateError(response: Pick<Response, "status" | "json">, secrets: string[] = []) {
  let message = `native create HTTP ${response.status}`;
  try {
    const value = (await response.json()) as {
      detail?: { code?: unknown; message?: unknown };
      error?: { code?: unknown; message?: unknown };
      code?: unknown;
      message?: unknown;
    } | null;
    const detail = value?.detail ?? value?.error ?? value;
    if (typeof detail?.message === "string") message = detail.message;
  } catch (error) {
    if (!(error instanceof SyntaxError)) throw error;
  }
  for (const secret of secrets) if (secret) message = message.replaceAll(secret, "[redacted]");
  message = Array.from(message.replace(/https?:\/\/\S+/g, "[node URL]"), (character) =>
    character.charCodeAt(0) < 32 ? " " : character,
  )
    .join("")
    .slice(0, 500);
  return { message };
}

function responseOf(body: unknown, status = 400): Pick<Response, "status" | "json"> {
  return {
    status,
    json: async () => body,
  };
}

function failingResponse(error: Error, status = 500): Pick<Response, "status" | "json"> {
  return {
    status,
    json: async () => {
      throw error;
    },
  };
}

// ── tests ──

describe("nativeCreateError 消息提取", () => {
  test("优先取 detail.message", async () => {
    await expect(
      nativeCreateError(responseOf({ detail: { message: "detail said" }, error: { message: "err" }, message: "top" })),
    ).resolves.toEqual({ message: "detail said" });
  });

  test("其次取 error.message", async () => {
    await expect(nativeCreateError(responseOf({ error: { message: "err said" }, message: "top" }))).resolves.toEqual({
      message: "err said",
    });
  });

  test("再次取顶层 message", async () => {
    await expect(nativeCreateError(responseOf({ message: "top said" }))).resolves.toEqual({ message: "top said" });
  });

  test("缺少可用 message 时回退状态码", async () => {
    for (const body of [null, {}, { message: 42 }, { detail: {} }, { error: { message: null } }]) {
      await expect(nativeCreateError(responseOf(body, 503))).resolves.toEqual({
        message: "native create HTTP 503",
      });
    }
  });

  test("JSON 语法错误按回退处理，其它异常继续抛出", async () => {
    await expect(nativeCreateError(failingResponse(new SyntaxError("bad json")))).resolves.toEqual({
      message: "native create HTTP 500",
    });
    await expect(nativeCreateError(failingResponse(new TypeError("socket closed")))).rejects.toThrow("socket closed");
  });
});

describe("nativeCreateError 脱敏与清洗", () => {
  test("部署密钥以 [redacted] 替换，空密钥忽略", async () => {
    const result = await nativeCreateError(
      responseOf({ message: "pull failed for secret-key-1 and secret-key-2" }),
      ["", "secret-key-1", "secret-key-2"],
    );
    expect(result.message).toBe("pull failed for [redacted] and [redacted]");
  });

  test("HTTP(S) URL 整体替换为 [node URL]", async () => {
    const result = await nativeCreateError(
      responseOf({
        message: "failed to pull https://user:pw@registry.example.com/v2/image:tag while contacting http://node:8080/x",
      }),
    );
    expect(result.message).toBe("failed to pull [node URL] while contacting [node URL]");
  });

  test("控制字符替换为空格，普通字符保留", async () => {
    const message =
      "a" + String.fromCharCode(10) + "b" + String.fromCharCode(9) + "c" + String.fromCharCode(0) + "d e fg";
    const result = await nativeCreateError(responseOf({ message }));
    expect(result.message).toBe("a b c d e fg");
  });

  test("先脱敏再截断，截断到 500 字符", async () => {
    const secret = "very-secret-token";
    const result = await nativeCreateError(responseOf({ message: `${secret}${"x".repeat(600)}` }), [secret]);
    expect(result.message).toHaveLength(500);
    expect(result.message.startsWith("[redacted]")).toBe(true);
    expect(result.message).not.toContain(secret);
  });

  test("超长消息截断", async () => {
    const result = await nativeCreateError(responseOf({ message: "y".repeat(900) }));
    expect(result.message).toHaveLength(500);
    expect(result.message).toBe("y".repeat(500));
  });

  test("已短于上限的消息原样返回", async () => {
    await expect(nativeCreateError(responseOf({ message: "short" }))).resolves.toEqual({ message: "short" });
  });
});
