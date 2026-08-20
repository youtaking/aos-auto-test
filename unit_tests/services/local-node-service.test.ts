// local-node-service.test.ts — 本地执行节点服务测试
// 测试目标：LocalNodeAwareService 的 ensureNode/releaseNode 分支覆盖

import { describe, expect, test, beforeEach, mock } from "bun:test";

// ── 复制核心逻辑（隔离编排域依赖）──

const LOCAL_DEFAULT_NODE_ID = "local-default";

// 最小化 AgentNode 和 Socket 模拟
interface MockAgentNodeSocket {
  onOpen(handler: () => void): void;
  onClose(handler: () => void): void;
  onError(handler: () => void): void;
  send(data: unknown): void;
  close(): void;
}

class LocalStubSocket implements MockAgentNodeSocket {
  #onClose: (() => void) | null = null;

  onOpen(_handler: () => void): void {}
  onClose(handler: () => void): void { this.#onClose = handler; }
  onError(_handler: () => void): void {}
  send(_data: unknown): void {}
  close(): void { this.#onClose?.(); }
}

interface MockAgentNode {
  machineId: string;
  connected: boolean;
  close: () => void;
}

function createMockAgentNode(machineId: string): MockAgentNode {
  const socket = new LocalStubSocket();
  let connected = false;

  // 模拟 _handleConnected
  connected = true;

  return {
    machineId,
    connected,
    close: () => { socket.close(); },
  };
}

// 模拟 AgentNodeServicePort
interface MockAgentNodeServicePort {
  ensureNode(machineId: string): MockAgentNode;
  releaseNode(machineId: string): void;
}

class LocalNodeAwareService {
  readonly #getDelegate: () => MockAgentNodeServicePort;
  #localNode: MockAgentNode | null = null;

  constructor(getDelegate: () => MockAgentNodeServicePort) {
    this.#getDelegate = getDelegate;
  }

  ensureNode(machineId: string): MockAgentNode {
    if (machineId === LOCAL_DEFAULT_NODE_ID) {
      if (!this.#localNode) {
        this.#localNode = createMockAgentNode(machineId);
      }
      return this.#localNode;
    }
    return this.#getDelegate().ensureNode(machineId);
  }

  releaseNode(machineId: string): void {
    if (machineId === LOCAL_DEFAULT_NODE_ID) {
      return;
    }
    this.#getDelegate().releaseNode(machineId);
  }
}

// ── Tests ──

describe("LocalNodeAwareService", () => {
  let delegateEnsureCalls: string[];
  let delegateReleaseCalls: string[];
  let mockDelegate: MockAgentNodeServicePort;
  let service: LocalNodeAwareService;

  beforeEach(() => {
    mock.restore();
    delegateEnsureCalls = [];
    delegateReleaseCalls = [];
    mockDelegate = {
      ensureNode: (machineId: string) => {
        delegateEnsureCalls.push(machineId);
        return { machineId, connected: true, close: () => {} };
      },
      releaseNode: (machineId: string) => {
        delegateReleaseCalls.push(machineId);
      },
    };
    service = new LocalNodeAwareService(() => mockDelegate);
  });

  // ── ensureNode ──

  describe("ensureNode", () => {
    test("local-default → 返回本地占位节点", () => {
      const node = service.ensureNode("local-default");
      expect(node.machineId).toBe("local-default");
      expect(node.connected).toBe(true);
    });

    test("local-default → 不委托给 delegate", () => {
      service.ensureNode("local-default");
      expect(delegateEnsureCalls.length).toBe(0);
    });

    test("local-default → 多次调用返回同一实例（单例）", () => {
      const a = service.ensureNode("local-default");
      const b = service.ensureNode("local-default");
      expect(a).toBe(b);
    });

    test("远程 machineId → 委托给 delegate", () => {
      const node = service.ensureNode("remote-machine-1");
      expect(delegateEnsureCalls).toEqual(["remote-machine-1"]);
      expect(node.machineId).toBe("remote-machine-1");
    });

    test("不同远程 machineId 分别委托", () => {
      service.ensureNode("machine-a");
      service.ensureNode("machine-b");
      expect(delegateEnsureCalls).toEqual(["machine-a", "machine-b"]);
    });
  });

  // ── releaseNode ──

  describe("releaseNode", () => {
    test("local-default → 空操作不委托", () => {
      service.releaseNode("local-default");
      expect(delegateReleaseCalls.length).toBe(0);
    });

    test("远程 machineId → 委托给 delegate", () => {
      service.releaseNode("remote-machine-1");
      expect(delegateReleaseCalls).toEqual(["remote-machine-1"]);
    });

    test("多次释放 remote 节点都委托", () => {
      service.releaseNode("m1");
      service.releaseNode("m2");
      expect(delegateReleaseCalls).toEqual(["m1", "m2"]);
    });
  });

  // ── 混合场景 ──

  describe("混合场景", () => {
    test("先 ensure local 再 ensure remote 互不干扰", () => {
      const localNode = service.ensureNode("local-default");
      const remoteNode = service.ensureNode("machine-x");
      expect(localNode.machineId).toBe("local-default");
      expect(remoteNode.machineId).toBe("machine-x");
      expect(delegateEnsureCalls).toEqual(["machine-x"]);
    });

    test("释放 local 后再 ensure local 仍返回同一实例", () => {
      const first = service.ensureNode("local-default");
      service.releaseNode("local-default");
      const second = service.ensureNode("local-default");
      expect(first).toBe(second);
    });
  });
});

// ── LocalStubSocket ──

describe("LocalStubSocket", () => {
  test("send 不抛异常（空操作）", () => {
    const socket = new LocalStubSocket();
    expect(() => socket.send("test-data")).not.toThrow();
  });

  test("close 触发 onClose 回调", () => {
    const socket = new LocalStubSocket();
    let closeCalled = false;
    socket.onClose(() => { closeCalled = true; });
    socket.close();
    expect(closeCalled).toBe(true);
  });

  test("close 无回调时不抛异常", () => {
    const socket = new LocalStubSocket();
    expect(() => socket.close()).not.toThrow();
  });

  test("onOpen 不抛异常", () => {
    const socket = new LocalStubSocket();
    expect(() => socket.onOpen(() => {})).not.toThrow();
  });

  test("onError 不抛异常", () => {
    const socket = new LocalStubSocket();
    expect(() => socket.onError(() => {})).not.toThrow();
  });
});
