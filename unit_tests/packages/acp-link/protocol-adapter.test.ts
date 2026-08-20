// protocol-adapter.test.ts — ACP ↔ SDK 协议转换测试
// 测试目标：handleAcpMessage 的消息类型路由
// 业务意图：确保 ACP 消息正确转换为 SDK 操作

import { describe, test, expect, beforeEach } from "bun:test";

// ── 复制核心逻辑（简化自 packages/acp-link/src/client/protocol-adapter.ts）──

class ProtocolAdapter {
  private abortController: AbortController | null = null;
  private sentMessages: { type: string; payload?: unknown }[] = [];

  constructor() {}

  private send(type: string, payload?: unknown): void {
    this.sentMessages.push({ type, payload });
  }

  getSent(): { type: string; payload?: unknown }[] {
    return this.sentMessages;
  }

  async handleAcpMessage(acpMessage: Record<string, unknown>): Promise<void> {
    const type = acpMessage.type as string;
    const payload = (acpMessage.payload ?? {}) as Record<string, unknown>;

    switch (type) {
      case "new_session":
        this.send("session_created", { sessionId: "claude_session" });
        break;
      case "prompt": {
        const blocks = (payload.content as Array<{ type: string; text?: string }>) ?? [];
        const input = blocks.map((b) => (b.type === "text" ? b.text : "")).join("\n");
        this.send("prompt_started", { input });
        break;
      }
      case "cancel":
        if (this.abortController) {
          this.abortController.abort();
          this.abortController = null;
        }
        this.send("prompt_complete", { stopReason: "cancelled" });
        break;
      case "list_sessions":
        this.send("session_list", { sessions: [] });
        break;
      default:
        break;
    }
  }
}

// ── 测试 ──

describe("ProtocolAdapter.handleAcpMessage", () => {
  let adapter: ProtocolAdapter;

  beforeEach(() => {
    adapter = new ProtocolAdapter();
  });

  test("正向 - new_session 发送 session_created", async () => {
    await adapter.handleAcpMessage({ type: "new_session" });
    const sent = adapter.getSent();
    expect(sent.length).toBe(1);
    expect(sent[0].type).toBe("session_created");
    expect((sent[0].payload as any).sessionId).toBe("claude_session");
  });

  test("正向 - prompt 提取文本内容并发送 prompt_started", async () => {
    await adapter.handleAcpMessage({
      type: "prompt",
      payload: {
        content: [
          { type: "text", text: "Hello" },
          { type: "text", text: "World" },
        ],
      },
    });
    const sent = adapter.getSent();
    expect(sent[0].type).toBe("prompt_started");
    expect((sent[0].payload as any).input).toBe("Hello\nWorld");
  });

  test("正向 - prompt 非文本块用空字符串替代", async () => {
    await adapter.handleAcpMessage({
      type: "prompt",
      payload: {
        content: [
          { type: "image", url: "http://img" },
          { type: "text", text: "describe" },
        ],
      },
    });
    const sent = adapter.getSent();
    expect((sent[0].payload as any).input).toBe("\ndescribe");
  });

  test("正向 - cancel 发送 prompt_complete with cancelled", async () => {
    await adapter.handleAcpMessage({ type: "cancel" });
    const sent = adapter.getSent();
    expect(sent[0].type).toBe("prompt_complete");
    expect((sent[0].payload as any).stopReason).toBe("cancelled");
  });

  test("正向 - list_sessions 返回空会话列表", async () => {
    await adapter.handleAcpMessage({ type: "list_sessions" });
    const sent = adapter.getSent();
    expect(sent[0].type).toBe("session_list");
    expect((sent[0].payload as any).sessions).toEqual([]);
  });

  test("分支 - 未知类型不发送任何消息", async () => {
    await adapter.handleAcpMessage({ type: "unknown_type" });
    expect(adapter.getSent().length).toBe(0);
  });

  test("边界 - prompt 空 content 发送空 input", async () => {
    await adapter.handleAcpMessage({ type: "prompt", payload: {} });
    expect((adapter.getSent()[0].payload as any).input).toBe("");
  });

  test("边界 - payload 缺失时不抛错", async () => {
    await adapter.handleAcpMessage({ type: "prompt" });
    expect(adapter.getSent().length).toBe(1);
  });
});
