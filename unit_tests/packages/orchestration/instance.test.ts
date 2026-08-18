// instance.test.ts — Agent Instance 运行时载体测试
// 测试目标：Instance 类的状态推导、send/stop/info 行为
// 业务意图：确保 AgentNode 生命周期状态正确映射为 Instance 可见状态
// 策略：复制 Instance 类 + 错误类，mock AgentNode 接口

import { describe, test, expect } from "bun:test";

// ========== Pure function copies from packages/orchestration/src/instance/instance.ts ==========

// ---------- Types (inline) ----------

type InstanceStatus = "starting" | "running" | "stopped" | "error";

type AgentNodeStatus =
  | "uninitialized"
  | "connecting"
  | "connected"
  | "disconnected"
  | "closing"
  | "closed"
  | "destroyed";

interface InstanceInfo {
  instanceId: string;
  environmentId: string;
  agentConfigId: string;
  machineId: string;
  status: InstanceStatus;
}

// ---------- Error classes (inline) ----------

class OrchestrationError extends Error {
  readonly code: string;
  constructor(message: string, code: string) {
    super(message);
    this.name = new.target.name;
    this.code = code;
  }
}

class AgentNodeUnavailableError extends OrchestrationError {
  constructor(message = "Agent node is unavailable") {
    super(message, "AGENT_NODE_UNAVAILABLE");
  }
}

// ---------- AgentNode interface (mock-friendly) ----------

interface AgentNode {
  machineId: string;
  status(): AgentNodeStatus;
  send(data: unknown): void;
}

// ---------- Instance class (copied from source) ----------

interface InstanceParams {
  instanceId: string;
  environmentId: string;
  agentConfigId: string;
  agentNode: AgentNode;
}

const NODE_TO_INSTANCE_STATUS: Record<AgentNodeStatus, InstanceStatus> = {
  uninitialized: "starting",
  connecting: "starting",
  connected: "running",
  disconnected: "error",
  closing: "stopped",
  closed: "stopped",
  destroyed: "stopped",
};

class Instance {
  readonly instanceId: string;
  readonly environmentId: string;
  readonly agentConfigId: string;
  readonly machineId: string;
  readonly #agentNode: AgentNode;
  #terminated = false;

  constructor(params: InstanceParams) {
    this.instanceId = params.instanceId;
    this.environmentId = params.environmentId;
    this.agentConfigId = params.agentConfigId;
    this.#agentNode = params.agentNode;
    this.machineId = params.agentNode.machineId;
  }

  status(): InstanceStatus {
    if (this.#terminated) {
      return "stopped";
    }
    return NODE_TO_INSTANCE_STATUS[this.#agentNode.status()];
  }

  send(data: unknown): void {
    if (this.#terminated) {
      throw new AgentNodeUnavailableError(`Instance ${this.instanceId} is terminated`);
    }
    this.#agentNode.send(data);
  }

  stop(): void {
    if (this.#terminated) {
      return;
    }
    if (this.#agentNode.status() === "connected") {
      try {
        this.#agentNode.send({ type: "stop", instance_id: this.instanceId });
      } catch {
        // 停止帧发送失败不阻断停止流程
      }
    }
    this.#terminated = true;
  }

  info(): InstanceInfo {
    return {
      instanceId: this.instanceId,
      environmentId: this.environmentId,
      agentConfigId: this.agentConfigId,
      machineId: this.machineId,
      status: this.status(),
    };
  }
}

// ========== Test helpers ==========

function mockAgentNode(overrides: Partial<AgentNode> = {}): AgentNode & { sentMessages: unknown[] } {
  let currentNodeStatus: AgentNodeStatus = "connected";
  const sentMessages: unknown[] = [];

  return {
    machineId: "machine-1",
    sentMessages,
    status: () => currentNodeStatus,
    send: (data: unknown) => {
      sentMessages.push(data);
    },
    ...overrides,
    // Allow tests to change node status
    setStatus: (s: AgentNodeStatus) => { currentNodeStatus = s; },
  } as AgentNode & { sentMessages: unknown[]; setStatus: (s: AgentNodeStatus) => void };
}

function makeInstance(nodeOverrides?: Partial<AgentNode>): {
  instance: Instance;
  node: ReturnType<typeof mockAgentNode>;
} {
  const node = mockAgentNode(nodeOverrides);
  const instance = new Instance({
    instanceId: "inst-1",
    environmentId: "env-1",
    agentConfigId: "config-1",
    agentNode: node,
  });
  return { instance, node };
}

// ========== Tests ==========

// ── NODE_TO_INSTANCE_STATUS 映射表 ──

describe("Instance: 状态映射表完整性", () => {
  test("所有 7 种 AgentNode 状态都有映射", () => {
    const allStates: AgentNodeStatus[] = [
      "uninitialized", "connecting", "connected",
      "disconnected", "closing", "closed", "destroyed",
    ];
    for (const state of allStates) {
      expect(NODE_TO_INSTANCE_STATUS[state]).toBeDefined();
    }
  });

  test("uninitialized → starting", () => {
    expect(NODE_TO_INSTANCE_STATUS["uninitialized"]).toBe("starting");
  });

  test("connecting → starting", () => {
    expect(NODE_TO_INSTANCE_STATUS["connecting"]).toBe("starting");
  });

  test("connected → running", () => {
    expect(NODE_TO_INSTANCE_STATUS["connected"]).toBe("running");
  });

  test("disconnected → error", () => {
    expect(NODE_TO_INSTANCE_STATUS["disconnected"]).toBe("error");
  });

  test("closing → stopped", () => {
    expect(NODE_TO_INSTANCE_STATUS["closing"]).toBe("stopped");
  });

  test("closed → stopped", () => {
    expect(NODE_TO_INSTANCE_STATUS["closed"]).toBe("stopped");
  });

  test("destroyed → stopped", () => {
    expect(NODE_TO_INSTANCE_STATUS["destroyed"]).toBe("stopped");
  });
});

// ── status() 方法 ──

describe("Instance: status()", () => {
  test("节点 connected 时实例 running", () => {
    const { instance } = makeInstance();
    expect(instance.status()).toBe("running");
  });

  test("节点 connecting 时实例 starting", () => {
    const { instance, node } = makeInstance();
    (node as any).setStatus("connecting");
    expect(instance.status()).toBe("starting");
  });

  test("节点 disconnected 时实例 error", () => {
    const { instance, node } = makeInstance();
    (node as any).setStatus("disconnected");
    expect(instance.status()).toBe("error");
  });

  test("节点 closed 时实例 stopped", () => {
    const { instance, node } = makeInstance();
    (node as any).setStatus("closed");
    expect(instance.status()).toBe("stopped");
  });

  test("节点 destroyed 时实例 stopped", () => {
    const { instance, node } = makeInstance();
    (node as any).setStatus("destroyed");
    expect(instance.status()).toBe("stopped");
  });

  test("status 实时计算（不缓存）", () => {
    const { instance, node } = makeInstance();
    expect(instance.status()).toBe("running");

    (node as any).setStatus("connecting");
    expect(instance.status()).toBe("starting");

    (node as any).setStatus("connected");
    expect(instance.status()).toBe("running");
  });
});

// ── send() 方法 ──

describe("Instance: send()", () => {
  test("正常发送数据到 AgentNode", () => {
    const { instance, node } = makeInstance();
    instance.send({ type: "message", content: "hello" });

    expect(node.sentMessages).toHaveLength(1);
    expect(node.sentMessages[0]).toEqual({ type: "message", content: "hello" });
  });

  test("多次发送数据累积", () => {
    const { instance, node } = makeInstance();
    instance.send("msg1");
    instance.send("msg2");
    instance.send("msg3");

    expect(node.sentMessages).toHaveLength(3);
    expect(node.sentMessages).toEqual(["msg1", "msg2", "msg3"]);
  });

  test("terminated 后 send 抛 AgentNodeUnavailableError", () => {
    const { instance } = makeInstance();
    instance.stop();

    expect(() => instance.send("data")).toThrow(AgentNodeUnavailableError);
  });

  test("terminated 后 send 错误消息包含实例 ID", () => {
    const { instance } = makeInstance();
    instance.stop();

    try {
      instance.send("data");
      expect.unreachable("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(AgentNodeUnavailableError);
      expect((err as AgentNodeUnavailableError).message).toContain("inst-1");
      expect((err as AgentNodeUnavailableError).message).toContain("terminated");
    }
  });

  test("terminated 后 send 错误码为 AGENT_NODE_UNAVAILABLE", () => {
    const { instance } = makeInstance();
    instance.stop();

    try {
      instance.send("data");
      expect.unreachable("should have thrown");
    } catch (err) {
      expect((err as AgentNodeUnavailableError).code).toBe("AGENT_NODE_UNAVAILABLE");
    }
  });
});

// ── stop() 方法 ──

describe("Instance: stop()", () => {
  test("connected 时 stop 发送停止帧", () => {
    const { instance, node } = makeInstance();
    instance.stop();

    expect(node.sentMessages).toHaveLength(1);
    expect(node.sentMessages[0]).toEqual({ type: "stop", instance_id: "inst-1" });
  });

  test("stop 后 status 返回 stopped", () => {
    const { instance } = makeInstance();
    expect(instance.status()).toBe("running");

    instance.stop();
    expect(instance.status()).toBe("stopped");
  });

  test("stop 后即使节点状态变回 connected，实例仍 stopped", () => {
    const { instance, node } = makeInstance();
    instance.stop();

    (node as any).setStatus("connected");
    expect(instance.status()).toBe("stopped");
  });

  test("非 connected 时 stop 不发送停止帧", () => {
    const { instance, node } = makeInstance();
    (node as any).setStatus("disconnected");

    instance.stop();
    expect(node.sentMessages).toHaveLength(0);
    expect(instance.status()).toBe("stopped");
  });

  test("closing 时 stop 不发送停止帧", () => {
    const { instance, node } = makeInstance();
    (node as any).setStatus("closing");

    instance.stop();
    expect(node.sentMessages).toHaveLength(0);
  });

  test("重复调用 stop 幂等", () => {
    const { instance, node } = makeInstance();
    instance.stop();
    instance.stop();
    instance.stop();

    // 只发送一次停止帧
    expect(node.sentMessages).toHaveLength(1);
    expect(instance.status()).toBe("stopped");
  });

  test("停止帧发送失败时仍标记 terminated", () => {
    const node: AgentNode = {
      machineId: "machine-1",
      status: () => "connected",
      send: () => { throw new Error("connection broken"); },
    };
    const instance = new Instance({
      instanceId: "inst-1",
      environmentId: "env-1",
      agentConfigId: "config-1",
      agentNode: node,
    });

    // 不应抛错
    instance.stop();
    expect(instance.status()).toBe("stopped");
  });

  test("uninitialized 时 stop 不发送停止帧", () => {
    const { instance, node } = makeInstance();
    (node as any).setStatus("uninitialized");

    instance.stop();
    expect(node.sentMessages).toHaveLength(0);
    expect(instance.status()).toBe("stopped");
  });
});

// ── info() 方法 ──

describe("Instance: info()", () => {
  test("返回完整的 InstanceInfo", () => {
    const { instance } = makeInstance();
    const info = instance.info();

    expect(info.instanceId).toBe("inst-1");
    expect(info.environmentId).toBe("env-1");
    expect(info.agentConfigId).toBe("config-1");
    expect(info.machineId).toBe("machine-1");
    expect(info.status).toBe("running");
  });

  test("info 反映当前状态（starting）", () => {
    const { instance, node } = makeInstance();
    (node as any).setStatus("connecting");

    const info = instance.info();
    expect(info.status).toBe("starting");
  });

  test("info 反映当前状态（error）", () => {
    const { instance, node } = makeInstance();
    (node as any).setStatus("disconnected");

    const info = instance.info();
    expect(info.status).toBe("error");
  });

  test("info 在 stop 后反映 stopped", () => {
    const { instance } = makeInstance();
    instance.stop();

    const info = instance.info();
    expect(info.status).toBe("stopped");
  });

  test("info 返回的是快照（不可变）", () => {
    const { instance, node } = makeInstance();
    const info1 = instance.info();
    expect(info1.status).toBe("running");

    (node as any).setStatus("disconnected");
    // info1 不受影响（它是快照）
    expect(info1.status).toBe("running");

    // 新调用反映最新状态
    const info2 = instance.info();
    expect(info2.status).toBe("error");
  });

  test("machineId 来自 AgentNode", () => {
    const { instance } = makeInstance({ machineId: "special-machine" });
    expect(instance.machineId).toBe("special-machine");
    expect(instance.info().machineId).toBe("special-machine");
  });
});

// ── 构造函数 ──

describe("Instance: 构造函数", () => {
  test("构造时正确初始化所有属性", () => {
    const node: AgentNode = {
      machineId: "m-42",
      status: () => "connected",
      send: () => {},
    };
    const instance = new Instance({
      instanceId: "i-100",
      environmentId: "env-200",
      agentConfigId: "cfg-300",
      agentNode: node,
    });

    expect(instance.instanceId).toBe("i-100");
    expect(instance.environmentId).toBe("env-200");
    expect(instance.agentConfigId).toBe("cfg-300");
    expect(instance.machineId).toBe("m-42");
  });

  test("初始状态为 starting（节点 uninitialized）", () => {
    const { instance, node } = makeInstance();
    (node as any).setStatus("uninitialized");
    expect(instance.status()).toBe("starting");
  });
});

// ── 边界场景 ──

describe("Instance: 边界场景", () => {
  test("连续状态变化: starting → running → error → stopped", () => {
    const { instance, node } = makeInstance();
    (node as any).setStatus("connecting");
    expect(instance.status()).toBe("starting");

    (node as any).setStatus("connected");
    expect(instance.status()).toBe("running");

    (node as any).setStatus("disconnected");
    expect(instance.status()).toBe("error");

    instance.stop();
    expect(instance.status()).toBe("stopped");
  });

  test("send 成功后 stop 再 send 失败", () => {
    const { instance, node } = makeInstance();

    instance.send({ data: "ok" });
    expect(node.sentMessages).toHaveLength(1);

    instance.stop();
    // stop 时 connected → 发送停止帧，共 2 条
    expect(node.sentMessages).toHaveLength(2);

    expect(() => instance.send({ data: "fail" })).toThrow(AgentNodeUnavailableError);
  });
});
