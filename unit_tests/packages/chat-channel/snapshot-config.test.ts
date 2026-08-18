import { describe, test, expect, afterEach } from "bun:test";

// ========== Pure function copies from packages/chat-channel/src/persist/snapshot-config.ts ==========

const DEFAULT_SNAPSHOT_INTERVAL_MS = 2000;
const DEFAULT_SNAPSHOT_IDLE_MS = 500;
const DEFAULT_SNAPSHOT_TTL_SECONDS = 7 * 24 * 60 * 60;

type SnapshotEnvConfig = { intervalMs: number; idleMs: number; ttlSeconds: number };

function readPositiveIntEnv(name: string, fallback: number): number {
  const raw = process.env[name];
  if (!raw) return fallback;
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

// ========== getSnapshotEnvConfig (fresh copy without caching) ==========
// The original uses `cachedEnvConfig ??= ...` which caches forever in the module.
// For testing we re-implement the same logic without caching so each test is isolated.

function getSnapshotEnvConfigFresh(): SnapshotEnvConfig {
  return {
    intervalMs: readPositiveIntEnv("RCS_YJS_SNAPSHOT_INTERVAL_MS", DEFAULT_SNAPSHOT_INTERVAL_MS),
    idleMs: readPositiveIntEnv("RCS_YJS_SNAPSHOT_IDLE_MS", DEFAULT_SNAPSHOT_IDLE_MS),
    ttlSeconds: readPositiveIntEnv("RCS_YJS_SNAPSHOT_TTL_SECONDS", DEFAULT_SNAPSHOT_TTL_SECONDS),
  };
}

// ========== reportSnapshotCasMetric (copy with injectable metrics) ==========
// The original uses a module-level `snapshotMetrics` object. We copy the function
// and accept the metrics object as a parameter so tests can reset it between runs.

type SnapshotMetrics = { windowStart: number; windowCount: number };

function reportSnapshotCasMetric(
  log: ((msg: string) => void) | undefined,
  docName: string,
  bytes: number,
  encodeMs: number,
  casMs: number,
  persisted: boolean,
  metrics: SnapshotMetrics,
): void {
  if (!log) return;

  const now = Date.now();
  metrics.windowCount += 1;
  if (now - metrics.windowStart >= 60_000) {
    metrics.windowStart = now;
    metrics.windowCount = 1;
  }
  log(
    `[redis-provider] snapshot cas doc=${docName} bytes=${bytes} encodeMs=${encodeMs} casMs=${casMs} persisted=${persisted} casPerMin=${metrics.windowCount}`,
  );
}

// ========== Env var cleanup ==========

const ENV_KEYS = [
  "RCS_YJS_SNAPSHOT_INTERVAL_MS",
  "RCS_YJS_SNAPSHOT_IDLE_MS",
  "RCS_YJS_SNAPSHOT_TTL_SECONDS",
];

afterEach(() => {
  // 每个测试结束后清理环境变量，避免串扰
  for (const key of ENV_KEYS) {
    delete process.env[key];
  }
});

// ========== Tests ==========

describe("readPositiveIntEnv", () => {
  test("env 未设置时返回 fallback", () => {
    // 环境变量不存在，应使用默认值
    delete process.env.TEST_POSITIVE_INT;
    const result = readPositiveIntEnv("TEST_POSITIVE_INT", 42);
    expect(result).toBe(42);
  });

  test("有效正整数 → 返回解析后的值", () => {
    // 正常正整数应正确解析
    process.env.TEST_POSITIVE_INT = "100";
    const result = readPositiveIntEnv("TEST_POSITIVE_INT", 42);
    expect(result).toBe(100);
    delete process.env.TEST_POSITIVE_INT;
  });

  test("零 → 返回 fallback（非正数）", () => {
    // 0 不是正数，应回落
    process.env.TEST_POSITIVE_INT = "0";
    const result = readPositiveIntEnv("TEST_POSITIVE_INT", 42);
    expect(result).toBe(42);
    delete process.env.TEST_POSITIVE_INT;
  });

  test("负数 → 返回 fallback", () => {
    // 负数不是正数，应回落
    process.env.TEST_POSITIVE_INT = "-5";
    const result = readPositiveIntEnv("TEST_POSITIVE_INT", 42);
    expect(result).toBe(42);
    delete process.env.TEST_POSITIVE_INT;
  });

  test("NaN 字符串 → 返回 fallback", () => {
    // 非数字字符串 parseInt 返回 NaN，应回落
    process.env.TEST_POSITIVE_INT = "abc";
    const result = readPositiveIntEnv("TEST_POSITIVE_INT", 42);
    expect(result).toBe(42);
    delete process.env.TEST_POSITIVE_INT;
  });

  test("空字符串 → 返回 fallback", () => {
    // 空字符串视为未设置
    process.env.TEST_POSITIVE_INT = "";
    const result = readPositiveIntEnv("TEST_POSITIVE_INT", 42);
    expect(result).toBe(42);
    delete process.env.TEST_POSITIVE_INT;
  });

  test("小数字符串 → parseInt 截断为整数", () => {
    // "3.7" → parseInt 解析为 3（截断小数部分）
    process.env.TEST_POSITIVE_INT = "3.7";
    const result = readPositiveIntEnv("TEST_POSITIVE_INT", 42);
    expect(result).toBe(3);
    delete process.env.TEST_POSITIVE_INT;
  });

  test("带前导空格的正整数 → parseInt 自动忽略空格", () => {
    // parseInt 会忽略前导空格
    process.env.TEST_POSITIVE_INT = "  50";
    const result = readPositiveIntEnv("TEST_POSITIVE_INT", 42);
    expect(result).toBe(50);
    delete process.env.TEST_POSITIVE_INT;
  });

  test("数字后跟非数字 → parseInt 解析前缀", () => {
    // "100px" → parseInt 解析为 100
    process.env.TEST_POSITIVE_INT = "100px";
    const result = readPositiveIntEnv("TEST_POSITIVE_INT", 42);
    expect(result).toBe(100);
    delete process.env.TEST_POSITIVE_INT;
  });

  test("Infinity 字符串 → Number.isFinite 为 false → fallback", () => {
    // parseInt("Infinity") = NaN，回落
    process.env.TEST_POSITIVE_INT = "Infinity";
    const result = readPositiveIntEnv("TEST_POSITIVE_INT", 42);
    expect(result).toBe(42);
    delete process.env.TEST_POSITIVE_INT;
  });

  test("超大正整数 → 正常解析", () => {
    // 大数在安全整数范围内应正常解析
    process.env.TEST_POSITIVE_INT = "999999999";
    const result = readPositiveIntEnv("TEST_POSITIVE_INT", 42);
    expect(result).toBe(999999999);
    delete process.env.TEST_POSITIVE_INT;
  });
});

describe("getSnapshotEnvConfig (fresh, no cache)", () => {
  test("所有 env 未设置 → 返回默认值", () => {
    // 无环境变量时使用硬编码默认值
    const config = getSnapshotEnvConfigFresh();
    expect(config.intervalMs).toBe(2000);
    expect(config.idleMs).toBe(500);
    expect(config.ttlSeconds).toBe(7 * 24 * 60 * 60); // 604800 秒 = 7 天
  });

  test("所有 env 设置为有效值 → 返回自定义值", () => {
    // 三个环境变量都设置，应全部生效
    process.env.RCS_YJS_SNAPSHOT_INTERVAL_MS = "5000";
    process.env.RCS_YJS_SNAPSHOT_IDLE_MS = "1000";
    process.env.RCS_YJS_SNAPSHOT_TTL_SECONDS = "3600";

    const config = getSnapshotEnvConfigFresh();
    expect(config.intervalMs).toBe(5000);
    expect(config.idleMs).toBe(1000);
    expect(config.ttlSeconds).toBe(3600);
  });

  test("部分 env 设置 → 未设置的用默认值", () => {
    // 只设置 intervalMs，其他保持默认
    process.env.RCS_YJS_SNAPSHOT_INTERVAL_MS = "3000";

    const config = getSnapshotEnvConfigFresh();
    expect(config.intervalMs).toBe(3000);
    expect(config.idleMs).toBe(500);
    expect(config.ttlSeconds).toBe(604800);
  });

  test("env 设置为无效值（零/负/NaN）→ 对应字段用默认值", () => {
    // 无效值各自回落默认
    process.env.RCS_YJS_SNAPSHOT_INTERVAL_MS = "0";
    process.env.RCS_YJS_SNAPSHOT_IDLE_MS = "-10";
    process.env.RCS_YJS_SNAPSHOT_TTL_SECONDS = "not-a-number";

    const config = getSnapshotEnvConfigFresh();
    expect(config.intervalMs).toBe(2000);
    expect(config.idleMs).toBe(500);
    expect(config.ttlSeconds).toBe(604800);
  });

  test("默认 TTL 精确等于 7 天（604800 秒）", () => {
    // 验证常量计算正确
    const config = getSnapshotEnvConfigFresh();
    expect(config.ttlSeconds).toBe(604800);
    expect(config.ttlSeconds).toBe(7 * 24 * 60 * 60);
  });
});

describe("reportSnapshotCasMetric", () => {
  test("log 为 undefined → 不执行任何操作（no-op）", () => {
    // log=undefined 时函数应立即返回，不抛异常
    const metrics: SnapshotMetrics = { windowStart: Date.now(), windowCount: 0 };
    expect(() => {
      reportSnapshotCasMetric(undefined, "doc1", 100, 5, 3, true, metrics);
    }).not.toThrow();
    // windowCount 不应递增
    expect(metrics.windowCount).toBe(0);
  });

  test("log 为函数 → 调用并输出格式化字符串", () => {
    // log 函数应被调用一次，参数包含所有指标
    const logs: string[] = [];
    const logFn = (msg: string) => logs.push(msg);
    const metrics: SnapshotMetrics = { windowStart: Date.now(), windowCount: 0 };

    reportSnapshotCasMetric(logFn, "my-doc", 1024, 12, 8, true, metrics);

    expect(logs.length).toBe(1);
    expect(logs[0]).toContain("doc=my-doc");
    expect(logs[0]).toContain("bytes=1024");
    expect(logs[0]).toContain("encodeMs=12");
    expect(logs[0]).toContain("casMs=8");
    expect(logs[0]).toContain("persisted=true");
    expect(logs[0]).toContain("casPerMin=1");
  });

  test("windowCount 在 60 秒窗口内递增", () => {
    // 连续调用多次，casPerMin 应递增
    const logs: string[] = [];
    const logFn = (msg: string) => logs.push(msg);
    const metrics: SnapshotMetrics = { windowStart: Date.now(), windowCount: 0 };

    reportSnapshotCasMetric(logFn, "doc", 100, 1, 1, true, metrics);
    reportSnapshotCasMetric(logFn, "doc", 200, 2, 2, false, metrics);
    reportSnapshotCasMetric(logFn, "doc", 300, 3, 3, true, metrics);

    expect(logs.length).toBe(3);
    expect(logs[0]).toContain("casPerMin=1");
    expect(logs[1]).toContain("casPerMin=2");
    expect(logs[2]).toContain("casPerMin=3");
    expect(metrics.windowCount).toBe(3);
  });

  test("超过 60 秒窗口 → windowCount 重置为 1", () => {
    // windowStart 在 60 秒前，新调用应重置窗口
    const logs: string[] = [];
    const logFn = (msg: string) => logs.push(msg);
    const metrics: SnapshotMetrics = { windowStart: Date.now() - 61_000, windowCount: 50 };

    reportSnapshotCasMetric(logFn, "doc", 100, 1, 1, true, metrics);

    expect(logs.length).toBe(1);
    // 窗口重置后 casPerMin 应为 1
    expect(logs[0]).toContain("casPerMin=1");
    expect(metrics.windowCount).toBe(1);
  });

  test("恰好在 60 秒边界 → 不重置（< 60_000ms）", () => {
    // 59999ms < 60000ms，不应重置
    const logs: string[] = [];
    const logFn = (msg: string) => logs.push(msg);
    const metrics: SnapshotMetrics = { windowStart: Date.now() - 59_999, windowCount: 10 };

    reportSnapshotCasMetric(logFn, "doc", 100, 1, 1, true, metrics);

    // 未超过 60 秒，windowCount 继续递增
    expect(logs[0]).toContain("casPerMin=11");
    expect(metrics.windowCount).toBe(11);
  });

  test("persisted=false 时正确反映在日志中", () => {
    // 验证 persisted 参数为 false 的场景
    const logs: string[] = [];
    const logFn = (msg: string) => logs.push(msg);
    const metrics: SnapshotMetrics = { windowStart: Date.now(), windowCount: 0 };

    reportSnapshotCasMetric(logFn, "doc", 500, 10, 5, false, metrics);

    expect(logs[0]).toContain("persisted=false");
  });

  test("日志前缀包含 [redis-provider]", () => {
    // 验证日志格式前缀
    const logs: string[] = [];
    const logFn = (msg: string) => logs.push(msg);
    const metrics: SnapshotMetrics = { windowStart: Date.now(), windowCount: 0 };

    reportSnapshotCasMetric(logFn, "doc", 100, 1, 1, true, metrics);

    expect(logs[0]).toMatch(/^\[redis-provider\] snapshot cas /);
  });

  test("bytes=0 和 毫秒=0 的边界值", () => {
    // 零值边界情况
    const logs: string[] = [];
    const logFn = (msg: string) => logs.push(msg);
    const metrics: SnapshotMetrics = { windowStart: Date.now(), windowCount: 0 };

    reportSnapshotCasMetric(logFn, "empty-doc", 0, 0, 0, true, metrics);

    expect(logs[0]).toContain("bytes=0");
    expect(logs[0]).toContain("encodeMs=0");
    expect(logs[0]).toContain("casMs=0");
  });
});
