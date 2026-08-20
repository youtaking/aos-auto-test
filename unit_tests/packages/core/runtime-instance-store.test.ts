// runtime-instance-store.test.ts — Core 运行时实例存储测试
// 测试目标：create/get/require/list/update/attachRuntime/setRelay/clearRelay/delete
// 业务意图：确保编排层实例生命周期管理正确，状态机推进、深拷贝隔离

import { describe, test, expect, beforeEach } from "bun:test";

// ── 复制核心逻辑（简化自 packages/core/src/runtime/runtime-instance-store.ts）──

class CoreRuntimeError extends Error {
  readonly code: string;
  readonly details?: Record<string, unknown>;
  constructor(code: string, message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "CoreRuntimeError";
    this.code = code;
    this.details = details;
  }
}

function createCoreRuntimeError(code: string, message: string, details?: Record<string, unknown>) {
  return new CoreRuntimeError(code, message, details);
}

interface AgentLaunchSpec {
  organizationId: string;
  userId: string;
  agent: { name: string; prompt?: string; extra?: Record<string, unknown> | null };
  model: { provider: string; protocol: string; baseUrl: string; apiKey: string; model: string; modelName?: string };
  skills: { name: string; url: string }[];
  mcpServers: { name: string; type: string }[];
  env?: Record<string, string>;
}

interface RuntimeInstanceRecord {
  instanceId: string;
  engineType: string;
  nodeId: string;
  status: string;
  launchSpec: AgentLaunchSpec;
  relayConnected: boolean;
  errorMessage?: string;
  pluginMetadata?: Record<string, unknown>;
  createdAt: Date;
  updatedAt: Date;
}

type RuntimeClock = () => Date;

function cloneLaunchSpec(spec: AgentLaunchSpec): AgentLaunchSpec {
  return {
    ...spec,
    env: spec.env ? { ...spec.env } : undefined,
    agent: { ...spec.agent },
    model: { ...spec.model },
    skills: spec.skills.map((s) => ({ ...s })),
    mcpServers: spec.mcpServers.map((s) => ({ ...s })),
  };
}

function toSnapshot(record: RuntimeInstanceRecord) {
  return {
    ...record,
    launchSpec: cloneLaunchSpec(record.launchSpec),
    createdAt: new Date(record.createdAt),
    updatedAt: new Date(record.updatedAt),
  };
}

function createRuntimeInstanceStore(options?: { now?: RuntimeClock }) {
  const records = new Map<string, RuntimeInstanceRecord>();
  const runtimeEntries = new Map<string, { plugin: unknown; runtime: unknown; relay: unknown }>();
  const now = options?.now ?? (() => new Date());

  return {
    create(input: { instanceId: string; engineType: string; nodeId: string; launchSpec: AgentLaunchSpec }) {
      if (records.has(input.instanceId)) {
        throw createCoreRuntimeError("INSTANCE_ALREADY_EXISTS", `already exists: ${input.instanceId}`, {
          instanceId: input.instanceId,
        });
      }
      const timestamp = now();
      const record: RuntimeInstanceRecord = {
        instanceId: input.instanceId,
        engineType: input.engineType,
        nodeId: input.nodeId,
        status: "created",
        launchSpec: cloneLaunchSpec(input.launchSpec),
        relayConnected: false,
        createdAt: timestamp,
        updatedAt: timestamp,
      };
      records.set(record.instanceId, record);
      return toSnapshot(record);
    },
    get(id: string) {
      const r = records.get(id);
      return r ? toSnapshot(r) : null;
    },
    require(id: string) {
      const r = records.get(id);
      if (!r) throw createCoreRuntimeError("INSTANCE_NOT_FOUND", `not found: ${id}`, { instanceId: id });
      return toSnapshot(r);
    },
    list() {
      return [...records.values()].map(toSnapshot);
    },
    update(id: string, input: { status?: string; launchSpec?: AgentLaunchSpec; relayConnected?: boolean; errorMessage?: string; pluginMetadata?: Record<string, unknown> }) {
      const current = records.get(id);
      if (!current) throw createCoreRuntimeError("INSTANCE_NOT_FOUND", `not found: ${id}`, { instanceId: id });
      const nextStatus = input.status ?? current.status;
      const next: RuntimeInstanceRecord = {
        ...current,
        status: nextStatus,
        launchSpec: input.launchSpec ? cloneLaunchSpec(input.launchSpec) : current.launchSpec,
        relayConnected: input.relayConnected ?? current.relayConnected,
        errorMessage: nextStatus === "error" ? (input.errorMessage ?? current.errorMessage) : undefined,
        pluginMetadata: input.pluginMetadata ?? current.pluginMetadata,
        updatedAt: now(),
      };
      records.set(id, next);
      return toSnapshot(next);
    },
    attachRuntime(id: string, entry: { plugin: unknown; runtime: unknown; relay: unknown }) {
      if (!records.has(id)) throw createCoreRuntimeError("INSTANCE_NOT_FOUND", `not found: ${id}`, { instanceId: id });
      runtimeEntries.set(id, { ...entry });
      return { ...entry };
    },
    getRuntimeEntry(id: string) {
      const e = runtimeEntries.get(id);
      return e ? { ...e } : null;
    },
    setRelay(id: string, relay: unknown) {
      const entry = runtimeEntries.get(id);
      if (!entry) throw createCoreRuntimeError("INSTANCE_NOT_FOUND", `no runtime: ${id}`, { instanceId: id });
      runtimeEntries.set(id, { ...entry, relay });
      this.update(id, { relayConnected: true });
      return { ...runtimeEntries.get(id)! };
    },
    clearRelay(id: string) {
      const entry = runtimeEntries.get(id);
      if (!entry) return null;
      runtimeEntries.set(id, { ...entry, relay: null });
      this.update(id, { relayConnected: false });
      return { ...runtimeEntries.get(id)! };
    },
    delete(id: string) {
      const deleted = records.delete(id);
      runtimeEntries.delete(id);
      return deleted;
    },
  };
}

// ── 辅助 ──

const FIXED_TIME = new Date("2026-01-01T00:00:00Z");

function makeSpec(): AgentLaunchSpec {
  return {
    organizationId: "org-1",
    userId: "user-1",
    agent: { name: "test-agent" },
    model: { provider: "openai", protocol: "openai", baseUrl: "http://api", apiKey: "sk", model: "gpt-4" },
    skills: [{ name: "skill-1", url: "http://dl" }],
    mcpServers: [{ name: "mcp-1", type: "stdio" }],
  };
}

// ── 测试 ──

describe("RuntimeInstanceStore", () => {
  let store: ReturnType<typeof createRuntimeInstanceStore>;

  beforeEach(() => {
    store = createRuntimeInstanceStore({ now: () => FIXED_TIME });
  });

  describe("create", () => {
    test("正向 - 创建实例状态为 created", () => {
      const snap = store.create({ instanceId: "i1", engineType: "opencode", nodeId: "n1", launchSpec: makeSpec() });
      expect(snap.instanceId).toBe("i1");
      expect(snap.status).toBe("created");
      expect(snap.relayConnected).toBe(false);
    });

    test("正向 - 时间戳使用注入的 clock", () => {
      const snap = store.create({ instanceId: "i1", engineType: "opencode", nodeId: "n1", launchSpec: makeSpec() });
      expect(snap.createdAt).toEqual(FIXED_TIME);
      expect(snap.updatedAt).toEqual(FIXED_TIME);
    });

    test("异常 - 重复 instanceId 抛 INSTANCE_ALREADY_EXISTS", () => {
      store.create({ instanceId: "i1", engineType: "opencode", nodeId: "n1", launchSpec: makeSpec() });
      try {
        store.create({ instanceId: "i1", engineType: "opencode", nodeId: "n1", launchSpec: makeSpec() });
        expect.unreachable("should throw");
      } catch (err) {
        expect((err as CoreRuntimeError).code).toBe("INSTANCE_ALREADY_EXISTS");
      }
    });

    test("隔离 - launchSpec 深拷贝，外部修改不影响内部", () => {
      const spec = makeSpec();
      store.create({ instanceId: "i1", engineType: "opencode", nodeId: "n1", launchSpec: spec });
      spec.agent.name = "changed";
      expect(store.get("i1")!.launchSpec.agent.name).toBe("test-agent");
    });
  });

  describe("get / require / list", () => {
    test("正向 - get 不存在返回 null", () => {
      expect(store.get("missing")).toBeNull();
    });

    test("异常 - require 不存在抛 INSTANCE_NOT_FOUND", () => {
      try {
        store.require("missing");
        expect.unreachable("should throw");
      } catch (err) {
        expect((err as CoreRuntimeError).code).toBe("INSTANCE_NOT_FOUND");
      }
    });

    test("正向 - list 返回所有实例", () => {
      store.create({ instanceId: "i1", engineType: "opencode", nodeId: "n1", launchSpec: makeSpec() });
      store.create({ instanceId: "i2", engineType: "claude-code", nodeId: "n2", launchSpec: makeSpec() });
      expect(store.list().length).toBe(2);
    });
  });

  describe("update", () => {
    test("正向 - 更新状态", () => {
      store.create({ instanceId: "i1", engineType: "opencode", nodeId: "n1", launchSpec: makeSpec() });
      const updated = store.update("i1", { status: "running" });
      expect(updated.status).toBe("running");
    });

    test("正向 - error 状态保留 errorMessage", () => {
      store.create({ instanceId: "i1", engineType: "opencode", nodeId: "n1", launchSpec: makeSpec() });
      const updated = store.update("i1", { status: "error", errorMessage: "boom" });
      expect(updated.errorMessage).toBe("boom");
    });

    test("分支 - 非 error 状态清除 errorMessage", () => {
      store.create({ instanceId: "i1", engineType: "opencode", nodeId: "n1", launchSpec: makeSpec() });
      store.update("i1", { status: "error", errorMessage: "boom" });
      const recovered = store.update("i1", { status: "running" });
      expect(recovered.errorMessage).toBeUndefined();
    });

    test("异常 - 不存在的实例抛错", () => {
      expect(() => store.update("missing", { status: "running" })).toThrow("not found");
    });
  });

  describe("attachRuntime / getRuntimeEntry", () => {
    test("正向 - 绑定后可查询", () => {
      store.create({ instanceId: "i1", engineType: "opencode", nodeId: "n1", launchSpec: makeSpec() });
      store.attachRuntime("i1", { plugin: "p", runtime: "r", relay: null });
      expect(store.getRuntimeEntry("i1")).toEqual({ plugin: "p", runtime: "r", relay: null });
    });

    test("正向 - 未绑定时返回 null", () => {
      store.create({ instanceId: "i1", engineType: "opencode", nodeId: "n1", launchSpec: makeSpec() });
      expect(store.getRuntimeEntry("i1")).toBeNull();
    });

    test("异常 - 实例不存在时抛错", () => {
      expect(() => store.attachRuntime("missing", { plugin: "p", runtime: "r", relay: null })).toThrow("not found");
    });
  });

  describe("setRelay / clearRelay", () => {
    test("正向 - setRelay 同步 relayConnected=true", () => {
      store.create({ instanceId: "i1", engineType: "opencode", nodeId: "n1", launchSpec: makeSpec() });
      store.attachRuntime("i1", { plugin: "p", runtime: "r", relay: null });
      store.setRelay("i1", "relay-handle");
      expect(store.get("i1")!.relayConnected).toBe(true);
    });

    test("正向 - clearRelay 同步 relayConnected=false", () => {
      store.create({ instanceId: "i1", engineType: "opencode", nodeId: "n1", launchSpec: makeSpec() });
      store.attachRuntime("i1", { plugin: "p", runtime: "r", relay: null });
      store.setRelay("i1", "relay-handle");
      const cleared = store.clearRelay("i1");
      expect(cleared!.relay).toBeNull();
      expect(store.get("i1")!.relayConnected).toBe(false);
    });

    test("分支 - clearRelay 无 runtime 返回 null", () => {
      store.create({ instanceId: "i1", engineType: "opencode", nodeId: "n1", launchSpec: makeSpec() });
      expect(store.clearRelay("i1")).toBeNull();
    });
  });

  describe("delete", () => {
    test("正向 - 删除后 get 返回 null", () => {
      store.create({ instanceId: "i1", engineType: "opencode", nodeId: "n1", launchSpec: makeSpec() });
      expect(store.delete("i1")).toBe(true);
      expect(store.get("i1")).toBeNull();
    });

    test("分支 - 删除不存在的返回 false", () => {
      expect(store.delete("missing")).toBe(false);
    });

    test("正向 - 删除同时清理 runtime entry", () => {
      store.create({ instanceId: "i1", engineType: "opencode", nodeId: "n1", launchSpec: makeSpec() });
      store.attachRuntime("i1", { plugin: "p", runtime: "r", relay: null });
      store.delete("i1");
      expect(store.getRuntimeEntry("i1")).toBeNull();
    });
  });
});
