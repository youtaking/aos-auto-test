// port-allocator.test.ts — plugin-ccb 端口分配器测试
// 测试目标：PortAllocator 的分配、释放、范围耗尽行为
// 业务意图：确保本地 ACP 实例端口不冲突，耗尽时明确报错

import { describe, test, expect, beforeEach } from "bun:test";

// ── 复制纯函数（来自 packages/plugin-ccb/src/process/port-allocator.ts）──

const PORT_MIN = 8888;
const PORT_MAX = 8999;

interface PortAllocatorDependencies {
  probePort?: (port: number) => Promise<boolean>;
}

class PortAllocator {
  private readonly occupied = new Set<number>();
  private readonly probePort: (port: number) => Promise<boolean>;

  constructor(
    private readonly minPort = PORT_MIN,
    private readonly maxPort = PORT_MAX,
    dependencies: PortAllocatorDependencies = {},
  ) {
    this.probePort = dependencies.probePort ?? (async () => true);
  }

  async allocate(): Promise<number> {
    for (let port = this.minPort; port <= this.maxPort; port += 1) {
      if (this.occupied.has(port)) continue;
      if (!(await this.probePort(port))) continue;
      this.occupied.add(port);
      return port;
    }
    throw new Error(`No available port in range ${this.minPort}-${this.maxPort}`);
  }

  release(port: number): void {
    this.occupied.delete(port);
  }
}

function createPortAllocator(dependencies: PortAllocatorDependencies = {}): PortAllocator {
  return new PortAllocator(PORT_MIN, PORT_MAX, dependencies);
}

// ── 测试 ──

describe("PortAllocator", () => {
  test("正向 - 首次分配返回最小端口", async () => {
    const allocator = new PortAllocator(9000, 9010, { probePort: async () => true });
    expect(await allocator.allocate()).toBe(9000);
  });

  test("正向 - 连续分配返回递增端口", async () => {
    const allocator = new PortAllocator(9000, 9010, { probePort: async () => true });
    const p1 = await allocator.allocate();
    const p2 = await allocator.allocate();
    expect(p1).toBe(9000);
    expect(p2).toBe(9001);
  });

  test("正向 - 释放后可重新分配", async () => {
    const allocator = new PortAllocator(9000, 9000, { probePort: async () => true });
    const p1 = await allocator.allocate();
    expect(p1).toBe(9000);
    allocator.release(9000);
    const p2 = await allocator.allocate();
    expect(p2).toBe(9000);
  });

  test("分支 - probe 失败的端口被跳过", async () => {
    const allocator = new PortAllocator(9000, 9005, {
      probePort: async (port) => port !== 9000,
    });
    expect(await allocator.allocate()).toBe(9001);
  });

  test("分支 - 已占用端口被跳过", async () => {
    const allocator = new PortAllocator(9000, 9010, { probePort: async () => true });
    await allocator.allocate(); // 9000
    expect(await allocator.allocate()).toBe(9001);
  });

  test("异常 - 范围内无可用端口抛错", async () => {
    const allocator = new PortAllocator(9000, 9001, { probePort: async () => false });
    await expect(allocator.allocate()).rejects.toThrow("No available port in range 9000-9001");
  });

  test("异常 - 全部占用时抛错", async () => {
    const allocator = new PortAllocator(9000, 9000, { probePort: async () => true });
    await allocator.allocate();
    await expect(allocator.allocate()).rejects.toThrow("No available port");
  });

  test("边界 - 单端口范围正常分配", async () => {
    const allocator = new PortAllocator(9000, 9000, { probePort: async () => true });
    expect(await allocator.allocate()).toBe(9000);
  });

  test("隔离 - 释放不存在的端口不抛错", () => {
    const allocator = new PortAllocator(9000, 9010);
    expect(() => allocator.release(9999)).not.toThrow();
  });
});

describe("createPortAllocator", () => {
  test("正向 - 使用默认端口范围 8888-8999", async () => {
    const allocator = createPortAllocator({ probePort: async () => true });
    expect(await allocator.allocate()).toBe(PORT_MIN);
  });
});
