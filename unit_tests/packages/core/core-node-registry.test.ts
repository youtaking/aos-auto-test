// core-node-registry.test.ts — Core node 注册表测试
// 测试目标：register/get/require/list/setStatus/supportsEngine 的行为正确性
// 业务意图：确保 core 编排层可调度的 node 管理能力，重复注册拒绝、缺失查询报错

import { describe, test, expect, beforeEach } from "bun:test";

// ── 复制纯函数/类（来自 packages/core/src/registry/core-node-registry.ts + errors）──

type CoreRuntimeErrorCode =
  | "DUPLICATE_CORE_NODE"
  | "NODE_NOT_FOUND"
  | "NODE_OFFLINE";

class CoreRuntimeError extends Error {
  readonly code: CoreRuntimeErrorCode;
  readonly details?: Record<string, unknown>;
  constructor(code: CoreRuntimeErrorCode, message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "CoreRuntimeError";
    this.code = code;
    this.details = details;
  }
}

function createCoreRuntimeError(code: CoreRuntimeErrorCode, message: string, details?: Record<string, unknown>) {
  return new CoreRuntimeError(code, message, details);
}

interface CoreNode {
  id: string;
  mode: string;
  engineTypes: string[];
  status: string;
  metadata?: Record<string, unknown>;
}

interface CreateCoreNodeInput {
  id: string;
  mode: string;
  engineTypes: string[];
  status: string;
  metadata?: Record<string, unknown>;
}

function cloneNode(node: CoreNode): CoreNode {
  return {
    ...node,
    engineTypes: [...node.engineTypes],
    metadata: node.metadata ? { ...node.metadata } : undefined,
  };
}

class CoreNodeRegistry {
  private readonly nodes = new Map<string, CoreNode>();

  register(input: CreateCoreNodeInput): CoreNode {
    if (this.nodes.has(input.id)) {
      throw createCoreRuntimeError("DUPLICATE_CORE_NODE", `Core node already registered: ${input.id}`, {
        nodeId: input.id,
      });
    }
    const node: CoreNode = {
      id: input.id,
      mode: input.mode,
      engineTypes: [...new Set(input.engineTypes)],
      status: input.status,
      metadata: input.metadata ? { ...input.metadata } : undefined,
    };
    this.nodes.set(node.id, node);
    return cloneNode(node);
  }

  get(nodeId: string): CoreNode | null {
    const node = this.nodes.get(nodeId);
    return node ? cloneNode(node) : null;
  }

  require(nodeId: string): CoreNode {
    const node = this.get(nodeId);
    if (!node) {
      throw createCoreRuntimeError("NODE_NOT_FOUND", `Core node not found: ${nodeId}`, { nodeId });
    }
    return node;
  }

  list(): CoreNode[] {
    return [...this.nodes.values()].map(cloneNode);
  }

  setStatus(nodeId: string, status: string): CoreNode {
    const current = this.require(nodeId);
    const nextNode: CoreNode = {
      ...current,
      status,
      engineTypes: [...current.engineTypes],
      metadata: current.metadata ? { ...current.metadata } : undefined,
    };
    this.nodes.set(nodeId, nextNode);
    return cloneNode(nextNode);
  }

  supportsEngine(nodeId: string, engineType: string): boolean {
    const node = this.require(nodeId);
    return node.engineTypes.includes(engineType);
  }
}

// ── 测试 ──

describe("CoreNodeRegistry", () => {
  let registry: CoreNodeRegistry;

  beforeEach(() => {
    registry = new CoreNodeRegistry();
  });

  describe("register", () => {
    test("正向 - 注册后 get 返回副本", () => {
      const node = registry.register({ id: "n1", mode: "local", engineTypes: ["opencode"], status: "online" });
      expect(node.id).toBe("n1");
      expect(registry.get("n1")?.id).toBe("n1");
    });

    test("正向 - engineTypes 去重", () => {
      registry.register({ id: "n1", mode: "local", engineTypes: ["a", "a", "b"], status: "online" });
      const node = registry.get("n1");
      expect(node!.engineTypes).toEqual(["a", "b"]);
    });

    test("正向 - 返回的是副本，修改不影响注册表", () => {
      const node = registry.register({ id: "n1", mode: "local", engineTypes: ["a"], status: "online" });
      node.engineTypes.push("b");
      expect(registry.get("n1")!.engineTypes).toEqual(["a"]);
    });

    test("异常 - 重复注册抛 DUPLICATE_CORE_NODE", () => {
      registry.register({ id: "n1", mode: "local", engineTypes: [], status: "online" });
      expect(() => registry.register({ id: "n1", mode: "local", engineTypes: [], status: "online" })).toThrow(
        "Core node already registered",
      );
    });
  });

  describe("get / require", () => {
    test("正向 - get 不存在返回 null", () => {
      expect(registry.get("missing")).toBeNull();
    });

    test("正向 - require 存在返回 node", () => {
      registry.register({ id: "n1", mode: "local", engineTypes: [], status: "online" });
      expect(registry.require("n1").id).toBe("n1");
    });

    test("异常 - require 不存在抛 NODE_NOT_FOUND", () => {
      try {
        registry.require("missing");
        expect.unreachable("should throw");
      } catch (err) {
        expect(err).toBeInstanceOf(CoreRuntimeError);
        expect((err as CoreRuntimeError).code).toBe("NODE_NOT_FOUND");
      }
    });
  });

  describe("list", () => {
    test("正向 - 空注册表返回空列表", () => {
      expect(registry.list()).toEqual([]);
    });

    test("正向 - 返回所有已注册 node", () => {
      registry.register({ id: "n1", mode: "local", engineTypes: [], status: "online" });
      registry.register({ id: "n2", mode: "remote", engineTypes: [], status: "online" });
      expect(registry.list().length).toBe(2);
    });

    test("隔离 - 返回列表是副本", () => {
      registry.register({ id: "n1", mode: "local", engineTypes: ["a"], status: "online" });
      const list = registry.list();
      list[0].engineTypes.push("b");
      expect(registry.get("n1")!.engineTypes).toEqual(["a"]);
    });
  });

  describe("setStatus", () => {
    test("正向 - 更新状态", () => {
      registry.register({ id: "n1", mode: "local", engineTypes: [], status: "online" });
      const updated = registry.setStatus("n1", "offline");
      expect(updated.status).toBe("offline");
      expect(registry.get("n1")!.status).toBe("offline");
    });

    test("异常 - 不存在的 node 抛错", () => {
      expect(() => registry.setStatus("missing", "offline")).toThrow("Core node not found");
    });
  });

  describe("supportsEngine", () => {
    test("正向 - 已声明的 engine 返回 true", () => {
      registry.register({ id: "n1", mode: "local", engineTypes: ["opencode", "claude-code"], status: "online" });
      expect(registry.supportsEngine("n1", "opencode")).toBe(true);
    });

    test("分支 - 未声明的 engine 返回 false", () => {
      registry.register({ id: "n1", mode: "local", engineTypes: ["opencode"], status: "online" });
      expect(registry.supportsEngine("n1", "unknown")).toBe(false);
    });

    test("异常 - 不存在的 node 抛错", () => {
      expect(() => registry.supportsEngine("missing", "opencode")).toThrow("Core node not found");
    });
  });
});
