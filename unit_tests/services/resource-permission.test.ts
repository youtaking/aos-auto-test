import { describe, test, expect } from "bun:test";

// ── Pure function copies from src/services/resource-permission.ts ──

class AppError extends Error {
  readonly code: string;
  readonly statusCode: number;
  constructor(message: string, code: string, statusCode: number) {
    super(message);
    this.code = code;
    this.statusCode = statusCode;
  }
}

interface AuthContext {
  organizationId: string;
  userId: string;
  role: string;
  organizationName?: string;
}

interface ResourceAccessInput {
  id: string;
  organizationId: string;
}

interface ResourceAccess {
  ownership: "internal" | "external";
  sourceOrganizationId: string;
  sourceOrganizationName?: string;
  resourceUid: string;
  resourceKey: string;
  manageable: boolean;
  writable: boolean;
  publicReadable?: boolean;
}

function buildResourceAccess(
  ctx: AuthContext,
  _resourceType: string,
  row: ResourceAccessInput,
  publicReadable?: boolean,
  sourceOrganizationName?: string,
): ResourceAccess {
  const internal = row.organizationId === ctx.organizationId;
  return {
    ownership: internal ? "internal" : "external",
    sourceOrganizationId: row.organizationId,
    sourceOrganizationName,
    resourceUid: row.id,
    resourceKey: `${row.organizationId}/${row.id}`,
    manageable: internal,
    writable: internal,
    publicReadable: internal ? publicReadable : undefined,
  };
}

function assertInternalWritable(
  ctx: AuthContext,
  _resourceType: string,
  _resourceId: string,
  ownerOrganizationId: string,
): void {
  if (ownerOrganizationId !== ctx.organizationId) {
    throw new AppError("External resource is read-only", "FORBIDDEN", 403);
  }
}

// ── Tests ──

describe("buildResourceAccess", () => {
  const ctx: AuthContext = {
    organizationId: "org-1",
    userId: "user-1",
    role: "admin",
  };

  test("internal ownership: all writable and manageable", () => {
    const row: ResourceAccessInput = { id: "res-1", organizationId: "org-1" };
    const result = buildResourceAccess(ctx, "agent", row);

    expect(result.ownership).toBe("internal");
    expect(result.manageable).toBe(true);
    expect(result.writable).toBe(true);
    expect(result.sourceOrganizationId).toBe("org-1");
    expect(result.resourceUid).toBe("res-1");
  });

  test("external ownership: read-only, not manageable", () => {
    const row: ResourceAccessInput = { id: "res-2", organizationId: "org-2" };
    const result = buildResourceAccess(ctx, "agent", row);

    expect(result.ownership).toBe("external");
    expect(result.manageable).toBe(false);
    expect(result.writable).toBe(false);
    expect(result.sourceOrganizationId).toBe("org-2");
  });

  test("publicReadable is set for internal resources when true", () => {
    const row: ResourceAccessInput = { id: "res-1", organizationId: "org-1" };
    const result = buildResourceAccess(ctx, "agent", row, true);

    expect(result.publicReadable).toBe(true);
  });

  test("publicReadable is set for internal resources when false", () => {
    const row: ResourceAccessInput = { id: "res-1", organizationId: "org-1" };
    const result = buildResourceAccess(ctx, "agent", row, false);

    expect(result.publicReadable).toBe(false);
  });

  test("publicReadable is undefined for external resources even when param is true", () => {
    const row: ResourceAccessInput = { id: "res-2", organizationId: "org-2" };
    const result = buildResourceAccess(ctx, "agent", row, true);

    expect(result.publicReadable).toBeUndefined();
  });

  test("publicReadable is undefined for internal resources when param not provided", () => {
    const row: ResourceAccessInput = { id: "res-1", organizationId: "org-1" };
    const result = buildResourceAccess(ctx, "agent", row);

    expect(result.publicReadable).toBeUndefined();
  });

  test("resourceKey format is organizationId/id", () => {
    const row: ResourceAccessInput = { id: "res-abc", organizationId: "org-xyz" };
    const result = buildResourceAccess(ctx, "skill", row);

    expect(result.resourceKey).toBe("org-xyz/res-abc");
  });

  test("sourceOrganizationName is passed through when provided", () => {
    const row: ResourceAccessInput = { id: "res-1", organizationId: "org-2" };
    const result = buildResourceAccess(ctx, "agent", row, undefined, "Other Org");

    expect(result.sourceOrganizationName).toBe("Other Org");
  });

  test("sourceOrganizationName is undefined when not provided", () => {
    const row: ResourceAccessInput = { id: "res-1", organizationId: "org-1" };
    const result = buildResourceAccess(ctx, "agent", row);

    expect(result.sourceOrganizationName).toBeUndefined();
  });

  test("different resource types produce same structure", () => {
    const row: ResourceAccessInput = { id: "res-1", organizationId: "org-1" };
    const agentResult = buildResourceAccess(ctx, "agent", row);
    const skillResult = buildResourceAccess(ctx, "skill", row);

    // _resourceType is unused in the logic, so results should be identical
    expect(agentResult).toEqual(skillResult);
  });
});

describe("assertInternalWritable", () => {
  const ctx: AuthContext = {
    organizationId: "org-1",
    userId: "user-1",
    role: "admin",
  };

  test("passes silently for same organization", () => {
    expect(() => assertInternalWritable(ctx, "agent", "res-1", "org-1")).not.toThrow();
  });

  test("throws AppError for different organization", () => {
    expect(() => assertInternalWritable(ctx, "agent", "res-1", "org-2")).toThrow(
      "External resource is read-only",
    );
  });

  test("thrown error has correct code and statusCode", () => {
    try {
      assertInternalWritable(ctx, "agent", "res-1", "org-2");
      expect.unreachable("should have thrown");
    } catch (err) {
      const appErr = err as AppError;
      expect(appErr.code).toBe("FORBIDDEN");
      expect(appErr.statusCode).toBe(403);
    }
  });

  test("error message matches expected format", () => {
    try {
      assertInternalWritable(ctx, "skill", "skill-5", "other-org");
      expect.unreachable("should have thrown");
    } catch (err) {
      expect((err as Error).message).toBe("External resource is read-only");
    }
  });
});
