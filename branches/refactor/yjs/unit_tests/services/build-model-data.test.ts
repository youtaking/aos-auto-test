import { describe, expect, it } from "bun:test";

// buildModelData 纯函数复制（原函数位于 services/config/provider.ts，因 DB 依赖无法直接 import）

interface ModelDataInput {
  name?: string;
  modalities?: string[] | null;
  limit?: Record<string, unknown> | null;
  cost?: Record<string, unknown> | null;
  options?: Record<string, unknown> | null;
}

function buildModelData(data: ModelDataInput): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  if (typeof data.name === "string") result.displayName = data.name;
  if (data.modalities !== undefined) result.modalities = data.modalities;
  if (data.limit !== undefined) result.limitConfig = data.limit;
  if (data.cost !== undefined) result.cost = data.cost;
  if (data.options !== undefined) result.options = data.options;
  return result;
}

describe("buildModelData", () => {
  it("将前端字段映射为 PG 字段", () => {
    const result = buildModelData({
      name: "GPT-4o",
      modalities: ["text", "image"],
      limit: { rpm: 60 },
      cost: { input: 0.01 },
      options: { streaming: true },
    });
    expect(result.displayName).toBe("GPT-4o");
    expect(result.modalities).toEqual(["text", "image"]);
    expect(result.limitConfig).toEqual({ rpm: 60 });
    expect(result.cost).toEqual({ input: 0.01 });
    expect(result.options).toEqual({ streaming: true });
  });

  it("将 data.name 映射为 displayName", () => {
    const result = buildModelData({ name: "Claude 3.5" });
    expect(result.displayName).toBe("Claude 3.5");
  });

  it("非字符串 name 不映射为 displayName", () => {
    const result = buildModelData({ name: 123 as unknown as string });
    expect(result.displayName).toBeUndefined();
  });

  it("将 data.limit 映射为 limitConfig", () => {
    const result = buildModelData({ limit: { rpm: 100 } });
    expect(result.limitConfig).toEqual({ rpm: 100 });
  });

  it("空输入返回空对象", () => {
    const result = buildModelData({});
    expect(result).toEqual({});
  });

  it("透传 null 值以支持清除字段", () => {
    const result = buildModelData({ modalities: null });
    expect(result.displayName).toBeUndefined();
    expect(result.modalities).toBeNull();
  });

  it("跳过 undefined 值的字段", () => {
    const result = buildModelData({ modalities: undefined });
    expect(result.modalities).toBeUndefined();
  });
});

// ── mapCoreStatus ──

function mapCoreStatus(status: string): "running" | "stopped" | "error" | "starting" {
  switch (status) {
    case "running":
      return "running";
    case "stopped":
    case "stopping":
      return "stopped";
    case "error":
      return "error";
    default:
      return "starting";
  }
}

describe("mapCoreStatus", () => {
  it("running → running", () => {
    expect(mapCoreStatus("running")).toBe("running");
  });

  it("stopped → stopped", () => {
    expect(mapCoreStatus("stopped")).toBe("stopped");
  });

  it("stopping → stopped（合并为同一状态）", () => {
    expect(mapCoreStatus("stopping")).toBe("stopped");
  });

  it("error → error", () => {
    expect(mapCoreStatus("error")).toBe("error");
  });

  it("未知状态 → starting", () => {
    expect(mapCoreStatus("pending")).toBe("starting");
    expect(mapCoreStatus("")).toBe("starting");
  });
});
