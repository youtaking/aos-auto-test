// better-auth.test.ts — Better Auth 导出验证
//
// 被测模块 src/auth/better-auth.ts 的 auth 实例在全局 preload 中被 mock
// （见 fenix-source/src/test-utils/setup-mocks.ts）。本测试验证该 mock 导出
// 的结构完整性，以及 auth.api 各方法可通过 lazy stub 机制访问。
//
// 源码关键配置（人工审查记录）：
//   - session.expiresIn = 60*60*24*7 = 604800 秒（7 天）
//   - session.updateAge = 60*60*24 = 86400 秒（每日刷新）
//   - apiKey.defaultPrefix = "rcs_"，rateLimit.enabled = false
//   - organization({ allowUserToCreateOrganization: true, membershipLimit: 100 })
//   - plugins: organization, phoneNumber（含手机号校验器）, apiKey

import { describe, expect, test, beforeEach, mock } from "bun:test";
import { auth } from "@fenix/auth/better-auth";

describe("better-auth 导出", () => {
  beforeEach(() => {
    mock.restore();
  });

  test("auth 实例已导出且为对象", () => {
    expect(auth).not.toBeNull();
    expect(typeof auth).toBe("object");
  });

  test("auth.api 已导出且为对象", () => {
    expect(auth.api).not.toBeNull();
    expect(typeof auth.api).toBe("object");
  });

  test("auth.handler 是函数", () => {
    expect(typeof auth.handler).toBe("function");
  });

  // ── auth.api 方法存在性（preload lazy mock 注册了 16 个方法） ──

  describe("auth.api 方法存在性", () => {
    const expectedMethods = [
      "signUpEmail",
      "listApiKeys",
      "deleteApiKey",
      "createApiKey",
      "addMember",
      "getFullOrganization",
      "updateOrganization",
      "deleteOrganization",
      "setActiveOrganization",
      "removeMember",
      "updateMemberRole",
      "listMembers",
      "listOrganizations",
      "createOrganization",
      "verifyApiKey",
      "getSession",
    ] as const;

    for (const method of expectedMethods) {
      test(`auth.api.${method} 是函数`, () => {
        expect(typeof (auth.api as any)[method]).toBe("function");
      });
    }
  });

  // ── handler 行为 ──

  test("handler 默认返回 Response 对象", async () => {
    const req = new Request("http://localhost/api/auth/session");
    const result = await auth.handler(req);
    expect(result).toBeInstanceOf(Response);
  });

  test("handler 默认返回 200 状态", async () => {
    const req = new Request("http://localhost/api/auth/session");
    const result = await auth.handler(req);
    expect(result.status).toBe(200);
  });
});
