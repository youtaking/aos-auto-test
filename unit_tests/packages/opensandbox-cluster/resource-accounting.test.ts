// resource-accounting.test.ts — 资源计量精确算术测试
// 测试目标：decimalSum / sumResources / resourceFits / validateResources
// 业务意图：CPU/内存等小数配额按十进制精确求和与比较，避免二进制浮点误差导致准入误判
// 源：packages/opensandbox-cluster/src/services/resource-accounting.ts（main a7f477a9e）

import { describe, expect, test } from "bun:test";

// ── 复制实现 ──

interface Resources {
  cpu: number;
  memoryMb: number;
  diskGb: number;
  gpuCount: number;
}

const dimensions = ["cpu", "memoryMb", "diskGb", "gpuCount"] as const;

function decimal(value: number): [bigint, number] {
  const [mantissa, exponent = "0"] = String(value).split("e");
  const [whole = "0", fraction = ""] = mantissa!.split(".");
  return [BigInt(whole + fraction), fraction.length - Number(exponent)];
}

function decimalSum(values: number[]): number {
  const parts = values.map(decimal);
  const scale = Math.max(0, ...parts.map((p) => p[1]));
  const result = parts.reduce((sum, [value, s]) => sum + value * 10n ** BigInt(scale - s), 0n);
  return Number(`${result}e-${scale}`);
}

function sumResources(values: Resources[]): Resources {
  return Object.fromEntries(
    dimensions.map((key) => [key, decimalSum(values.map((value) => value[key]))]),
  ) as unknown as Resources;
}

function resourceFits(capacity: Resources, allocated: Resources | Resources[]): boolean {
  const values = Array.isArray(allocated) ? allocated : [allocated];
  return dimensions.every((key) => {
    const parts = [decimal(capacity[key]), ...values.map((value) => decimal(value[key]))];
    const scale = Math.max(0, ...parts.map((part) => part[1]));
    const integers = parts.map(([value, s]) => value * 10n ** BigInt(scale - s));
    return integers.slice(1).reduce((sum, value) => sum + value, 0n) <= integers[0]!;
  });
}

function validateResources(value: Resources): void {
  for (const key of dimensions)
    if (!Number.isFinite(value?.[key]) || value[key] < (key === "gpuCount" ? 0 : Number.MIN_VALUE))
      throw new Error(`invalid ${key}`);
  if (!Number.isInteger(value.gpuCount)) throw new Error("invalid gpuCount");
}

function resources(overrides: Partial<Resources> = {}): Resources {
  return { cpu: 1, memoryMb: 1024, diskGb: 10, gpuCount: 0, ...overrides };
}

// ── tests ──

describe("decimalSum 精确求和", () => {
  test("空数组和为 0", () => {
    expect(decimalSum([])).toBe(0);
  });

  test("0.1 + 0.2 精确等于 0.3", () => {
    expect(decimalSum([0.1, 0.2])).toBe(0.3);
    expect(0.1 + 0.2).not.toBe(0.3);
  });

  test("科学计数法小数精确相加", () => {
    expect(decimalSum([1e-7, 2e-7])).toBe(3e-7);
  });

  test("三位小数相加不产生尾差", () => {
    expect(decimalSum([1.005, 2.005])).toBe(3.01);
    expect(decimalSum([0.001, 0.002])).toBe(0.003);
  });

  test("正负值相抵", () => {
    expect(decimalSum([100, -50, 0.5])).toBe(50.5);
  });

  test("大整数保持精确", () => {
    expect(decimalSum([9007199254740991, 1])).toBe(9007199254740992);
  });
});

describe("sumResources 按维度求和", () => {
  test("各维度分别累加", () => {
    const result = sumResources([
      resources({ cpu: 0.1, memoryMb: 512, diskGb: 2, gpuCount: 1 }),
      resources({ cpu: 0.2, memoryMb: 512, diskGb: 3, gpuCount: 0 }),
    ]);
    expect(result).toEqual({ cpu: 0.3, memoryMb: 1024, diskGb: 5, gpuCount: 1 });
  });

  test("空列表各维度为 0", () => {
    expect(sumResources([])).toEqual({ cpu: 0, memoryMb: 0, diskGb: 0, gpuCount: 0 });
  });

  test("小数值不累积浮点误差", () => {
    const result = sumResources(Array.from({ length: 10 }, () => resources({ cpu: 0.1 })));
    expect(result.cpu).toBe(1);
  });
});

describe("resourceFits 准入比较", () => {
  test("容量充足时通过", () => {
    expect(resourceFits(resources(), resources({ cpu: 0.5, memoryMb: 512, diskGb: 5 }))).toBe(true);
  });

  test("恰好等于容量时通过", () => {
    expect(resourceFits(resources({ cpu: 0.3 }), resources({ cpu: 0.3 }))).toBe(true);
  });

  test("任一维度超出即拒绝", () => {
    expect(resourceFits(resources({ memoryMb: 512 }), resources({ memoryMb: 513 }))).toBe(false);
    expect(resourceFits(resources({ gpuCount: 0 }), resources({ gpuCount: 1 }))).toBe(false);
  });

  test("多个请求合计比较", () => {
    const small = { memoryMb: 64, diskGb: 1 };
    expect(
      resourceFits(resources({ cpu: 0.3 }), [
        resources({ ...small, cpu: 0.1 }),
        resources({ ...small, cpu: 0.2 }),
      ]),
    ).toBe(true);
    expect(
      resourceFits(resources({ cpu: 0.3 }), [
        resources({ ...small, cpu: 0.2 }),
        resources({ ...small, cpu: 0.2 }),
      ]),
    ).toBe(false);
  });

  test("0.1+0.2 不超过 0.3 容量", () => {
    const small = { memoryMb: 64, diskGb: 1 };
    expect(
      resourceFits(resources({ cpu: 0.3 }), [
        resources({ ...small, cpu: 0.1 }),
        resources({ ...small, cpu: 0.2 }),
      ]),
    ).toBe(true);
    expect(0.1 + 0.2 > 0.3).toBe(true);
  });

  test("浮点尾差的真实超额会被识别", () => {
    expect(resourceFits(resources({ cpu: 0.3 }), resources({ cpu: 0.30000000000000004 }))).toBe(false);
  });
});

describe("validateResources 入参校验", () => {
  test("合法资源通过", () => {
    expect(() => validateResources(resources())).not.toThrow();
    expect(() => validateResources(resources({ cpu: 0.001 }))).not.toThrow();
  });

  test("非有限值被拒绝", () => {
    for (const cpu of [Number.NaN, Infinity, Number.POSITIVE_INFINITY]) {
      expect(() => validateResources(resources({ cpu }))).toThrow("invalid cpu");
    }
  });

  test("非正数被拒绝（gpuCount 允许 0）", () => {
    expect(() => validateResources(resources({ cpu: 0 }))).toThrow("invalid cpu");
    expect(() => validateResources(resources({ cpu: -1 }))).toThrow("invalid cpu");
    expect(() => validateResources(resources({ memoryMb: 0 }))).toThrow("invalid memoryMb");
    expect(() => validateResources(resources({ diskGb: -0.1 }))).toThrow("invalid diskGb");
    expect(() => validateResources(resources({ gpuCount: 0 }))).not.toThrow();
    expect(() => validateResources(resources({ gpuCount: -1 }))).toThrow("invalid gpuCount");
  });

  test("gpuCount 必须是整数", () => {
    expect(() => validateResources(resources({ gpuCount: 0.5 }))).toThrow("invalid gpuCount");
    expect(() => validateResources(resources({ gpuCount: 2 }))).not.toThrow();
  });
});
