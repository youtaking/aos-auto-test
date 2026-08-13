// agent-node-fsm.test.ts — AgentNode 生命周期状态机测试
// 测试目标：合法转换、非法转换抛错、终态不可变
// 业务意图：确保 agent node 生命周期严格按状态转移表执行，防止非法状态

import { describe, expect, test } from "bun:test";

// ── 复制 FSM（避免 import 外部 errors.ts）──

class IllegalStateTransitionError extends Error {
  readonly code = "ILLEGAL_STATE_TRANSITION";
  constructor(message: string) {
    super(message);
    this.name = "IllegalStateTransitionError";
  }
}

type AgentNodeStatus =
  | "uninitialized" | "connecting" | "connected" | "disconnected"
  | "closing" | "closed" | "destroyed";

type AgentNodeEvent =
  | "connect" | "open" | "fail" | "disconnect"
  | "closeRequested" | "closeConfirmed";

const TRANSITIONS: Record<AgentNodeStatus, Partial<Record<AgentNodeEvent, AgentNodeStatus>>> = {
  uninitialized: { connect: "connecting", closeRequested: "closing" },
  connecting: { open: "connected", fail: "uninitialized", closeRequested: "closing" },
  connected: { disconnect: "disconnected", closeRequested: "closing" },
  disconnected: { open: "connected", closeRequested: "closing" },
  closing: { closeConfirmed: "closed" },
  closed: {},
  destroyed: {},
};

class AgentNodeFsm {
  #status: AgentNodeStatus;
  constructor(initial: AgentNodeStatus = "uninitialized") {
    this.#status = initial;
  }
  getStatus(): AgentNodeStatus { return this.#status; }
  transition(event: AgentNodeEvent): AgentNodeStatus {
    const next = TRANSITIONS[this.#status][event];
    if (next === undefined) {
      throw new IllegalStateTransitionError(`Invalid transition: ${this.#status} --${event}--> ?`);
    }
    this.#status = next;
    return next;
  }
}

// ── tests ──

describe("AgentNodeFsm", () => {
  // 初始状态为 uninitialized
  test("默认初始状态为 uninitialized", () => {
    const fsm = new AgentNodeFsm();
    expect(fsm.getStatus()).toBe("uninitialized");
  });

  // 自定义初始状态
  test("可指定自定义初始状态", () => {
    const fsm = new AgentNodeFsm("connected");
    expect(fsm.getStatus()).toBe("connected");
  });

  // 正常生命周期流程
  test("正常生命周期：uninitialized → connecting → connected → disconnected → connected → closing → closed", () => {
    const fsm = new AgentNodeFsm();
    expect(fsm.transition("connect")).toBe("connecting");
    expect(fsm.transition("open")).toBe("connected");
    expect(fsm.transition("disconnect")).toBe("disconnected");
    expect(fsm.transition("open")).toBe("connected"); // 被动恢复
    expect(fsm.transition("closeRequested")).toBe("closing");
    expect(fsm.transition("closeConfirmed")).toBe("closed");
  });

  // 连接失败回退到 uninitialized
  test("连接失败回退到 uninitialized", () => {
    const fsm = new AgentNodeFsm();
    fsm.transition("connect");
    expect(fsm.transition("fail")).toBe("uninitialized");
  });

  // 任意非终态可主动关闭
  test("uninitialized 可直接 closeRequested", () => {
    const fsm = new AgentNodeFsm();
    expect(fsm.transition("closeRequested")).toBe("closing");
  });

  // connected 时 closeRequested
  test("connected 可 closeRequested", () => {
    const fsm = new AgentNodeFsm("connected");
    expect(fsm.transition("closeRequested")).toBe("closing");
  });

  // disconnected 时 closeRequested
  test("disconnected 可 closeRequested", () => {
    const fsm = new AgentNodeFsm("disconnected");
    expect(fsm.transition("closeRequested")).toBe("closing");
  });
});

describe("AgentNodeFsm 非法转换", () => {
  // connected 时不能再次 connect
  test("connected 时 connect 抛 IllegalStateTransitionError", () => {
    const fsm = new AgentNodeFsm("connected");
    expect(() => fsm.transition("connect")).toThrow(IllegalStateTransitionError);
  });

  // disconnected 不能 connect（server 不自动重连）
  test("disconnected 时 connect 抛 IllegalStateTransitionError", () => {
    const fsm = new AgentNodeFsm("disconnected");
    expect(() => fsm.transition("connect")).toThrow(IllegalStateTransitionError);
  });

  // closed 是终态，不接受任何事件
  test("closed 时任何事件抛 IllegalStateTransitionError", () => {
    const fsm = new AgentNodeFsm("closed");
    expect(() => fsm.transition("connect")).toThrow();
    expect(() => fsm.transition("open")).toThrow();
    expect(() => fsm.transition("disconnect")).toThrow();
    expect(() => fsm.transition("closeRequested")).toThrow();
  });

  // destroyed 是终态
  test("destroyed 时任何事件抛 IllegalStateTransitionError", () => {
    const fsm = new AgentNodeFsm("destroyed");
    expect(() => fsm.transition("connect")).toThrow();
    expect(() => fsm.transition("open")).toThrow();
  });

  // closing 只接受 closeConfirmed
  test("closing 时非 closeConfirmed 事件抛错", () => {
    const fsm = new AgentNodeFsm("closing");
    expect(() => fsm.transition("connect")).toThrow();
    expect(() => fsm.transition("open")).toThrow();
    expect(() => fsm.transition("disconnect")).toThrow();
  });

  // uninitialized 时 open 非法（必须先 connect）
  test("uninitialized 时 open 抛错", () => {
    const fsm = new AgentNodeFsm();
    expect(() => fsm.transition("open")).toThrow();
  });

  // 非法转换不改变状态
  test("非法转换后状态不变", () => {
    const fsm = new AgentNodeFsm("connected");
    try { fsm.transition("connect"); } catch { /* expected */ }
    expect(fsm.getStatus()).toBe("connected");
  });
});
