// scheduler-agent-executor.test.ts — Agent 任务执行器纯逻辑测试
// 测试目标：parseDefinition、extractPlainText 事件解析
// 业务意图：确保 Agent 任务从 ACP 事件流中正确提取纯文本输出

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数 ──

interface AgentDefinition {
  prompt: string;
}

function parseDefinition(raw: unknown): AgentDefinition {
  const def = (raw ?? {}) as AgentDefinition;
  return { prompt: String(def.prompt ?? "") };
}

function extractPlainText(events: Array<{ type: string; payload?: unknown }>): string {
  const lines: string[] = [];
  for (const ev of events) {
    const payload = (ev.payload ?? ev) as Record<string, unknown> | undefined;
    if (!payload) continue;

    if (payload.jsonrpc === "2.0" && (payload as any).result?.stopReason) continue;

    if (payload.method === "session/update") {
      const params = payload.params as Record<string, unknown> | undefined;
      const update = params?.update as Record<string, unknown> | undefined;
      if (!update) continue;
      if (update.sessionUpdate !== "agent_message_chunk") continue;
      const content = update.content as Record<string, unknown> | undefined;
      if (content && typeof content.text === "string") lines.push(content.text);
    }
  }
  const text = lines.join("").trim();
  return text.slice(0, 2000);
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
  beforeEach(() => {
    mock.restore();
  });

  describe("parseDefinition 定义解析", () => {
    test("正常 prompt 提取", () => {
      const result = parseDefinition({ prompt: "请分析这段代码" });
      expect(result.prompt).toBe("请分析这段代码");
    });

    test("缺失 prompt 默认空字符串", () => {
      const result = parseDefinition({});
      expect(result.prompt).toBe("");
    });

    test("null 输入默认空字符串", () => {
      const result = parseDefinition(null);
      expect(result.prompt).toBe("");
    });

    test("prompt 为数字时转为字符串", () => {
      const result = parseDefinition({ prompt: 12345 });
      expect(result.prompt).toBe("12345");
    });

    test("空字符串 prompt 保持空", () => {
      const result = parseDefinition({ prompt: "" });
      expect(result.prompt).toBe("");
    });
  });

  describe("extractPlainText 文本提取", () => {
    test("从 agent_message_chunk 提取文本", () => {
      const events = [
        makeAgentMessageChunkEvent("Hello "),
        makeAgentMessageChunkEvent("World"),
      ];
      const result = extractPlainText(events);
      expect(result).toBe("Hello World");
    });

    test("忽略 tool_call 事件", () => {
      const events = [
        makeAgentMessageChunkEvent("Before tool"),
        makeToolCallEvent(),
        makeAgentMessageChunkEvent(" After tool"),
      ];
      const result = extractPlainText(events);
      expect(result).toBe("Before tool After tool");
    });

    test("忽略 stopReason 事件", () => {
      const events = [
        makeAgentMessageChunkEvent("Content"),
        makeStopEvent(),
      ];
      const result = extractPlainText(events);
      expect(result).toBe("Content");
    });

    test("空事件数组返回空字符串", () => {
      const result = extractPlainText([]);
      expect(result).toBe("");
    });

    test("结果 trim 前后空格", () => {
      const events = [makeAgentMessageChunkEvent("  hello  ")];
      const result = extractPlainText(events);
      expect(result).toBe("hello");
    });

    test("截断到 2000 字符", () => {
      const longText = "x".repeat(3000);
      const events = [makeAgentMessageChunkEvent(longText)];
      const result = extractPlainText(events);
      expect(result.length).toBe(2000);
    });

    test("忽略非 session/update 方法的通知", () => {
      const events = [
        {
          type: "message",
          payload: {
            jsonrpc: "2.0",
            method: "session/status",
            params: { status: "running" },
          },
        },
        makeAgentMessageChunkEvent("Real content"),
      ];
      const result = extractPlainText(events);
      expect(result).toBe("Real content");
    });

    test("忽略无 content 的 agent_message_chunk", () => {
      const events = [
        {
          type: "message",
          payload: {
            jsonrpc: "2.0",
            method: "session/update",
            params: {
              update: { sessionUpdate: "agent_message_chunk" },
            },
          },
        },
      ];
      const result = extractPlainText(events);
      expect(result).toBe("");
    });

    test("忽略非 text 类型的 content", () => {
      const events = [
        {
          type: "message",
          payload: {
            jsonrpc: "2.0",
            method: "session/update",
            params: {
              update: {
                sessionUpdate: "agent_message_chunk",
                content: { type: "image", url: "https://example.com/img.png" },
              },
            },
          },
        },
      ];
      const result = extractPlainText(events);
      expect(result).toBe("");
    });

    test("混合事件流正确提取", () => {
      const events = [
        makeAgentMessageChunkEvent("第一段"),
        makeToolCallEvent(),
        makeAgentMessageChunkEvent("第二段"),
        makeStopEvent(),
        makeAgentMessageChunkEvent("第三段"),
      ];
      const result = extractPlainText(events);
      expect(result).toBe("第一段第二段第三段");
    });

    test("原始 jsonrpc 格式事件正确提取", () => {
      const events = [
        {
          type: "raw",
          payload: {
            jsonrpc: "2.0",
            method: "session/update",
            params: {
              update: {
                sessionUpdate: "agent_message_chunk",
                content: { text: "raw text" },
              },
            },
          },
        },
      ];
      const result = extractPlainText(events);
      expect(result).toBe("raw text");
    });

    test("无 payload 时跳过", () => {
      const events = [{ type: "empty" }];
      const result = extractPlainText(events);
      expect(result).toBe("");
    });
  });
});
