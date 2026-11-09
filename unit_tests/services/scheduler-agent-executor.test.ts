// scheduler-agent-executor.test.ts — Agent 任务执行器纯逻辑测试
// 测试目标：parseDefinition、extractPlainText 单事件解析、MCP 初始化等待判定
// 业务意图：确保 Agent 任务从 ACP 事件流中正确提取纯文本输出，且等待窗口不拖垮预算
// 源：packages/resources/task/src/server/services/scheduler/agent-executor.ts（main a7f477a9e）

import { describe, expect, test } from "bun:test";

// ── 复制纯函数 ──

interface AgentDefinition {
  prompt: string;
}

function parseDefinition(raw: unknown): AgentDefinition {
  const def = raw as AgentDefinition;
  return { prompt: String(def.prompt ?? "") };
}

function extractJsonRpc(msg: unknown): Record<string, unknown> | null {
  const record = msg as Record<string, unknown>;
  if (record.jsonrpc === "2.0") return record;
  const payload = record.payload as Record<string, unknown> | undefined;
  if (payload?.jsonrpc === "2.0") return payload;
  return null;
}

/** 只保留有界文本摘要：单事件输入，非 agent_message_chunk 返回空串。 */
function extractPlainText(event: unknown): string {
  const rpc = extractJsonRpc(event);
  if (rpc?.method !== "session/update") return "";
  const params = rpc.params as Record<string, unknown> | undefined;
  const update = params?.update as Record<string, unknown> | undefined;
  if (update?.sessionUpdate !== "agent_message_chunk") return "";
  const content = update.content as Record<string, unknown> | undefined;
  return typeof content?.text === "string" ? content.text : "";
}

/** 剩余预算必须严格大于等待窗口才值得等，否则等待会把任务拖到超时。 */
function shouldWaitForMcpInit(remainingMs: number, mcpInitGraceMs: number): boolean {
  return mcpInitGraceMs > 0 && remainingMs > mcpInitGraceMs;
}

// ── 辅助工厂 ──

function makeAgentMessageChunkEvent(text: string) {
  return {
    type: "message",
    payload: {
      jsonrpc: "2.0",
      method: "session/update",
      params: {
        update: {
          sessionUpdate: "agent_message_chunk",
          content: { type: "text", text },
        },
      },
    },
  };
}

function makeStopEvent() {
  return {
    type: "message",
    payload: {
      jsonrpc: "2.0",
      result: { stopReason: "end_turn" },
    },
  };
}

function makeToolCallEvent() {
  return {
    type: "message",
    payload: {
      jsonrpc: "2.0",
      method: "session/update",
      params: {
        update: {
          sessionUpdate: "tool_call",
          content: { toolName: "read_file" },
        },
      },
    },
  };
}

// ── tests ──

describe("scheduler-agent-executor Agent 执行器", () => {
  describe("parseDefinition 定义解析", () => {
    test("正常 prompt 提取", () => {
      expect(parseDefinition({ prompt: "请分析这段代码" }).prompt).toBe("请分析这段代码");
    });

    test("缺失 prompt 默认空字符串", () => {
      expect(parseDefinition({}).prompt).toBe("");
    });

    test("prompt 为数字时转为字符串", () => {
      expect(parseDefinition({ prompt: 12345 }).prompt).toBe("12345");
    });

    test("空字符串 prompt 保持空", () => {
      expect(parseDefinition({ prompt: "" }).prompt).toBe("");
    });
  });

  describe("extractPlainText 单事件文本提取", () => {
    test("从 agent_message_chunk 提取文本", () => {
      expect(extractPlainText(makeAgentMessageChunkEvent("Hello World"))).toBe("Hello World");
    });

    test("忽略 tool_call 事件", () => {
      expect(extractPlainText(makeToolCallEvent())).toBe("");
    });

    test("忽略 stopReason 结果事件", () => {
      expect(extractPlainText(makeStopEvent())).toBe("");
    });

    test("忽略非 session/update 方法的通知", () => {
      const event = {
        jsonrpc: "2.0",
        method: "session/status",
        params: { status: "running" },
      };
      expect(extractPlainText(event)).toBe("");
    });

    test("忽略无 content 的 agent_message_chunk", () => {
      const event = {
        jsonrpc: "2.0",
        method: "session/update",
        params: { update: { sessionUpdate: "agent_message_chunk" } },
      };
      expect(extractPlainText(event)).toBe("");
    });

    test("忽略非 text 类型的 content", () => {
      const event = {
        jsonrpc: "2.0",
        method: "session/update",
        params: {
          update: {
            sessionUpdate: "agent_message_chunk",
            content: { type: "image", url: "https://example.com/img.png" },
          },
        },
      };
      expect(extractPlainText(event)).toBe("");
    });

    test("无 payload 的事件返回空串", () => {
      expect(extractPlainText({ type: "empty" })).toBe("");
    });

    test("直接 JSON-RPC（无 payload 包裹）也能提取", () => {
      const event = {
        jsonrpc: "2.0",
        method: "session/update",
        params: {
          update: { sessionUpdate: "agent_message_chunk", content: { text: "raw text" } },
        },
      };
      expect(extractPlainText(event)).toBe("raw text");
    });

    test("多事件逐条提取后拼接并截断", () => {
      const events = [
        makeAgentMessageChunkEvent("第一段"),
        makeToolCallEvent(),
        makeAgentMessageChunkEvent("第二段"),
      ];
      let summary = "";
      for (const event of events) summary = (summary + extractPlainText(event)).slice(0, 2000);
      expect(summary).toBe("第一段第二段");
    });
  });

  describe("shouldWaitForMcpInit 等待窗口判定", () => {
    test("预算充足时等待", () => {
      expect(shouldWaitForMcpInit(5000, 1000)).toBe(true);
    });

    test("预算恰好等于窗口时不等", () => {
      expect(shouldWaitForMcpInit(1000, 1000)).toBe(false);
    });

    test("预算不足时不等", () => {
      expect(shouldWaitForMcpInit(500, 1000)).toBe(false);
    });

    test("窗口为 0 时不等", () => {
      expect(shouldWaitForMcpInit(5000, 0)).toBe(false);
    });
  });
});
