// api-auth.test.ts — opensandbox-cluster API 认证中间件测试
// 测试目标：isValidClusterApiKey 的 Bearer token 校验
// 业务意图：确保集群内部 API 只接受正确的 service API key

import { describe, test, expect } from "bun:test";

// ── 复制纯函数（来自 packages/opensandbox-cluster/src/security/api-auth.ts）──

interface ClusterConfig {
  clusterServiceApiKey: string;
}

function isValidClusterApiKey(request: Request, config: ClusterConfig): boolean {
  const header = request.headers.get("authorization");
  const token = header?.match(/^Bearer\s+(.+)$/i)?.[1];
  return token === config.clusterServiceApiKey;
}

// ── 测试 ──

describe("isValidClusterApiKey", () => {
  const config = { clusterServiceApiKey: "my-secret-key" };

  test("正向 - 正确的 Bearer token 返回 true", () => {
    const req = new Request("http://localhost/api/test", {
      headers: { authorization: "Bearer my-secret-key" },
    });
    expect(isValidClusterApiKey(req, config)).toBe(true);
  });

  test("正向 - 大小写不敏感匹配 Bearer 前缀", () => {
    const req = new Request("http://localhost/api/test", {
      headers: { authorization: "bearer my-secret-key" },
    });
    expect(isValidClusterApiKey(req, config)).toBe(true);
  });

  test("分支 - 错误的 token 返回 false", () => {
    const req = new Request("http://localhost/api/test", {
      headers: { authorization: "Bearer wrong-key" },
    });
    expect(isValidClusterApiKey(req, config)).toBe(false);
  });

  test("分支 - 无 authorization header 返回 false", () => {
    const req = new Request("http://localhost/api/test");
    expect(isValidClusterApiKey(req, config)).toBe(false);
  });

  test("分支 - 非 Bearer 格式返回 false", () => {
    const req = new Request("http://localhost/api/test", {
      headers: { authorization: "Basic abc123" },
    });
    expect(isValidClusterApiKey(req, config)).toBe(false);
  });

  test("分支 - 空 Bearer token 返回 false", () => {
    const req = new Request("http://localhost/api/test", {
      headers: { authorization: "Bearer " },
    });
    expect(isValidClusterApiKey(req, config)).toBe(false);
  });

  test("边界 - Bearer 后多余空格仍正确解析", () => {
    const req = new Request("http://localhost/api/test", {
      headers: { authorization: "Bearer  my-secret-key" },
    });
    // regex \s+ 匹配多个空格
    expect(isValidClusterApiKey(req, config)).toBe(true);
  });

  test("边界 - token 含特殊字符", () => {
    const config2 = { clusterServiceApiKey: "key-with-$pecial!chars" };
    const req = new Request("http://localhost/api/test", {
      headers: { authorization: "Bearer key-with-$pecial!chars" },
    });
    expect(isValidClusterApiKey(req, config2)).toBe(true);
  });
});
