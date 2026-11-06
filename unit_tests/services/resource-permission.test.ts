import { describe, expect, test } from "bun:test";
import type { ResourceAccess, ResourceScope } from "@fenix/platform-sdk/resource/authorization";
import { toResourceAccessView } from "@fenix/platform-sdk/protocol/resource-access-view";

// 旧的 buildResourceAccess 已迁到平台侧的 toResourceAccessView：
// 视图字段由 scope + 有效动作派生，资源包不再各自实现一份。

function view(
  scope: ResourceScope,
  access: ResourceAccess,
  activeOrganizationId?: string,
  sourceOrganizationName?: string,
) {
  return toResourceAccessView({
    resource: { id: "res-1", scope, access },
    activeOrganizationId,
    sourceOrganizationName,
  });
}

const UPDATE: ResourceAccess = { actions: ["read", "update", "delete"] };
const READ_ONLY: ResourceAccess = { actions: ["read", "use"] };

describe("toResourceAccessView", () => {
  // 资源归属组织与当前组织一致时为 internal，并可由有效动作决定是否可写。
  test("maps an owned resource to internal", () => {
    const result = view({ organizationId: "org-1", visibility: "private" }, UPDATE, "org-1");

    expect(result.ownership).toBe("internal");
    expect(result.sourceOrganizationId).toBe("org-1");
    expect(result.resourceUid).toBe("res-1");
    expect(result.resourceKey).toBe("org-1/res-1");
    expect(result.manageable).toBe(true);
    expect(result.writable).toBe(true);
  });

  // 跨组织资源即使拿到了 update 动作，也必须标记为 external；可写性以动作集合为准。
  test("maps a shared resource to external while honouring granted actions", () => {
    const result = view({ organizationId: "org-2", visibility: "private" }, UPDATE, "org-1");

    expect(result.ownership).toBe("external");
    expect(result.sourceOrganizationId).toBe("org-2");
    expect(result.writable).toBe(true);
  });

  // 成员默认只拿到 read/use：同样是本组织资源，也不可管理、不可写。
  test("does not grant manage or write without the update action", () => {
    const result = view({ organizationId: "org-1", visibility: "private" }, READ_ONLY, "org-1");

    expect(result.ownership).toBe("internal");
    expect(result.manageable).toBe(false);
    expect(result.writable).toBe(false);
  });

  // publicReadable 由资源自身的 visibility 表达，而不是访问者权限。
  test("derives publicReadable from resource visibility", () => {
    expect(view({ organizationId: "org-1", visibility: "public" }, UPDATE, "org-1").publicReadable).toBe(true);
    expect(view({ organizationId: "org-1", visibility: "private" }, UPDATE, "org-1").publicReadable).toBe(false);
  });

  // 组织名录可用时透出来源组织名，便于外部资源展示。
  test("passes through the source organization name when provided", () => {
    const result = view({ organizationId: "org-2", visibility: "private" }, READ_ONLY, "org-1", "Other Org");

    expect(result.sourceOrganizationName).toBe("Other Org");
  });

  // 名录缺失时省略字段，而不是写 undefined，保持对外协议形状稳定。
  test("omits the source organization name when unavailable", () => {
    const result = view({ organizationId: "org-1", visibility: "private" }, UPDATE, "org-1");

    expect("sourceOrganizationName" in result).toBe(false);
  });

  // 无可比对的当前组织时，资源一律按 external 处理。
  test("treats a resource as external when the active organization is unknown", () => {
    const result = view({ organizationId: "org-1", visibility: "private" }, UPDATE);

    expect(result.ownership).toBe("external");
  });

  // 归属组织缺失时 resourceKey 仍保持稳定格式，不抛错。
  test("builds the resource key from the owning organization", () => {
    const result = view({ visibility: "private" }, UPDATE, "org-1");

    expect(result.sourceOrganizationId).toBe("");
    expect(result.resourceKey).toBe("/res-1");
  });
});
