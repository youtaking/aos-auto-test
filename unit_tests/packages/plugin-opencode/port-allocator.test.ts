// port-allocator.test.ts — plugin-opencode 端口分配器测试
// 与 plugin-ccb 共享相同实现，独立测试确保模块隔离
import { describe, test, expect } from "bun:test";

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

describe("PortAllocator (opencode)", () => {
  test("正向 - 首次分配返回最小端口", async () => {
    const alloc = new PortAllocator(7000, 7010, { probePort: async () => true });
    expect(await alloc.allocate()).toBe(7000);
  });

  test("正向 - 分配后标记占用，下次返回下一个", async () => {
    const alloc = new PortAllocator(7000, 7010, { probePort: async () => true });
    await alloc.allocate();
    expect(await alloc.allocate()).toBe(7001);
  });

  test("正向 - 释放后复用", async () => {
    const alloc = new PortAllocator(7000, 7000, { probePort: async () => true });
    const p = await alloc.allocate();
    alloc.release(p);
    expect(await alloc.allocate()).toBe(7000);
  });

  test("分支 - probe 返回 false 的端口被跳过", async () => {
    const alloc = new PortAllocator(7000, 7005, {
      probePort: async (p) => p > 7002,
    });
    expect(await alloc.allocate()).toBe(7003);
  });

  test("异常 - 全部不可用时抛错", async () => {
    const alloc = new PortAllocator(7000, 7001, { probePort: async () => false });
    await expect(alloc.allocate()).rejects.toThrow("No available port");
  });

  test("边界 - 释放未分配的端口静默成功", () => {
    const alloc = new PortAllocator(7000, 7010);
    expect(() => alloc.release(8888)).not.toThrow();
  });
});
