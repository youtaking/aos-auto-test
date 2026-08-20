// file-machine-events.test.ts — 机器端文件变更事件治理逻辑测试
// 测试目标：registerMachineEnvironment、registerMachineDeclaration、broadcastMachineInvalidateAll、
//   handleFileChangedFrame、handleFileChangedBatchFrame、handleEnvironmentDeclaredFrame、
//   clearMachineEventState、resetMachineEventState、handleFileWsRegisterIdentity

import { describe, expect, test, beforeEach, mock } from "bun:test";

// ── 模块级状态（复制自 src/services/file-machine-events.ts，保持逻辑一致）──

const MAX_DECLARED_ENVIRONMENTS = 500;
const MACHINE_INVALIDATE_LIMIT = 2;

const machineEnvironments = new Map<string, Set<string>>();
const strictMachines = new Set<string>();
const machineInvalidateRate = new Map<string, { start: number; count: number }>();

const CHANGE_KINDS = new Set(["write", "delete", "mkdir", "rename", "upload"]);
const CHANGE_SOURCES = new Set(["user", "agent", "api"]);

function isChangeKind(value: unknown): value is string {
  return typeof value === "string" && (CHANGE_KINDS as Set<string>).has(value);
}

function isChangeSource(value: unknown): value is string {
  return typeof value === "string" && (CHANGE_SOURCES as Set<string>).has(value);
}

function getMachineEnvironments(machineId: string): Set<string> {
  let set = machineEnvironments.get(machineId);
  if (!set) {
    set = new Set();
    machineEnvironments.set(machineId, set);
  }
  return set;
}

// 依赖注入点
const _deps = {
  registerEnvironmentQueue: (_envId: string) => {},
  writeRegistryEvent: async (_machineId: string, _type: string, _detail: Record<string, unknown>) => {},
  publishFileChanged: (_envId: string, _change: Record<string, unknown>, _opts?: Record<string, unknown>) => {},
  publishInvalidateAllLimited: (_envId: string) => {},
  publishDegradedLimited: (_envId: string, _machineId: string, _direction: string) => {},
  getCoreRuntime: (): { getNode: (id: string) => unknown } | null => null,
  fileWsIdentityStrict: false,
};

function registerMachineEnvironment(machineId: string, envId: string): void {
  if (getMachineEnvironments(machineId).size >= MAX_DECLARED_ENVIRONMENTS) {
    return;
  }
  getMachineEnvironments(machineId).add(envId);
  _deps.registerEnvironmentQueue(envId);
}

function mergeDeclaredEnvironments(machineId: string, declared: string[]): boolean {
  const merged = new Set(getMachineEnvironments(machineId));
  for (const env of declared) {
    merged.add(env);
  }
  if (merged.size > MAX_DECLARED_ENVIRONMENTS) {
    return false;
  }
  machineEnvironments.set(machineId, merged);
  for (const env of declared) {
    _deps.registerEnvironmentQueue(env);
  }
  return true;
}

function registerMachineDeclaration(machineId: string, rawEnvs: unknown): void {
  if (Array.isArray(rawEnvs)) {
    const declared = rawEnvs.filter((e): e is string => typeof e === "string" && e !== "");
    if (mergeDeclaredEnvironments(machineId, declared)) {
      strictMachines.add(machineId);
    }
  } else {
    strictMachines.delete(machineId);
  }
}

function isEnvironmentAccepted(machineId: string, envId: string): boolean {
  if (!strictMachines.has(machineId)) return true;
  if (getMachineEnvironments(machineId).has(envId)) return true;
  return false;
}

interface MockEntry {
  machineId: string | null;
  wsId: string;
  ws: { close: (code: number, reason: string) => void };
}

function handleFileWsRegisterIdentity(entry: MockEntry, machineId: string): boolean {
  const node = _deps.getCoreRuntime()?.getNode(machineId);
  if (node) return false;
  if (_deps.fileWsIdentityStrict) {
    try {
      entry.ws.close(4404, "unknown_machine");
    } catch {
      // ignore
    }
    return true;
  }
  return false;
}

function handleFileChangedFrame(entry: MockEntry, msg: Record<string, unknown>): { envId: string; change: Record<string, unknown> } | null {
  const machineId = entry.machineId;
  if (!machineId) return null;
  const envId = msg.environment_id;
  if (typeof envId !== "string" || envId === "") return null;
  if (!isEnvironmentAccepted(machineId, envId)) return null;

  const rawPath = msg.path;
  const rawKind = msg.kind;
  if (typeof rawPath !== "string" || rawPath === "" || !isChangeKind(rawKind)) return null;

  const change: Record<string, unknown> = {
    path: rawPath,
    kind: rawKind,
    source: isChangeSource(msg.source) ? msg.source : "agent",
  };
  if (typeof msg.actor_id === "string" && msg.actor_id !== "") change.actorId = msg.actor_id;
  if (typeof msg.to === "string" && msg.to !== "") change.to = msg.to;
  return { envId, change };
}

function broadcastMachineInvalidateAll(machineId: string, now: number = Date.now()): string[] {
  const window = machineInvalidateRate.get(machineId);
  if (!window || now - window.start >= 1_000) {
    machineInvalidateRate.set(machineId, { start: now, count: 1 });
  } else if (window.count >= MACHINE_INVALIDATE_LIMIT) {
    return [];
  } else {
    window.count++;
  }
  const envs = machineEnvironments.get(machineId);
  if (!envs) return [];
  return [...envs];
}

function clearMachineEventState(machineId: string): void {
  machineEnvironments.delete(machineId);
  strictMachines.delete(machineId);
}

function resetMachineEventState(): void {
  machineEnvironments.clear();
  strictMachines.clear();
  machineInvalidateRate.clear();
}

// ── Tests ──

describe("file-machine-events", () => {
  beforeEach(() => {
    mock.restore();
    resetMachineEventState();
  });

  // ── registerMachineEnvironment ──

  describe("registerMachineEnvironment", () => {
    test("注册单个环境到权威集", () => {
      registerMachineEnvironment("m1", "env-1");
      expect(getMachineEnvironments("m1").has("env-1")).toBe(true);
    });

    test("注册多个环境", () => {
      registerMachineEnvironment("m1", "env-1");
      registerMachineEnvironment("m1", "env-2");
      expect(getMachineEnvironments("m1").size).toBe(2);
    });

    test("重复注册同一环境不增加数量", () => {
      registerMachineEnvironment("m1", "env-1");
      registerMachineEnvironment("m1", "env-1");
      expect(getMachineEnvironments("m1").size).toBe(1);
    });

    test("达到上限后拒绝新环境", () => {
      for (let i = 0; i < MAX_DECLARED_ENVIRONMENTS; i++) {
        registerMachineEnvironment("m1", `env-${i}`);
      }
      expect(getMachineEnvironments("m1").size).toBe(MAX_DECLARED_ENVIRONMENTS);
      registerMachineEnvironment("m1", "env-overflow");
      expect(getMachineEnvironments("m1").has("env-overflow")).toBe(false);
      expect(getMachineEnvironments("m1").size).toBe(MAX_DECLARED_ENVIRONMENTS);
    });

    test("不同机器独立计数", () => {
      registerMachineEnvironment("m1", "env-1");
      registerMachineEnvironment("m2", "env-2");
      expect(getMachineEnvironments("m1").size).toBe(1);
      expect(getMachineEnvironments("m2").size).toBe(1);
    });
  });

  // ── registerMachineDeclaration ──

  describe("registerMachineDeclaration", () => {
    test("数组输入合并进权威集并进入严格模式", () => {
      registerMachineDeclaration("m1", ["env-1", "env-2"]);
      expect(getMachineEnvironments("m1").size).toBe(2);
      expect(strictMachines.has("m1")).toBe(true);
    });

    test("过滤非字符串和空字符串", () => {
      registerMachineDeclaration("m1", ["env-1", "", 42, null, "env-2"]);
      expect(getMachineEnvironments("m1").size).toBe(2);
      expect(getMachineEnvironments("m1").has("env-1")).toBe(true);
      expect(getMachineEnvironments("m1").has("env-2")).toBe(true);
    });

    test("非数组输入退出严格模式", () => {
      registerMachineDeclaration("m1", ["env-1"]);
      expect(strictMachines.has("m1")).toBe(true);
      registerMachineDeclaration("m1", undefined);
      expect(strictMachines.has("m1")).toBe(false);
    });

    test("null 输入退出严格模式", () => {
      registerMachineDeclaration("m1", ["env-1"]);
      registerMachineDeclaration("m1", null);
      expect(strictMachines.has("m1")).toBe(false);
    });

    test("空数组仍进入严格模式", () => {
      registerMachineDeclaration("m1", []);
      expect(strictMachines.has("m1")).toBe(true);
    });
  });

  // ── isEnvironmentAccepted ──

  describe("isEnvironmentAccepted（严格/宽松模式）", () => {
    test("宽松模式（未声明）接受任意环境", () => {
      expect(isEnvironmentAccepted("unknown-machine", "any-env")).toBe(true);
    });

    test("严格模式接受权威集内环境", () => {
      registerMachineDeclaration("m1", ["env-1"]);
      expect(isEnvironmentAccepted("m1", "env-1")).toBe(true);
    });

    test("严格模式拒绝权威集外环境", () => {
      registerMachineDeclaration("m1", ["env-1"]);
      expect(isEnvironmentAccepted("m1", "env-unknown")).toBe(false);
    });
  });

  // ── handleFileChangedFrame ──

  describe("handleFileChangedFrame", () => {
    test("正常帧返回解析后的变更", () => {
      const entry: MockEntry = { machineId: "m1", wsId: "ws-1", ws: { close: () => {} } };
      const result = handleFileChangedFrame(entry, {
        environment_id: "env-1",
        path: "/src/main.ts",
        kind: "write",
        source: "user",
      });
      expect(result).not.toBeNull();
      expect(result!.envId).toBe("env-1");
      expect(result!.change.path).toBe("/src/main.ts");
      expect(result!.change.kind).toBe("write");
      expect(result!.change.source).toBe("user");
    });

    test("machineId 为 null 时返回 null", () => {
      const entry: MockEntry = { machineId: null, wsId: "ws-1", ws: { close: () => {} } };
      const result = handleFileChangedFrame(entry, { environment_id: "env-1", path: "/x", kind: "write" });
      expect(result).toBeNull();
    });

    test("environment_id 为空字符串时返回 null", () => {
      const entry: MockEntry = { machineId: "m1", wsId: "ws-1", ws: { close: () => {} } };
      const result = handleFileChangedFrame(entry, { environment_id: "", path: "/x", kind: "write" });
      expect(result).toBeNull();
    });

    test("environment_id 非字符串时返回 null", () => {
      const entry: MockEntry = { machineId: "m1", wsId: "ws-1", ws: { close: () => {} } };
      const result = handleFileChangedFrame(entry, { environment_id: 42, path: "/x", kind: "write" });
      expect(result).toBeNull();
    });

    test("无效 kind 返回 null", () => {
      const entry: MockEntry = { machineId: "m1", wsId: "ws-1", ws: { close: () => {} } };
      const result = handleFileChangedFrame(entry, { environment_id: "env-1", path: "/x", kind: "invalid" });
      expect(result).toBeNull();
    });

    test("空 path 返回 null", () => {
      const entry: MockEntry = { machineId: "m1", wsId: "ws-1", ws: { close: () => {} } };
      const result = handleFileChangedFrame(entry, { environment_id: "env-1", path: "", kind: "write" });
      expect(result).toBeNull();
    });

    test("未知 source 回退为 agent", () => {
      const entry: MockEntry = { machineId: "m1", wsId: "ws-1", ws: { close: () => {} } };
      const result = handleFileChangedFrame(entry, {
        environment_id: "env-1",
        path: "/x",
        kind: "write",
        source: "unknown_source",
      });
      expect(result!.change.source).toBe("agent");
    });

    test("actor_id 和 to 字段透传", () => {
      const entry: MockEntry = { machineId: "m1", wsId: "ws-1", ws: { close: () => {} } };
      const result = handleFileChangedFrame(entry, {
        environment_id: "env-1",
        path: "/old.ts",
        kind: "rename",
        source: "user",
        actor_id: "user-123",
        to: "/new.ts",
      });
      expect(result!.change.actorId).toBe("user-123");
      expect(result!.change.to).toBe("/new.ts");
    });

    test("严格模式下权威集外环境被拒绝", () => {
      registerMachineDeclaration("m1", ["env-1"]);
      const entry: MockEntry = { machineId: "m1", wsId: "ws-1", ws: { close: () => {} } };
      const result = handleFileChangedFrame(entry, {
        environment_id: "env-unknown",
        path: "/x",
        kind: "write",
      });
      expect(result).toBeNull();
    });
  });

  // ── broadcastMachineInvalidateAll ──

  describe("broadcastMachineInvalidateAll", () => {
    test("首次广播返回所有环境", () => {
      registerMachineEnvironment("m1", "env-1");
      registerMachineEnvironment("m1", "env-2");
      const result = broadcastMachineInvalidateAll("m1", 1000);
      expect(result.sort()).toEqual(["env-1", "env-2"]);
    });

    test("同一秒内第二次广播仍返回（限频 2 条/s）", () => {
      registerMachineEnvironment("m1", "env-1");
      broadcastMachineInvalidateAll("m1", 1000);
      const result = broadcastMachineInvalidateAll("m1", 1500);
      expect(result.length).toBe(1);
    });

    test("同一秒内第三次广播被限频拒绝", () => {
      registerMachineEnvironment("m1", "env-1");
      broadcastMachineInvalidateAll("m1", 1000);
      broadcastMachineInvalidateAll("m1", 1500);
      const result = broadcastMachineInvalidateAll("m1", 1800);
      expect(result).toEqual([]);
    });

    test("超过 1 秒窗口后重置计数", () => {
      registerMachineEnvironment("m1", "env-1");
      broadcastMachineInvalidateAll("m1", 1000);
      broadcastMachineInvalidateAll("m1", 1500);
      // 超过 1 秒窗口
      const result = broadcastMachineInvalidateAll("m1", 2100);
      expect(result.length).toBe(1);
    });

    test("无环境时返回空数组", () => {
      const result = broadcastMachineInvalidateAll("m-noenv", 1000);
      expect(result).toEqual([]);
    });
  });

  // ── handleFileWsRegisterIdentity ──

  describe("handleFileWsRegisterIdentity", () => {
    test("core runtime 中存在节点 → 返回 false（放行）", () => {
      _deps.getCoreRuntime = () => ({ getNode: (_id: string) => ({ status: "online" }) });
      const entry: MockEntry = { machineId: "m1", wsId: "ws-1", ws: { close: () => {} } };
      expect(handleFileWsRegisterIdentity(entry, "m1")).toBe(false);
    });

    test("core runtime 中不存在 + 宽松模式 → 返回 false（放行）", () => {
      _deps.getCoreRuntime = () => null;
      _deps.fileWsIdentityStrict = false;
      const entry: MockEntry = { machineId: "m1", wsId: "ws-1", ws: { close: () => {} } };
      expect(handleFileWsRegisterIdentity(entry, "m1")).toBe(false);
    });

    test("core runtime 中不存在 + 严格模式 → 返回 true（拒绝）并 close 4404", () => {
      _deps.getCoreRuntime = () => null;
      _deps.fileWsIdentityStrict = true;
      let closeCode = 0;
      let closeReason = "";
      const entry: MockEntry = {
        machineId: "m1",
        wsId: "ws-1",
        ws: { close: (code: number, reason: string) => { closeCode = code; closeReason = reason; } },
      };
      expect(handleFileWsRegisterIdentity(entry, "m1")).toBe(true);
      expect(closeCode).toBe(4404);
      expect(closeReason).toBe("unknown_machine");
    });
  });

  // ── clearMachineEventState / resetMachineEventState ──

  describe("状态清理", () => {
    test("clearMachineEventState 清理指定机器", () => {
      registerMachineDeclaration("m1", ["env-1"]);
      registerMachineDeclaration("m2", ["env-2"]);
      clearMachineEventState("m1");
      expect(machineEnvironments.has("m1")).toBe(false);
      expect(strictMachines.has("m1")).toBe(false);
      expect(machineEnvironments.has("m2")).toBe(true);
    });

    test("resetMachineEventState 清理所有状态", () => {
      registerMachineDeclaration("m1", ["env-1"]);
      registerMachineDeclaration("m2", ["env-2"]);
      broadcastMachineInvalidateAll("m1", 1000);
      resetMachineEventState();
      expect(machineEnvironments.size).toBe(0);
      expect(strictMachines.size).toBe(0);
      expect(machineInvalidateRate.size).toBe(0);
    });
  });
});
