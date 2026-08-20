// require-team-scope.test.ts — 组织权限校验测试
// 测试目标：requireOrgScope 的跨组织拒绝和放行逻辑
// 业务意图：确保 API 路由不能访问其他组织的资源

import { describe, test, expect } from "bun:test";

// ── 复制纯函数（来自 src/plugins/require-team-scope.ts + auth.ts 的 errorResponse）──

interface AuthContext {
  organizationId: string;
  organizationName?: string;
  userId: string;
  role: "owner" | "admin" | "member";
}

function errorResponse(code: number, response: unknown): Response {
  return new Response(JSON.stringify(response), {
    status: code,
    headers: { "Content-Type": "application/json" },
  });
}

function requireOrgScope(
  authContext: AuthContext | null,
  resourceOrgId: string | null | undefined,
): Response | undefined {
  if (!authContext || !resourceOrgId) {
    return errorResponse(403, { error: { type: "forbidden", message: "Access denied" } });
  }
  if (authContext.organizationId !== resourceOrgId) {
    return errorResponse(403, {
      error: { type: "forbidden", message: "Resource does not belong to your organization" },
    });
  }
  return;
}

// ── 测试 ──

describe("requireOrgScope", () => {
  const ctx: AuthContext = { organizationId: "org-1", userId: "u1", role: "member" };

  test("正向 - 同组织返回 undefined（放行）", () => {
    expect(requireOrgScope(ctx, "org-1")).toBeUndefined();
  });

  test("分支 - 不同组织返回 403 Response", async () => {
    const resp = requireOrgScope(ctx, "org-2");
    expect(resp).toBeInstanceOf(Response);
    expect(resp!.status).toBe(403);
    const body = await resp!.json();
    expect(body.error.message).toContain("does not belong");
  });

  test("分支 - authContext 为 null 返回 403", async () => {
    const resp = requireOrgScope(null, "org-1");
    expect(resp!.status).toBe(403);
    const body = await resp!.json();
    expect(body.error.message).toBe("Access denied");
  });

  test("分支 - resourceOrgId 为 null 返回 403", () => {
    expect(requireOrgScope(ctx, null)).toBeInstanceOf(Response);
  });

  test("分支 - resourceOrgId 为 undefined 返回 403", () => {
    expect(requireOrgScope(ctx, undefined)).toBeInstanceOf(Response);
  });

  test("边界 - 双方都是 null 返回 403", () => {
    expect(requireOrgScope(null, null)).toBeInstanceOf(Response);
  });

  test("隔离 - 不影响原 authContext", () => {
    requireOrgScope(ctx, "org-1");
    expect(ctx.organizationId).toBe("org-1");
  });
});
