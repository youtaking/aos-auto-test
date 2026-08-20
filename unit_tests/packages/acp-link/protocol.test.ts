// protocol.test.ts — ACP 协议解析层测试
// 测试目标：ACPProtocol.handleMessage 的消息分类路由（传输层/JSON-RPC/keep_alive/yjs）
// 业务意图：确保不同格式的 ACP 消息被正确派发为对应事件

import { describe, test, expect, beforeEach } from "bun:test";

// ── 复制最小 EventEmitter + ACPProtocol（来自 packages/acp-link/src/client/protocol.ts）──

type Handler<T = void> = T extends void ? () => void : (payload: T) => void;

class EventEmitter<Events extends Record<string, unknown>> {
  private handlers = new Map<string, Set<Handler<any>>>();

  on<Event extends keyof Events>(event: Event, handler: Handler<Events[Event]>): void {
    let set = this.handlers.get(event as string);
    if (!set) { set = new Set(); this.handlers.set(event as string, set); }
    set.add(handler);
  }

  off<Event extends keyof Events>(event: Event, handler: Handler<Events[Event]>): void {
    const set = this.handlers.get(event as string);
    if (set) set.delete(handler);
  }

  emit<Event extends keyof Events>(event: Event, ...args: Events[Event] extends void ? [] : [Events[Event]]): void {
    const set = this.handlers.get(event as string);
    if (!set) return;
    for (const handler of set) {
      if (args.length === 0) (handler as () => void)();
      else handler(args[0]);
    }
  }

  removeAllListeners(): void {
    this.handlers.clear();
  }
}

// 简化版 JSON-RPC 判定
function isJsonRpcMessage(parsed: unknown): boolean {
  return typeof parsed === "object" && parsed !== null && "jsonrpc" in parsed && (parsed as any).jsonrpc === "2.0";
}
function isJsonRpcResponse(msg: any): boolean {
  return "id" in msg && ("result" in msg || "error" in msg);
}
function isJsonRpcRequest(msg: any): boolean {
  return "id" in msg && "method" in msg;
}
function isJsonRpcNotification(msg: any): boolean {
  return !("id" in msg) && "method" in msg;
}
function isTransportMessage(parsed: unknown): boolean {
  if (typeof parsed !== "object" || parsed === null) return false;
  const t = (parsed as any).type;
  return ["status", "error", "pong", "prompt_complete", "permission_request", "interactive_question", "permission_response"].includes(t);
}

const ACP_METHOD = {
  SESSION_UPDATE: "session/update",
  SESSION_MODEL_CHANGED: "session/modelChanged",
  SESSION_MODE_CHANGED: "session/modeChanged",
  REQUEST_PERMISSION: "requestPermission",
};

interface ProtocolEvents {
  status: any;
  error: any;
  pong: undefined;
  session_update: any;
  permission_request: any;
  model_changed: any;
  mode_changed: any;
  rpc_response: any;
  yjs_update: any;
  prompt_complete: any;
  interactive_question: any;
  [key: string]: unknown;
}

class ACPProtocol extends EventEmitter<ProtocolEvents> {
  handleMessage(raw: string): void {
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return;
    }

    if ((parsed as any)?.type === "keep_alive") return;
    if ((parsed as any)?.type === "yjs:update") {
      const msg = parsed as any;
      this.emit("yjs_update", { docName: msg.docName, data: msg.data });
      return;
    }
    if (isTransportMessage(parsed)) {
      this.handleTransportMessage(parsed as any);
      return;
    }
    if (isJsonRpcMessage(parsed)) {
      this.handleJsonRpcMessage(parsed as any);
      return;
    }
    const t = (parsed as any).type;
    if (t === "permission_request" || t === "permission_response") {
      this.handleTransportMessage(parsed as any);
      return;
    }
  }

  private handleTransportMessage(msg: any): void {
    switch (msg.type) {
      case "status": this.emit("status", msg.payload); break;
      case "error": this.emit("error", msg.payload); break;
      case "pong": this.emit("pong"); break;
      case "prompt_complete": this.emit("prompt_complete", msg.payload); break;
      case "permission_request": this.emit("permission_request", msg.payload); break;
      case "interactive_question": this.emit("interactive_question", msg.payload); break;
    }
  }

  private handleJsonRpcMessage(msg: any): void {
    if (isJsonRpcResponse(msg)) {
      if ("result" in msg) this.emit("rpc_response", { id: msg.id, result: msg.result });
      else if ("error" in msg) this.emit("rpc_response", { id: msg.id, result: msg });
      return;
    }
    if (isJsonRpcRequest(msg) || isJsonRpcNotification(msg)) {
      this.handleNotification(msg.method, msg.params);
    }
  }

  private handleNotification(method: string, params: unknown): void {
    const p = params as any;
    switch (method) {
      case ACP_METHOD.SESSION_UPDATE:
        this.emit("session_update", { sessionId: p?.sessionId, update: p?.update });
        break;
      case ACP_METHOD.SESSION_MODEL_CHANGED:
        this.emit("model_changed", { modelId: p?.modelId });
        break;
      case ACP_METHOD.SESSION_MODE_CHANGED:
        this.emit("mode_changed", { modeId: p?.modeId });
        break;
      case ACP_METHOD.REQUEST_PERMISSION:
        this.emit("permission_request", params);
        break;
    }
  }
}

// ── 测试 ──

describe("ACPProtocol.handleMessage", () => {
  let protocol: ACPProtocol;
  let events: { name: string; payload: any }[];

  beforeEach(() => {
    protocol = new ACPProtocol();
    events = [];
    const track = (name: string) => (payload: any) => events.push({ name, payload });
    protocol.on("status", track("status"));
    protocol.on("error", track("error"));
    protocol.on("pong", () => events.push({ name: "pong", payload: undefined }));
    protocol.on("session_update", track("session_update"));
    protocol.on("permission_request", track("permission_request"));
    protocol.on("model_changed", track("model_changed"));
    protocol.on("mode_changed", track("mode_changed"));
    protocol.on("rpc_response", track("rpc_response"));
    protocol.on("yjs_update", track("yjs_update"));
    protocol.on("prompt_complete", track("prompt_complete"));
    protocol.on("interactive_question", track("interactive_question"));
  });

  test("正向 - keep_alive 被静默忽略", () => {
    protocol.handleMessage('{"type":"keep_alive"}');
    expect(events.length).toBe(0);
  });

  test("正向 - yjs:update 派发 yjs_update 事件", () => {
    protocol.handleMessage('{"type":"yjs:update","docName":"chat:abc","data":"base64data"}');
    expect(events.length).toBe(1);
    expect(events[0].name).toBe("yjs_update");
    expect(events[0].payload.docName).toBe("chat:abc");
  });

  test("正向 - transport status 派发 status 事件", () => {
    protocol.handleMessage('{"type":"status","payload":{"connected":true}}');
    expect(events[0].name).toBe("status");
    expect(events[0].payload.connected).toBe(true);
  });

  test("正向 - transport error 派发 error 事件", () => {
    protocol.handleMessage('{"type":"error","payload":{"message":"oops"}}');
    expect(events[0].name).toBe("error");
    expect(events[0].payload.message).toBe("oops");
  });

  test("正向 - transport pong 派发 pong 事件", () => {
    protocol.handleMessage('{"type":"pong"}');
    expect(events[0].name).toBe("pong");
  });

  test("正向 - prompt_complete 派发事件", () => {
    protocol.handleMessage('{"type":"prompt_complete","payload":{"stopReason":"completed"}}');
    expect(events[0].name).toBe("prompt_complete");
    expect(events[0].payload.stopReason).toBe("completed");
  });

  test("正向 - JSON-RPC response 派发 rpc_response", () => {
    protocol.handleMessage('{"jsonrpc":"2.0","id":1,"result":{"ok":true}}');
    expect(events[0].name).toBe("rpc_response");
    expect(events[0].payload.id).toBe(1);
    expect(events[0].payload.result).toEqual({ ok: true });
  });

  test("正向 - JSON-RPC error response 也派发 rpc_response", () => {
    protocol.handleMessage('{"jsonrpc":"2.0","id":2,"error":{"code":-1,"message":"fail"}}');
    expect(events[0].name).toBe("rpc_response");
    expect(events[0].payload.id).toBe(2);
  });

  test("正向 - JSON-RPC notification session/update 派发 session_update", () => {
    protocol.handleMessage('{"jsonrpc":"2.0","method":"session/update","params":{"sessionId":"s1","update":{"type":"text"}}}');
    expect(events[0].name).toBe("session_update");
    expect(events[0].payload.sessionId).toBe("s1");
  });

  test("正向 - JSON-RPC notification modelChanged 派发 model_changed", () => {
    protocol.handleMessage('{"jsonrpc":"2.0","method":"session/modelChanged","params":{"modelId":"claude-3"}}');
    expect(events[0].name).toBe("model_changed");
    expect(events[0].payload.modelId).toBe("claude-3");
  });

  test("正向 - JSON-RPC notification modeChanged 派发 mode_changed", () => {
    protocol.handleMessage('{"jsonrpc":"2.0","method":"session/modeChanged","params":{"modeId":"code"}}');
    expect(events[0].name).toBe("mode_changed");
  });

  test("正向 - JSON-RPC requestPermission 派发 permission_request", () => {
    protocol.handleMessage('{"jsonrpc":"2.0","method":"requestPermission","params":{"permissionId":"p1"}}');
    expect(events[0].name).toBe("permission_request");
  });

  test("分支 - 非法 JSON 不抛异常", () => {
    expect(() => protocol.handleMessage("not json")).not.toThrow();
    expect(events.length).toBe(0);
  });

  test("分支 - 未知格式消息不派发事件", () => {
    protocol.handleMessage('{"foo":"bar"}');
    expect(events.length).toBe(0);
  });

  test("正向 - interactive_question 派发事件", () => {
    protocol.handleMessage('{"type":"interactive_question","payload":{"questionId":"q1"}}');
    expect(events[0].name).toBe("interactive_question");
  });
});
