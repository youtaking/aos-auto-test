// config.test.ts — opensandbox-cluster 配置加载测试
// 测试目标：loadConfig 的必填校验、默认值填充、类型校验
// 业务意图：确保集群服务启动前配置完整且安全（加密密钥 32 字节、正整数校验）

import { describe, test, expect } from "bun:test";

// ── 复制纯函数（来自 packages/opensandbox-cluster/src/config.ts）──

const required = (env: Record<string, string | undefined>, name: string): string => {
  const value = env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
};

const positiveInt = (value: string | undefined, fallback: number, name: string): number => {
  const parsed = Number(value ?? fallback);
  if (!Number.isInteger(parsed) || parsed <= 0) throw new Error(`${name} must be a positive integer`);
  return parsed;
};

function loadConfig(env: Record<string, string | undefined>): {
  port: number;
  host: string;
  databasePath: string;
  clusterServiceApiKey: string;
  serverApiKeyEncryptionKey: Uint8Array;
  proxyConnectTimeoutMs: number;
  proxyResponseTimeoutMs: number;
  frpPluginPort: number;
  frpPublicAddress: string;
  frpBindPort: number;
  frpInternalUrl: string;
  frpToken: string;
  frpConnectionStaleMs: number;
  frpHealthIntervalMs: number;
} {
  const encryptionKey = required(env, "SERVER_API_KEY_ENCRYPTION_KEY");
  const keyBytes = new TextEncoder().encode(encryptionKey);
  if (keyBytes.length !== 32) {
    throw new Error("SERVER_API_KEY_ENCRYPTION_KEY must be exactly 32 UTF-8 bytes");
  }

  return {
    port: positiveInt(env.PORT, 8080, "PORT"),
    host: env.HOST ?? "0.0.0.0",
    databasePath: env.DATABASE_PATH ?? "/data/opensandbox-cluster.db",
    clusterServiceApiKey: required(env, "CLUSTER_SERVICE_API_KEY"),
    serverApiKeyEncryptionKey: keyBytes,
    proxyConnectTimeoutMs: positiveInt(env.PROXY_CONNECT_TIMEOUT_MS, 3000, "PROXY_CONNECT_TIMEOUT_MS"),
    proxyResponseTimeoutMs: positiveInt(env.PROXY_RESPONSE_TIMEOUT_MS, 120000, "PROXY_RESPONSE_TIMEOUT_MS"),
    frpPluginPort: positiveInt(env.FRP_PLUGIN_PORT, 8081, "FRP_PLUGIN_PORT"),
    frpPublicAddress: required(env, "FRP_PUBLIC_ADDRESS"),
    frpBindPort: positiveInt(env.FRP_BIND_PORT, 7000, "FRP_BIND_PORT"),
    frpInternalUrl: env.FRP_INTERNAL_URL ?? "http://frps:7080",
    frpToken: required(env, "FRP_TOKEN"),
    frpConnectionStaleMs: positiveInt(env.FRP_CONNECTION_STALE_MS, 40000, "FRP_CONNECTION_STALE_MS"),
    frpHealthIntervalMs: positiveInt(env.FRP_HEALTH_INTERVAL_MS, 30000, "FRP_HEALTH_INTERVAL_MS"),
  };
}

// 32 字节 ASCII 密钥
const VALID_KEY = "abcdefghijklmnopqrstuvwxyz123456";

function validEnv(): Record<string, string> {
  return {
    SERVER_API_KEY_ENCRYPTION_KEY: VALID_KEY,
    CLUSTER_SERVICE_API_KEY: "cluster-key-1",
    FRP_PUBLIC_ADDRESS: "frp.example.com",
    FRP_TOKEN: "frp-token-1",
  };
}

// ── 测试 ──

describe("required", () => {
  test("正向 - 存在的键返回值", () => {
    expect(required({ A: "hello" }, "A")).toBe("hello");
  });

  test("异常 - 缺失键抛错", () => {
    expect(() => required({}, "MISSING")).toThrow("MISSING is required");
  });

  test("异常 - 空字符串视为缺失", () => {
    expect(() => required({ A: "" }, "A")).toThrow("A is required");
  });
});

describe("positiveInt", () => {
  test("正向 - 有效字符串解析为整数", () => {
    expect(positiveInt("42", 10, "X")).toBe(42);
  });

  test("正向 - undefined 使用 fallback", () => {
    expect(positiveInt(undefined, 8080, "PORT")).toBe(8080);
  });

  test("异常 - 非整数抛错", () => {
    expect(() => positiveInt("3.14", 10, "X")).toThrow("must be a positive integer");
  });

  test("异常 - 零抛错", () => {
    expect(() => positiveInt("0", 10, "X")).toThrow("must be a positive integer");
  });

  test("异常 - 负数抛错", () => {
    expect(() => positiveInt("-1", 10, "X")).toThrow("must be a positive integer");
  });

  test("异常 - 非数字抛错", () => {
    expect(() => positiveInt("abc", 10, "X")).toThrow("must be a positive integer");
  });
});

describe("loadConfig", () => {
  test("正向 - 最小配置使用全部默认值", () => {
    const config = loadConfig(validEnv());
    expect(config.port).toBe(8080);
    expect(config.host).toBe("0.0.0.0");
    expect(config.databasePath).toBe("/data/opensandbox-cluster.db");
    expect(config.proxyConnectTimeoutMs).toBe(3000);
    expect(config.proxyResponseTimeoutMs).toBe(120000);
    expect(config.frpPluginPort).toBe(8081);
    expect(config.frpBindPort).toBe(7000);
    expect(config.frpInternalUrl).toBe("http://frps:7080");
    expect(config.frpConnectionStaleMs).toBe(40000);
    expect(config.frpHealthIntervalMs).toBe(30000);
  });

  test("正向 - 自定义值覆盖默认", () => {
    const env = { ...validEnv(), PORT: "9090", HOST: "127.0.0.1" };
    const config = loadConfig(env);
    expect(config.port).toBe(9090);
    expect(config.host).toBe("127.0.0.1");
  });

  test("正向 - 加密密钥正确解析为 32 字节 Uint8Array", () => {
    const config = loadConfig(validEnv());
    expect(config.serverApiKeyEncryptionKey).toBeInstanceOf(Uint8Array);
    expect(config.serverApiKeyEncryptionKey.length).toBe(32);
  });

  test("异常 - 缺少加密密钥抛错", () => {
    const env = validEnv();
    delete env.SERVER_API_KEY_ENCRYPTION_KEY;
    expect(() => loadConfig(env)).toThrow("SERVER_API_KEY_ENCRYPTION_KEY is required");
  });

  test("异常 - 加密密钥非 32 字节抛错", () => {
    const env = { ...validEnv(), SERVER_API_KEY_ENCRYPTION_KEY: "tooshort" };
    expect(() => loadConfig(env)).toThrow("exactly 32 UTF-8 bytes");
  });

  test("异常 - 缺少 CLUSTER_SERVICE_API_KEY 抛错", () => {
    const env = validEnv();
    delete env.CLUSTER_SERVICE_API_KEY;
    expect(() => loadConfig(env)).toThrow("CLUSTER_SERVICE_API_KEY is required");
  });

  test("异常 - 缺少 FRP_PUBLIC_ADDRESS 抛错", () => {
    const env = validEnv();
    delete env.FRP_PUBLIC_ADDRESS;
    expect(() => loadConfig(env)).toThrow("FRP_PUBLIC_ADDRESS is required");
  });

  test("异常 - PORT 非法值抛错", () => {
    const env = { ...validEnv(), PORT: "not-a-number" };
    expect(() => loadConfig(env)).toThrow("PORT must be a positive integer");
  });

  test("边界 - DATABASE_PATH 自定义覆盖默认", () => {
    const env = { ...validEnv(), DATABASE_PATH: "/custom/path.db" };
    expect(loadConfig(env).databasePath).toBe("/custom/path.db");
  });
});
