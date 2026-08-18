import { describe, expect, it } from "bun:test";

// resolveAgentNode / toolsToPermission 纯函数复制
// 原函数位于 services/config/agent-config.ts，因 DB 依赖无法直接 import

// ── resolveAgentNode ──

type AgentNode =
  | { kind: "machine"; machineId: string }
  | { kind: "sandbox"; sandboxPoolId: string }
  | Record<string, never>;

function normalizeAgentNode(input: unknown): AgentNode | null {
  if (!input || typeof input !== "object" || Array.isArray(input)) return null;
  const value = input as Record<string, unknown>;
  if (Object.keys(value).length === 0) return {};
  if (value.kind === "machine" && typeof value.machineId === "string" && value.machineId.length > 0) {
    return { kind: "machine", machineId: value.machineId };
  }
  if (value.kind === "sandbox" && typeof value.sandboxPoolId === "string" && value.sandboxPoolId.length > 0) {
    return { kind: "sandbox", sandboxPoolId: value.sandboxPoolId };
  }
  return null;
}

function resolveAgentNode(row: { agentNode?: unknown; machineId: string | null }): AgentNode | null {
  if (row.agentNode !== null && row.agentNode !== undefined) {
    return normalizeAgentNode(row.agentNode) ?? (row.machineId ? { kind: "machine", machineId: row.machineId } : {});
  }
  return row.machineId ? { kind: "machine", machineId: row.machineId } : {};
}

// ── toolsToPermission ──

type PermissionAction = "ask" | "allow" | "deny";

function toolsToPermission(tools: Record<string, boolean>): Record<string, PermissionAction> {
  const result: Record<string, PermissionAction> = {};
  for (const [key, val] of Object.entries(tools)) {
    result[key] = val ? "allow" : "deny";
  }
  return result;
}

// ────────────────────────────────────────────
// Tests: resolveAgentNode
// ────────────────────────────────────────────

describe("resolveAgentNode", () => {
  it("agentNode 为有效 machine 节点时直接返回", () => {
    const result = resolveAgentNode({
      agentNode: { kind: "machine", machineId: "m-001" },
      machineId: "fallback-id",
    });
    expect(result).toEqual({ kind: "machine", machineId: "m-001" });
  });

  it("agentNode 为有效 sandbox 节点时直接返回", () => {
    const result = resolveAgentNode({
      agentNode: { kind: "sandbox", sandboxPoolId: "pool-abc" },
      machineId: "fallback-id",
    });
    expect(result).toEqual({ kind: "sandbox", sandboxPoolId: "pool-abc" });
  });

  it("agentNode 为空对象时返回空对象", () => {
    const result = resolveAgentNode({
      agentNode: {},
      machineId: "m-002",
    });
    expect(result).toEqual({});
  });

  it("agentNode 无效且 machineId 存在时 fallback 到 machine", () => {
    // agentNode 为数组 → normalizeAgentNode 返回 null → fallback
    const result = resolveAgentNode({
      agentNode: [1, 2, 3],
      machineId: "m-fallback",
    });
    expect(result).toEqual({ kind: "machine", machineId: "m-fallback" });
  });

  it("agentNode 无效且 machineId 为 null 时返回空对象", () => {
    const result = resolveAgentNode({
      agentNode: "bad-string",
      machineId: null,
    });
    expect(result).toEqual({});
  });

  it("agentNode 为 null 时走 machineId 分支", () => {
    const result = resolveAgentNode({
      agentNode: null,
      machineId: "m-from-null",
    });
    expect(result).toEqual({ kind: "machine", machineId: "m-from-null" });
  });

  it("agentNode 为 undefined 时走 machineId 分支", () => {
    const result = resolveAgentNode({
      machineId: "m-from-undef",
    });
    expect(result).toEqual({ kind: "machine", machineId: "m-from-undef" });
  });

  it("agentNode 为 null 且 machineId 为 null 时返回空对象", () => {
    const result = resolveAgentNode({
      agentNode: null,
      machineId: null,
    });
    expect(result).toEqual({});
  });

  it("agentNode 为 undefined 且 machineId 为 null 时返回空对象", () => {
    const result = resolveAgentNode({
      machineId: null,
    });
    expect(result).toEqual({});
  });

  it("agentNode 无效（kind 未知）时 fallback 到 machineId", () => {
    const result = resolveAgentNode({
      agentNode: { kind: "unknown-type", foo: "bar" },
      machineId: "m-fb",
    });
    expect(result).toEqual({ kind: "machine", machineId: "m-fb" });
  });

  it("agentNode kind=machine 但 machineId 为空字符串时 fallback", () => {
    const result = resolveAgentNode({
      agentNode: { kind: "machine", machineId: "" },
      machineId: "m-fallback2",
    });
    // normalizeAgentNode 返回 null（machineId 长度为 0），fallback 到 row.machineId
    expect(result).toEqual({ kind: "machine", machineId: "m-fallback2" });
  });

  it("agentNode kind=sandbox 但 sandboxPoolId 缺失时 fallback", () => {
    const result = resolveAgentNode({
      agentNode: { kind: "sandbox" },
      machineId: null,
    });
    expect(result).toEqual({});
  });
});

// ────────────────────────────────────────────
// Tests: toolsToPermission
// ────────────────────────────────────────────

describe("toolsToPermission", () => {
  it("true 映射为 allow，false 映射为 deny", () => {
    const result = toolsToPermission({ read: true, write: false });
    expect(result).toEqual({ read: "allow", write: "deny" });
  });

  it("空对象返回空对象", () => {
    expect(toolsToPermission({})).toEqual({});
  });

  it("全部 true 全部映射为 allow", () => {
    const result = toolsToPermission({ a: true, b: true, c: true });
    expect(result).toEqual({ a: "allow", b: "allow", c: "allow" });
  });

  it("全部 false 全部映射为 deny", () => {
    const result = toolsToPermission({ x: false, y: false });
    expect(result).toEqual({ x: "deny", y: "deny" });
  });

  it("单个工具也能正确转换", () => {
    expect(toolsToPermission({ shell: true })).toEqual({ shell: "allow" });
    expect(toolsToPermission({ shell: false })).toEqual({ shell: "deny" });
  });

  it("保留工具名称作为 key", () => {
    const result = toolsToPermission({
      "mcp__filesystem__read": true,
      "mcp__filesystem__write": false,
      "bash_execute": true,
    });
    expect(Object.keys(result)).toEqual([
      "mcp__filesystem__read",
      "mcp__filesystem__write",
      "bash_execute",
    ]);
    expect(result["mcp__filesystem__read"]).toBe("allow");
    expect(result["mcp__filesystem__write"]).toBe("deny");
    expect(result["bash_execute"]).toBe("allow");
  });
});
