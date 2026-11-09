// native-resources.test.ts — 原生 resourceLimits 归一化测试
// 测试目标：nativeResources 的字段存在性判定与 quantity 单位换算
// 业务意图：代理调用方传入的 K8s 风格数量要换算成集群 CPU/内存/磁盘/GPU 口径，未知或非法值保留为 null
// 源：packages/opensandbox-cluster/src/services/native-resources.ts（main a7f477a9e）

import { describe, expect, test } from "bun:test";

// ── 复制实现 ──

interface NativeResources {
  cpu: number | null;
  memoryMb: number | null;
  diskGb: number | null;
  gpuCount: number | null;
}

function quantity(value: unknown, unit: "cpu" | "memory" | "disk" | "gpu"): number | null {
  if (typeof value !== "string" && typeof value !== "number") return null;
  const match = /^(\d+(?:\.\d+)?)([A-Za-z]*)$/.exec(String(value));
  if (!match) return null;
  const number = Number(match[1]);
  const suffix = match[2];
  let result: number;
  if (unit === "cpu") result = suffix === "m" ? number / 1000 : suffix === "" ? number : NaN;
  else if (unit === "gpu") result = suffix === "" && Number.isInteger(number) ? number : NaN;
  else {
    const multipliers: Record<string, number> = {
      "": 1,
      Ki: 2 ** 10,
      Mi: 2 ** 20,
      Gi: 2 ** 30,
      Ti: 2 ** 40,
      K: 1e3,
      M: 1e6,
      G: 1e9,
      T: 1e12,
    };
    result = (number * (multipliers[suffix] ?? NaN)) / (unit === "memory" ? 2 ** 20 : 2 ** 30);
  }
  return Number.isFinite(result) && result >= 0 ? result : null;
}

function nativeResources(body: unknown): NativeResources | undefined {
  if (!body || typeof body !== "object" || !("resourceLimits" in body)) return;
  const limits = body.resourceLimits;
  if (!limits || typeof limits !== "object") return;
  const fields = limits as Record<string, unknown>;
  return {
    cpu: quantity(fields.cpu, "cpu"),
    memoryMb: quantity(fields.memory, "memory"),
    diskGb: quantity(fields.disk, "disk"),
    gpuCount: quantity(fields.gpu, "gpu"),
  };
}

// ── tests ──

describe("quantity CPU 换算", () => {
  test("毫核换算为核", () => {
    expect(quantity("500m", "cpu")).toBe(0.5);
    expect(quantity("250m", "cpu")).toBe(0.25);
    expect(quantity(1500, "cpu")).toBe(1500);
  });

  test("无单位按核处理，支持小数", () => {
    expect(quantity("2", "cpu")).toBe(2);
    expect(quantity("0.5", "cpu")).toBe(0.5);
    expect(quantity(1.25, "cpu")).toBe(1.25);
  });

  test("未知单位或非法写法返回 null", () => {
    for (const value of ["2c", "1Gi", "-1", "+1", "", "abc", "1.2.3", " 1"]) {
      expect(quantity(value, "cpu")).toBeNull();
    }
  });
});

describe("quantity 内存与磁盘换算", () => {
  test("二进制单位换算到 MiB / GiB", () => {
    expect(quantity("512Mi", "memory")).toBe(512);
    expect(quantity("2Gi", "memory")).toBe(2048);
    expect(quantity("1Ti", "memory")).toBe(1024 * 1024);
    expect(quantity("8192Ki", "memory")).toBe(8);
    expect(quantity("10Gi", "disk")).toBe(10);
    expect(quantity("1Ti", "disk")).toBe(1024);
  });

  test("十进制单位按 1e3 进制换算", () => {
    expect(quantity("1G", "memory")).toBeCloseTo(1e9 / 2 ** 20, 10);
    expect(quantity("2M", "memory")).toBeCloseTo((2e6) / 2 ** 20, 10);
    expect(quantity("1T", "disk")).toBeCloseTo(1e12 / 2 ** 30, 10);
    expect(quantity("500K", "disk")).toBeCloseTo(500e3 / 2 ** 30, 12);
  });

  test("无单位按字节处理", () => {
    expect(quantity("1048576", "memory")).toBe(1);
    expect(quantity(2 ** 21, "memory")).toBe(2);
    expect(quantity(String(2 ** 30), "disk")).toBe(1);
    expect(quantity("5", "disk")).toBeCloseTo(5 / 2 ** 30, 15);
  });

  test("大小写不匹配的单位视为未知", () => {
    expect(quantity("1gi", "memory")).toBeNull();
    expect(quantity("1KI", "memory")).toBeNull();
    expect(quantity("1g", "disk")).toBeNull();
  });
});

describe("quantity GPU 换算", () => {
  test("无单位整数直接取值，含 0", () => {
    expect(quantity("1", "gpu")).toBe(1);
    expect(quantity(0, "gpu")).toBe(0);
    expect(quantity("4", "gpu")).toBe(4);
  });

  test("小数或带单位返回 null", () => {
    expect(quantity("1.5", "gpu")).toBeNull();
    expect(quantity("1Gi", "gpu")).toBeNull();
  });
});

describe("quantity 非数值输入", () => {
  test("布尔、null、对象、数组返回 null", () => {
    for (const value of [true, null, undefined, {}, []]) {
      expect(quantity(value, "memory")).toBeNull();
    }
  });

  test("NaN 与 Infinity 不能作为数字输入", () => {
    expect(quantity(Number.NaN, "memory")).toBeNull();
    expect(quantity(Number.POSITIVE_INFINITY, "memory")).toBeNull();
  });
});

describe("nativeResources 提取", () => {
  test("缺 resourceLimits 或类型非法时返回 undefined", () => {
    for (const body of [null, undefined, "text", 42, {}, { resourceLimits: null }, { resourceLimits: "x" }]) {
      expect(nativeResources(body)).toBeUndefined();
    }
  });

  test("缺字段或字段非法时为 null", () => {
    expect(nativeResources({ resourceLimits: {} })).toEqual({
      cpu: null,
      memoryMb: null,
      diskGb: null,
      gpuCount: null,
    });
    expect(nativeResources({ resourceLimits: { cpu: "bad", memory: -1 } })).toEqual({
      cpu: null,
      memoryMb: null,
      diskGb: null,
      gpuCount: null,
    });
  });

  test("完整字段按集群口径返回", () => {
    expect(nativeResources({ resourceLimits: { cpu: "500m", memory: "1Gi", disk: "10Gi", gpu: 1 } })).toEqual({
      cpu: 0.5,
      memoryMb: 1024,
      diskGb: 10,
      gpuCount: 1,
    });
  });

  test("忽略未知字段，不修改入参", () => {
    const limits = { cpu: "2", other: "ignored" };
    const body = { resourceLimits: limits, extra: 1 };
    expect(nativeResources(body)).toEqual({ cpu: 2, memoryMb: null, diskGb: null, gpuCount: null });
    expect(limits).toEqual({ cpu: "2", other: "ignored" });
  });
});
