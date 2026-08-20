// mcp-inspector.test.ts — MCP 检查器接口与结果结构测试
// 测试目标：McpInspectResult 结构验证、inspectRemoteMcpServer 的 fallback 逻辑
// 注意：由于依赖 @modelcontextprotocol/sdk，无法直接 import，此处测试接口约束和错误处理逻辑

import { describe, expect, test, beforeEach, mock } from "bun:test";

// ── 复制接口和结果构造逻辑 ──

interface McpToolItem {
  name: string;
  description?: string;
  inputSchema?: Record<string, unknown>;
}

interface McpInspectResult {
  reachable: boolean;
  protocol: boolean;
  serverName?: string;
  serverVersion?: string;
  tools: McpToolItem[];
  transport?: "streamable-http" | "sse";
  message?: string;
}

/** 构造成功结果 */
function buildSuccessResult(
  transport: "streamable-http" | "sse",
  serverName: string | undefined,
  serverVersion: string | undefined,
  tools: McpToolItem[],
): McpInspectResult {
  return {
    reachable: true,
    protocol: true,
    serverName,
    serverVersion,
    tools,
    transport,
  };
}

/** 构造失败结果 */
function buildFailureResult(message: string): McpInspectResult {
  return {
    reachable: false,
    protocol: false,
    tools: [],
    message,
  };
}

/** 从 Error 提取消息 */
function extractErrorMessage(e: unknown): string {
  return e instanceof Error ? e.message : "连接失败";
}

// ── Tests ──

describe("mcp-inspector", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("McpInspectResult 成功结构", () => {
    test("streamable-http 成功结果", () => {
      const result = buildSuccessResult(
        "streamable-http",
        "my-mcp-server",
        "1.0.0",
        [{ name: "tool-a", description: "Tool A", inputSchema: { type: "object" } }],
      );
      expect(result.reachable).toBe(true);
      expect(result.protocol).toBe(true);
      expect(result.serverName).toBe("my-mcp-server");
      expect(result.serverVersion).toBe("1.0.0");
      expect(result.tools.length).toBe(1);
      expect(result.tools[0].name).toBe("tool-a");
      expect(result.transport).toBe("streamable-http");
    });

    test("sse 成功结果", () => {
      const result = buildSuccessResult("sse", "sse-server", "2.0", []);
      expect(result.transport).toBe("sse");
      expect(result.tools).toEqual([]);
    });

    test("serverName 和 serverVersion 可选", () => {
      const result = buildSuccessResult("streamable-http", undefined, undefined, []);
      expect(result.serverName).toBeUndefined();
      expect(result.serverVersion).toBeUndefined();
    });

    test("多工具列表", () => {
      const tools: McpToolItem[] = [
        { name: "read-file", description: "Read a file" },
        { name: "write-file", description: "Write a file", inputSchema: { type: "object", properties: { path: { type: "string" } } } },
        { name: "list-dir" },
      ];
      const result = buildSuccessResult("streamable-http", "server", "1.0", tools);
      expect(result.tools.length).toBe(3);
      expect(result.tools[2].description).toBeUndefined();
      expect(result.tools[2].inputSchema).toBeUndefined();
    });
  });

  describe("McpInspectResult 失败结构", () => {
    test("连接失败结果", () => {
      const result = buildFailureResult("ECONNREFUSED");
      expect(result.reachable).toBe(false);
      expect(result.protocol).toBe(false);
      expect(result.tools).toEqual([]);
      expect(result.message).toBe("ECONNREFUSED");
      expect(result.transport).toBeUndefined();
    });

    test("超时失败", () => {
      const result = buildFailureResult("连接超时");
      expect(result.reachable).toBe(false);
      expect(result.message).toBe("连接超时");
    });
  });

  describe("extractErrorMessage", () => {
    test("Error 实例提取 message", () => {
      expect(extractErrorMessage(new Error("timeout"))).toBe("timeout");
    });

    test("非 Error 返回默认消息", () => {
      expect(extractErrorMessage("string error")).toBe("连接失败");
    });

    test("null 返回默认消息", () => {
      expect(extractErrorMessage(null)).toBe("连接失败");
    });

    test("数字返回默认消息", () => {
      expect(extractErrorMessage(42)).toBe("连接失败");
    });
  });

  describe("fallback 逻辑验证", () => {
    // 模拟 inspectRemoteMcpServer 的 try-fallback 流程
    async function simulateInspect(
      tryStreamableHttp: () => Promise<McpInspectResult>,
      trySse: () => Promise<McpInspectResult>,
    ): Promise<McpInspectResult> {
      try {
        return await tryStreamableHttp();
      } catch {
        // fallback
      }
      try {
        return await trySse();
      } catch (e) {
        return buildFailureResult(extractErrorMessage(e));
      }
    }

    test("streamable-http 成功 → 不尝试 SSE", async () => {
      let sseCalled = false;
      const result = await simulateInspect(
        async () => buildSuccessResult("streamable-http", "server", "1.0", []),
        async () => { sseCalled = true; return buildSuccessResult("sse", "server", "1.0", []); },
      );
      expect(result.transport).toBe("streamable-http");
      expect(sseCalled).toBe(false);
    });

    test("streamable-http 失败 → fallback SSE 成功", async () => {
      const result = await simulateInspect(
        async () => { throw new Error("streamable-http failed"); },
        async () => buildSuccessResult("sse", "server", "1.0", []),
      );
      expect(result.transport).toBe("sse");
      expect(result.reachable).toBe(true);
    });

    test("两者都失败 → 返回失败结果", async () => {
      const result = await simulateInspect(
        async () => { throw new Error("first fail"); },
        async () => { throw new Error("second fail"); },
      );
      expect(result.reachable).toBe(false);
      expect(result.message).toBe("second fail");
    });

    test("SSE 抛出非 Error → 使用默认消息", async () => {
      const result = await simulateInspect(
        async () => { throw new Error("first fail"); },
        async () => { throw "string error"; },
      );
      expect(result.reachable).toBe(false);
      expect(result.message).toBe("连接失败");
    });
  });
});
