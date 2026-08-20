// relay-handler.test.ts — Relay Handler 纯逻辑测试
// 测试目标：sendToInstanceRelay 的 JSON 解析和消息构建
// 业务意图：确保消息正确序列化并转发到远程机器

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数 ──

interface MachineEntry {
  ws: { readyState: number; send: (data: string) => void };
}

const machineConnections = new Map<string, MachineEntry>();

function findMachineConnectionById(instanceId: string): MachineEntry | undefined {
  return machineConnections.get(instanceId);
}

function sendToWs(ws: MachineEntry["ws"], data: Record<string, unknown>): void {
  if (ws.readyState !== 1) return;
  ws.send(JSON.stringify(data));
}

function closeInstanceRelay(instanceId: string): { sent: boolean; data?: Record<string, unknown> } {
  const entry = findMachineConnectionById(instanceId);
  if (!entry) return { sent: false };
  const data = { type: "session_end", session_id: `auto_${instanceId}` };
  sendToWs(entry.ws, data);
  return { sent: true, data };
}

function sendToInstanceRelay(instanceId: string, data: string): boolean {
  const entry = findMachineConnectionById(instanceId);
  if (!entry) return false;
  try {
    const parsed = JSON.parse(data);
    sendToWs(entry.ws, {
      type: "session_data",
      session_id: `auto_${instanceId}`,
      payload: parsed,
    });
    return true;
  } catch {
    return false;
  }
}

// ── 辅助工厂 ──

function makeWs(readyState = 1): { readyState: number; send: ReturnType<typeof mock>; sent: string[] } {
  const sent: string[] = [];
  return {
    readyState,
    send: mock((data: string) => sent.push(data)),
    sent,
  };
}

// ── tests ──

describe("relay-handler Relay 处理器", () => {
  beforeEach(() => {
    mock.restore();
    machineConnections.clear();
  });

  describe("closeInstanceRelay 关闭 Relay", () => {
    test("连接不存在时不发送", () => {
      const result = closeInstanceRelay("nonexistent");
      expect(result.sent).toBe(false);
    });

    test("连接存在时发送 session_end", () => {
      const ws = makeWs();
      machineConnections.set("inst-1", { ws });

      const result = closeInstanceRelay("inst-1");
      expect(result.sent).toBe(true);
      expect(result.data).toEqual({
        type: "session_end",
        session_id: "auto_inst-1",
      });
      expect(ws.sent.length).toBe(1);

      const sentData = JSON.parse(ws.sent[0]);
      expect(sentData.type).toBe("session_end");
      expect(sentData.session_id).toBe("auto_inst-1");
    });

    test("WS 已关闭时不发送", () => {
      const ws = makeWs(3); // CLOSED
      machineConnections.set("inst-1", { ws });

      closeInstanceRelay("inst-1");
      expect(ws.sent.length).toBe(0);
    });
  });

  describe("sendToInstanceRelay 发送数据到 Relay", () => {
    test("连接不存在返回 false", () => {
      expect(sendToInstanceRelay("nonexistent", '{"type":"test"}')).toBe(false);
    });

    test("合法 JSON 被解析并发送", () => {
      const ws = makeWs();
      machineConnections.set("inst-1", { ws });

      const result = sendToInstanceRelay("inst-1", '{"type":"prompt","text":"hello"}');
      expect(result).toBe(true);
      expect(ws.sent.length).toBe(1);

      const sentData = JSON.parse(ws.sent[0]);
      expect(sentData.type).toBe("session_data");
      expect(sentData.session_id).toBe("auto_inst-1");
      expect(sentData.payload).toEqual({ type: "prompt", text: "hello" });
    });

    test("非法 JSON 返回 false", () => {
      const ws = makeWs();
      machineConnections.set("inst-1", { ws });

      const result = sendToInstanceRelay("inst-1", "not-json{{{");
      expect(result).toBe(false);
      expect(ws.sent.length).toBe(0);
    });

    test("空字符串返回 false（JSON.parse('') 抛错）", () => {
      const ws = makeWs();
      machineConnections.set("inst-1", { ws });

      const result = sendToInstanceRelay("inst-1", "");
      expect(result).toBe(false);
    });

    test("WS 已关闭时 send 不实际发送", () => {
      const ws = makeWs(3); // CLOSED
      machineConnections.set("inst-1", { ws });

      const result = sendToInstanceRelay("inst-1", '{"type":"test"}');
      expect(result).toBe(true); // parse 成功
      expect(ws.sent.length).toBe(0); // 但 ws.send 内部检查了 readyState
    });

    test("复杂嵌套 JSON 正确转发", () => {
      const ws = makeWs();
      machineConnections.set("inst-1", { ws });

      const complexData = JSON.stringify({
        jsonrpc: "2.0",
        method: "session/prompt",
        params: { content: [{ type: "text", text: "分析代码" }] },
      });

      sendToInstanceRelay("inst-1", complexData);
      const sentData = JSON.parse(ws.sent[0]);
      expect(sentData.payload.jsonrpc).toBe("2.0");
      expect(sentData.payload.method).toBe("session/prompt");
      expect(sentData.payload.params.content).toHaveLength(1);
    });
  });
});
