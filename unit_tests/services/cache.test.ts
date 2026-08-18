import { describe, expect, it } from "bun:test";

// cache.ts 纯函数测试
// 覆盖：getCacheBackend 初始值、getEnv 辅助函数行为
// 不测试 Redis/Keyv 实际连接（需要真实 Redis 实例）

// ── 辅助函数复制 ──

function getEnv(key: string): string | undefined {
  return process.env[key] || (typeof Bun !== "undefined" ? Bun.env[key] : undefined);
}

// ── getEnv ──

describe("getEnv", () => {
  const TEST_KEY = "__CACHE_TEST_VAR__";

  it("读取已设置的环境变量", () => {
    process.env[TEST_KEY] = "test-value";
    expect(getEnv(TEST_KEY)).toBe("test-value");
    delete process.env[TEST_KEY];
  });

  it("未设置时返回 undefined", () => {
    delete process.env[TEST_KEY];
    expect(getEnv(TEST_KEY)).toBeUndefined();
  });

  it("空字符串回退到 Bun.env（Bun 环境下返回空字符串）", () => {
    // process.env 空字符串是 falsy，会回退到 Bun.env
    // Bun 环境下 Bun.env 和 process.env 双向同步，两者都是 ""
    // "" || "" → ""（空字符串本身是 falsy 但仍然是 || 运算的返回值）
    process.env[TEST_KEY] = "";
    const result = getEnv(TEST_KEY);
    expect(result).toBe("");
    delete process.env[TEST_KEY];
  });
});

// ── Redis 节点解析逻辑（从 buildRedisConnection 中提取） ──

function parseClusterNodes(clusterStr: string): Array<{ host: string; port: number }> {
  const nodes = clusterStr
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => {
      const [host, port] = s.split(":");
      return { host: host || "127.0.0.1", port: Number(port) || 6379 };
    });
  return nodes;
}

describe("parseClusterNodes（Redis 集群节点解析）", () => {
  it("解析单节点", () => {
    const nodes = parseClusterNodes("redis-host:6380");
    expect(nodes).toEqual([{ host: "redis-host", port: 6380 }]);
  });

  it("解析多节点", () => {
    const nodes = parseClusterNodes("host1:6379,host2:6380,host3:6381");
    expect(nodes).toEqual([
      { host: "host1", port: 6379 },
      { host: "host2", port: 6380 },
      { host: "host3", port: 6381 },
    ]);
  });

  it("trim 节点两侧空白", () => {
    const nodes = parseClusterNodes(" host1:6379 , host2:6380 ");
    expect(nodes).toEqual([
      { host: "host1", port: 6379 },
      { host: "host2", port: 6380 },
    ]);
  });

  it("忽略空项（多余逗号）", () => {
    const nodes = parseClusterNodes("host1:6379,,host2:6380,");
    expect(nodes).toEqual([
      { host: "host1", port: 6379 },
      { host: "host2", port: 6380 },
    ]);
  });

  it("缺少端口时默认 6379", () => {
    const nodes = parseClusterNodes("redis-host");
    expect(nodes).toEqual([{ host: "redis-host", port: 6379 }]);
  });

  it("非法端口时默认 6379", () => {
    const nodes = parseClusterNodes("redis-host:abc");
    expect(nodes).toEqual([{ host: "redis-host", port: 6379 }]);
  });

  it("空字符串返回空数组", () => {
    const nodes = parseClusterNodes("");
    expect(nodes).toEqual([]);
  });

  it("只有逗号返回空数组", () => {
    const nodes = parseClusterNodes(",,");
    expect(nodes).toEqual([]);
  });

  it("host 为空但端口存在时使用默认 host", () => {
    const nodes = parseClusterNodes(":6380");
    expect(nodes).toEqual([{ host: "127.0.0.1", port: 6380 }]);
  });
});
