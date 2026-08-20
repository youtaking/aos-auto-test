// logger.test.ts — 请求日志插件中可测纯函数测试
// 测试目标：isRecoverableCtrlSpa404 的 SPA fallback 判定逻辑
// 业务意图：确保 /ctrl/* 无扩展名路径的 404 被识别为 SPA 路由而非真正资源缺失

import { describe, test, expect } from "bun:test";

// ── 复制纯函数（来自 src/plugins/logger.ts）──

function isNotFoundLikeError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  return error.name === "NotFoundError" || "status" in error || "code" in error;
}

function isRecoverableCtrlSpa404(request: Request, error: unknown, status: number): boolean {
  if (status !== 404 || !isNotFoundLikeError(error)) return false;

  const url = new URL(request.url);
  if (!url.pathname.startsWith("/ctrl/")) return false;
  // extname 等效
  const lastDot = url.pathname.lastIndexOf(".");
  const lastSlash = url.pathname.lastIndexOf("/");
  const hasExt = lastDot > lastSlash && lastDot > 0;
  if (hasExt) return false;

  return true;
}

// ── 辅助 ──

function makeNotFoundError() {
  const err = new Error("Not Found");
  err.name = "NotFoundError";
  return err;
}

function makeStatusError(status: number) {
  const err = new Error("not found");
  (err as any).status = status;
  return err;
}

// ── 测试 ──

describe("isNotFoundLikeError", () => {
  test("正向 - NotFoundError 名称匹配", () => {
    expect(isNotFoundLikeError(makeNotFoundError())).toBe(true);
  });

  test("正向 - 带 status 属性匹配", () => {
    expect(isNotFoundLikeError(makeStatusError(404))).toBe(true);
  });

  test("正向 - 带 code 属性匹配", () => {
    const err = new Error("ENOENT");
    (err as any).code = "ENOENT";
    expect(isNotFoundLikeError(err)).toBe(true);
  });

  test("分支 - 普通 Error 不匹配", () => {
    expect(isNotFoundLikeError(new Error("other"))).toBe(false);
  });

  test("分支 - 非 Error 不匹配", () => {
    expect(isNotFoundLikeError("string")).toBe(false);
    expect(isNotFoundLikeError(null)).toBe(false);
    expect(isNotFoundLikeError({ name: "NotFoundError" })).toBe(false);
  });
});

describe("isRecoverableCtrlSpa404", () => {
  test("正向 - /ctrl/ 无扩展名 + 404 + NotFoundError 返回 true", () => {
    const req = new Request("http://localhost/ctrl/agent/home");
    expect(isRecoverableCtrlSpa404(req, makeNotFoundError(), 404)).toBe(true);
  });

  test("分支 - 非 404 状态返回 false", () => {
    const req = new Request("http://localhost/ctrl/agent/home");
    expect(isRecoverableCtrlSpa404(req, makeNotFoundError(), 500)).toBe(false);
  });

  test("分支 - 非 /ctrl/ 路径返回 false", () => {
    const req = new Request("http://localhost/api/test");
    expect(isRecoverableCtrlSpa404(req, makeNotFoundError(), 404)).toBe(false);
  });

  test("分支 - 有扩展名路径返回 false（JS/CSS/图片）", () => {
    const req = new Request("http://localhost/ctrl/assets/main.js");
    expect(isRecoverableCtrlSpa404(req, makeNotFoundError(), 404)).toBe(false);
  });

  test("分支 - .css 扩展名返回 false", () => {
    const req = new Request("http://localhost/ctrl/styles.css");
    expect(isRecoverableCtrlSpa404(req, makeNotFoundError(), 404)).toBe(false);
  });

  test("分支 - 非 NotFoundLike 错误返回 false", () => {
    const req = new Request("http://localhost/ctrl/agent/home");
    expect(isRecoverableCtrlSpa404(req, new Error("other"), 404)).toBe(false);
  });

  test("边界 - /ctrl/ 根路径（无子路径）返回 true", () => {
    const req = new Request("http://localhost/ctrl/");
    expect(isRecoverableCtrlSpa404(req, makeNotFoundError(), 404)).toBe(true);
  });

  test("边界 - /ctrl/view/abc123 深链返回 true", () => {
    const req = new Request("http://localhost/ctrl/view/abc123");
    expect(isRecoverableCtrlSpa404(req, makeStatusError(404), 404)).toBe(true);
  });

  test("边界 - 带查询参数不影响判定", () => {
    const req = new Request("http://localhost/ctrl/agent/home?tab=chat");
    expect(isRecoverableCtrlSpa404(req, makeNotFoundError(), 404)).toBe(true);
  });
});
