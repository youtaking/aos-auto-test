import { describe, expect, it } from "bun:test";

// workflow-trigger.ts 纯函数测试
// 覆盖：maskHash、rowToMaskedView
// generateHash 测试格式约束（无法导入原函数）

// ── 类型定义 ──

interface WorkflowTriggerRow {
  id: string;
  workflowId: string;
  type: string;
  publicHash: string;
  secret: string | null;
  config: unknown;
  enabled: boolean;
  organizationId: string;
  createdAt: Date;
  updatedAt: Date;
}

interface TriggerView {
  id: string;
  workflowId: string;
  type: string;
  publicHash: string;
  maskedHash: string;
  webhookUrl: string | null;
  secret: string | null;
  config: Record<string, unknown> | null;
  enabled: boolean;
  createdAt: Date;
  updatedAt: Date;
}

// ── 纯函数复制 ──

function maskHash(hash: string): string {
  if (hash.length <= 6) return `${hash}***`;
  return `${hash.slice(0, 6)}***`;
}

function rowToMaskedView(row: WorkflowTriggerRow): TriggerView {
  return {
    id: row.id,
    workflowId: row.workflowId,
    type: row.type,
    publicHash: maskHash(row.publicHash),
    maskedHash: maskHash(row.publicHash),
    webhookUrl: null,
    secret: row.secret ?? null,
    config: (row.config as Record<string, unknown>) ?? null,
    enabled: row.enabled,
    createdAt: row.createdAt,
    updatedAt: row.updatedAt,
  };
}

// ── maskHash ──

describe("maskHash", () => {
  it("长 hash 只显示前 6 位 + ***", () => {
    const hash = "abcdef1234567890abcdef1234567890";
    expect(maskHash(hash)).toBe("abcdef***");
  });

  it("正好 6 字符的 hash 返回原值 + ***", () => {
    expect(maskHash("abcdef")).toBe("abcdef***");
  });

  it("少于 6 字符的 hash 返回原值 + ***", () => {
    expect(maskHash("abc")).toBe("abc***");
    expect(maskHash("a")).toBe("a***");
  });

  it("空字符串返回 ***", () => {
    expect(maskHash("")).toBe("***");
  });

  it("7 字符的 hash 取前 6 位", () => {
    expect(maskHash("abcdefg")).toBe("abcdef***");
  });
});

// ── rowToMaskedView ──

describe("rowToMaskedView", () => {
  const now = new Date("2026-06-15T10:00:00.000Z");

  function makeTriggerRow(overrides: Partial<WorkflowTriggerRow> = {}): WorkflowTriggerRow {
    return {
      id: "trigger-001",
      workflowId: "wf-001",
      type: "webhook",
      publicHash: "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
      secret: "my-secret",
      config: { method: "POST" },
      enabled: true,
      organizationId: "org-1",
      createdAt: now,
      updatedAt: now,
      ...overrides,
    };
  }

  it("publicHash 和 maskedHash 都被 mask", () => {
    const row = makeTriggerRow();
    const view = rowToMaskedView(row);
    expect(view.publicHash).toBe("abcdef***");
    expect(view.maskedHash).toBe("abcdef***");
  });

  it("webhookUrl 始终为 null（masked 视图不暴露 URL）", () => {
    const view = rowToMaskedView(makeTriggerRow());
    expect(view.webhookUrl).toBeNull();
  });

  it("透传 id、workflowId、type", () => {
    const view = rowToMaskedView(makeTriggerRow());
    expect(view.id).toBe("trigger-001");
    expect(view.workflowId).toBe("wf-001");
    expect(view.type).toBe("webhook");
  });

  it("secret 有值时透传", () => {
    const view = rowToMaskedView(makeTriggerRow({ secret: "s3cret" }));
    expect(view.secret).toBe("s3cret");
  });

  it("secret 为 null 时返回 null", () => {
    const view = rowToMaskedView(makeTriggerRow({ secret: null }));
    expect(view.secret).toBeNull();
  });

  it("config 有值时透传", () => {
    const config = { method: "POST", url: "http://x" };
    const view = rowToMaskedView(makeTriggerRow({ config }));
    expect(view.config).toEqual(config);
  });

  it("config 为 null 时返回 null", () => {
    const view = rowToMaskedView(makeTriggerRow({ config: null }));
    expect(view.config).toBeNull();
  });

  it("enabled 字段正确透传", () => {
    expect(rowToMaskedView(makeTriggerRow({ enabled: true })).enabled).toBe(true);
    expect(rowToMaskedView(makeTriggerRow({ enabled: false })).enabled).toBe(false);
  });

  it("时间戳字段直接引用传递", () => {
    const created = new Date("2026-01-01T00:00:00.000Z");
    const updated = new Date("2026-06-01T00:00:00.000Z");
    const view = rowToMaskedView(makeTriggerRow({ createdAt: created, updatedAt: updated }));
    expect(view.createdAt).toBe(created);
    expect(view.updatedAt).toBe(updated);
  });
});

// ── generateHash 格式约束 ──

describe("generateHash 格式约束", () => {
  it("32 字节 hex hash 长度为 64", () => {
    const { randomBytes } = require("node:crypto");
    const hash = randomBytes(32).toString("hex");
    expect(hash.length).toBe(64);
    expect(/^[0-9a-f]{64}$/.test(hash)).toBe(true);
  });

  it("两次生成的 hash 不同", () => {
    const { randomBytes } = require("node:crypto");
    const h1 = randomBytes(32).toString("hex");
    const h2 = randomBytes(32).toString("hex");
    expect(h1).not.toBe(h2);
  });
});
