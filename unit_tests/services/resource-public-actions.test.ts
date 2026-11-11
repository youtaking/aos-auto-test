// resource-public-actions.test.ts — 受控资源公开共享动作语义测试
// 测试目标：mcpServerResource.definition / skillResource.definition 的动作与默认动作集合
// 业务意图：公开资源必须同时授予 read 与 use（其他组织可查看并绑定到 Agent），但不放大写权限；
//           私有资源对其它组织保持完全隔离，同组织成员仍只有 read/use
// 源：packages/resources/mcp/src/server/access/mcp-server-resource.ts
//     packages/resources/skill/src/server/access/skill-resource.ts（main f12e40ec）

import { describe, expect, test } from "bun:test";

// ── 复制实现 ──

type ResourceAction = "read" | "create" | "update" | "delete" | "use";
type Visibility = "public" | "private";

interface ResourceDefinition {
  type: string;
  ownershipMode: "organization";
  actions: readonly ResourceAction[];
  memberDefaultActions: readonly ResourceAction[];
  publicDefaultActions: readonly ResourceAction[];
}

interface ResourceRegistration {
  definition: ResourceDefinition;
}

const mcpServerResource: ResourceRegistration = {
  definition: {
    type: "mcp_server",
    ownershipMode: "organization",
    actions: ["read", "create", "update", "delete", "use"],
    memberDefaultActions: ["read", "use"],
    publicDefaultActions: ["read", "use"],
  },
};

const skillResource: ResourceRegistration = {
  definition: {
    type: "skill",
    ownershipMode: "organization",
    actions: ["read", "create", "update", "delete", "use"],
    memberDefaultActions: ["read", "use"],
    publicDefaultActions: ["read", "use"],
  },
};

const SHARED_RESOURCES = [
  { label: "mcp_server", definition: mcpServerResource.definition },
  { label: "skill", definition: skillResource.definition },
] as const;

/** 跨组织访问时仅公开资源按 publicDefaultActions 放行；私有资源一律无动作。 */
function crossOrganizationActions(definition: ResourceDefinition, visibility: Visibility): readonly ResourceAction[] {
  return visibility === "public" ? definition.publicDefaultActions : [];
}

/** 模拟授权判定：同组织成员用 memberDefaultActions，跨组织用公开默认动作。 */
function isAllowed(
  definition: ResourceDefinition,
  action: ResourceAction,
  options: { visibility: Visibility; crossOrganization: boolean },
): boolean {
  const granted = options.crossOrganization
    ? crossOrganizationActions(definition, options.visibility)
    : definition.memberDefaultActions;
  return granted.includes(action);
}

// ── 测试 ──

describe("受控资源注册声明", () => {
  test("MCP Server 使用 organization 归属并声明完整动作集合", () => {
    expect(mcpServerResource.definition).toEqual({
      type: "mcp_server",
      ownershipMode: "organization",
      actions: ["read", "create", "update", "delete", "use"],
      memberDefaultActions: ["read", "use"],
      publicDefaultActions: ["read", "use"],
    });
  });

  test("Skill 使用 organization 归属并声明完整动作集合", () => {
    expect(skillResource.definition).toEqual({
      type: "skill",
      ownershipMode: "organization",
      actions: ["read", "create", "update", "delete", "use"],
      memberDefaultActions: ["read", "use"],
      publicDefaultActions: ["read", "use"],
    });
  });

  test("MCP Server 与 Skill 的默认动作保持同形", () => {
    expect(mcpServerResource.definition.memberDefaultActions).toEqual(
      skillResource.definition.memberDefaultActions,
    );
    expect(mcpServerResource.definition.publicDefaultActions).toEqual(
      skillResource.definition.publicDefaultActions,
    );
  });
});

for (const { label, definition } of SHARED_RESOURCES) {
  describe(`${label} 公开默认动作`, () => {
    test("公开受众同时获得 read 与 use", () => {
      expect(definition.publicDefaultActions).toEqual(["read", "use"]);
    });

    test("公开受众不获得创建、修改、删除动作", () => {
      expect(definition.publicDefaultActions).not.toContain("create");
      expect(definition.publicDefaultActions).not.toContain("update");
      expect(definition.publicDefaultActions).not.toContain("delete");
    });

    test("默认动作是资源动作上限的子集", () => {
      for (const action of definition.publicDefaultActions) {
        expect(definition.actions).toContain(action);
      }
      for (const action of definition.memberDefaultActions) {
        expect(definition.actions).toContain(action);
      }
    });
  });

  describe(`${label} 跨组织授权`, () => {
    test("公开资源允许读取与使用", () => {
      const options = { visibility: "public" as const, crossOrganization: true };

      expect(isAllowed(definition, "read", options)).toBe(true);
      expect(isAllowed(definition, "use", options)).toBe(true);
    });

    test("公开资源仍然拒绝写操作", () => {
      const options = { visibility: "public" as const, crossOrganization: true };

      expect(isAllowed(definition, "create", options)).toBe(false);
      expect(isAllowed(definition, "update", options)).toBe(false);
      expect(isAllowed(definition, "delete", options)).toBe(false);
    });

    test("私有资源对其它组织完全隔离", () => {
      const options = { visibility: "private" as const, crossOrganization: true };

      for (const action of ["read", "use", "create", "update", "delete"] as const) {
        expect(isAllowed(definition, action, options)).toBe(false);
      }
    });

    test("未知可见性按私有处理", () => {
      const options = { visibility: "shared" as unknown as Visibility, crossOrganization: true };

      expect(isAllowed(definition, "read", options)).toBe(false);
      expect(isAllowed(definition, "use", options)).toBe(false);
    });
  });

  describe(`${label} 同组织成员授权`, () => {
    test("成员可读取与使用", () => {
      const options = { visibility: "private" as const, crossOrganization: false };

      expect(isAllowed(definition, "read", options)).toBe(true);
      expect(isAllowed(definition, "use", options)).toBe(true);
    });

    test("成员不获得写权限", () => {
      const options = { visibility: "private" as const, crossOrganization: false };

      expect(isAllowed(definition, "create", options)).toBe(false);
      expect(isAllowed(definition, "update", options)).toBe(false);
      expect(isAllowed(definition, "delete", options)).toBe(false);
    });
  });
}
