import { describe, expect, it } from "bun:test";

// instance.ts 纯函数测试
// 覆盖：toInstanceInfo（SpawnedInstance 路径，不调 getCoreRuntime）、toInstanceActivityInfo
// 编排域路径（instanceId 且 无 id）会调用 getCoreRuntime，无法纯测试

// ── 类型定义 ──

interface InstanceInfo {
  id: string;
  port: number;
  status: "starting" | "running" | "stopped" | "error";
  error: string | null;
  group_id: string;
  environment_id: string | null;
  session_id: string | null;
  instance_number: number;
  created_at: number;
}

interface InstanceInfoSource {
  id?: string;
  instanceId?: string;
  environmentId?: string;
  status?: InstanceInfo["status"] | (() => InstanceInfo["status"]);
  port?: number;
  error?: string | null;
  sessionId?: string;
  instanceNumber?: number;
  createdAt?: Date;
}

interface SpawnedInstance {
  id: string;
  userId: string;
  port: number;
  pid: number | null;
  status: "starting" | "running" | "stopped" | "error";
  command: string;
  error: string | null;
  apiKey: string;
  createdAt: Date;
  environmentId?: string;
  sessionId?: string;
  instanceNumber: number;
}

interface InstanceSupplement {
  userId: string;
  environmentId: string;
  organizationId: string;
  instanceNumber: number;
  spawnSource: "interactive" | "workflow" | "api" | null;
  lastActivityAt: number;
  relayCount: number;
  lastRelayDetachedAt: number | null;
}

interface InstanceActivityInfo extends InstanceInfo {
  user: { id: string; name: string | null; email: string | null } | null;
  spawn_source: InstanceSupplement["spawnSource"] | null;
  last_activity_at: number;
  relay_count: number;
  last_relay_detached_at: number | null;
  idle_seconds: number;
  idle_timeout_seconds: number;
  idle_kill_eligible: boolean;
  inactivity_seconds: number;
  activity_timeout_seconds: number;
  activity_kill_eligible: boolean;
}

// ── 纯函数复制 ──

function toInstanceInfo(instance: SpawnedInstance | InstanceInfoSource): InstanceInfo {
  const instanceId = "instanceId" in instance ? instance.instanceId : undefined;
  const id = instanceId ?? instance.id ?? "";
  const environmentId = instance.environmentId ?? null;
  const status = typeof instance.status === "function" ? instance.status() : (instance.status ?? "starting");

  const port = instance.port ?? 0;
  const error = instance.error ?? null;
  const sessionId = instance.sessionId ?? null;
  const instanceNumber = instance.instanceNumber ?? 0;
  const createdAt = instance.createdAt;

  return {
    id,
    port,
    status,
    error,
    group_id: environmentId ?? "",
    environment_id: environmentId,
    session_id: sessionId,
    instance_number: instanceNumber,
    created_at: createdAt ? Math.floor(createdAt.getTime() / 1000) : 0,
  };
}

function toInstanceActivityInfo(
  instance: SpawnedInstance,
  supplement: InstanceSupplement,
  idleTimeoutSeconds: number,
  activityTimeoutSeconds: number,
  now = Date.now(),
): InstanceActivityInfo {
  const idleSince = supplement.lastRelayDetachedAt ?? now;
  const idleSeconds = supplement.relayCount === 0 ? Math.max(0, Math.floor((now - idleSince) / 1000)) : 0;
  const inactivitySeconds = Math.max(0, Math.floor((now - supplement.lastActivityAt) / 1000));
  return {
    ...toInstanceInfo(instance),
    user: {
      id: supplement.userId,
      name: null,
      email: null,
    },
    spawn_source: supplement.spawnSource,
    last_activity_at: Math.floor(supplement.lastActivityAt / 1000),
    relay_count: supplement.relayCount,
    last_relay_detached_at:
      supplement.lastRelayDetachedAt === null ? null : Math.floor(supplement.lastRelayDetachedAt / 1000),
    idle_seconds: idleSeconds,
    idle_timeout_seconds: idleTimeoutSeconds,
    idle_kill_eligible: supplement.relayCount === 0 && idleSeconds >= idleTimeoutSeconds,
    inactivity_seconds: inactivitySeconds,
    activity_timeout_seconds: activityTimeoutSeconds,
    activity_kill_eligible: inactivitySeconds >= activityTimeoutSeconds,
  };
}

// ── 工厂 ──

function makeInstance(overrides: Partial<SpawnedInstance> = {}): SpawnedInstance {
  return {
    id: "inst-001",
    userId: "user-1",
    port: 3000,
    pid: 12345,
    status: "running",
    command: "node server.js",
    error: null,
    apiKey: "key-abc",
    createdAt: new Date("2026-06-15T10:00:00.000Z"),
    environmentId: "env-001",
    sessionId: "sess-001",
    instanceNumber: 1,
    ...overrides,
  };
}

function makeSupplement(overrides: Partial<InstanceSupplement> = {}): InstanceSupplement {
  return {
    userId: "user-1",
    environmentId: "env-001",
    organizationId: "org-1",
    instanceNumber: 1,
    spawnSource: "interactive",
    lastActivityAt: Date.now() - 5000,
    relayCount: 0,
    lastRelayDetachedAt: Date.now() - 10000,
    ...overrides,
  };
}

// ── toInstanceInfo ──

describe("toInstanceInfo — SpawnedInstance 路径", () => {
  it("基本字段正确映射", () => {
    const inst = makeInstance();
    const info = toInstanceInfo(inst);
    expect(info.id).toBe("inst-001");
    expect(info.port).toBe(3000);
    expect(info.status).toBe("running");
    expect(info.error).toBeNull();
    expect(info.environment_id).toBe("env-001");
    expect(info.session_id).toBe("sess-001");
    expect(info.instance_number).toBe(1);
  });

  it("group_id 使用 environmentId 作为兼容值", () => {
    const info = toInstanceInfo(makeInstance({ environmentId: "env-xyz" }));
    expect(info.group_id).toBe("env-xyz");
  });

  it("environmentId 为 undefined 时 group_id 为空字符串", () => {
    const inst = makeInstance();
    inst.environmentId = undefined;
    const info = toInstanceInfo(inst);
    expect(info.group_id).toBe("");
    expect(info.environment_id).toBeNull();
  });

  it("createdAt 转为 Unix 时间戳（秒）", () => {
    const date = new Date("2026-06-15T10:00:00.000Z");
    const info = toInstanceInfo(makeInstance({ createdAt: date }));
    expect(info.created_at).toBe(Math.floor(date.getTime() / 1000));
  });

  it("createdAt 为 undefined 时 created_at 为 0", () => {
    const inst = makeInstance();
    (inst as Record<string, unknown>).createdAt = undefined;
    const info = toInstanceInfo(inst as SpawnedInstance);
    expect(info.created_at).toBe(0);
  });

  it("sessionId 为 undefined 时 session_id 为 null", () => {
    const inst = makeInstance();
    inst.sessionId = undefined;
    const info = toInstanceInfo(inst);
    expect(info.session_id).toBeNull();
  });

  it("status 为各种枚举值时正确透传", () => {
    for (const s of ["starting", "running", "stopped", "error"] as const) {
      expect(toInstanceInfo(makeInstance({ status: s })).status).toBe(s);
    }
  });

  it("error 有值时正确透传", () => {
    const info = toInstanceInfo(makeInstance({ error: "OOM killed" }));
    expect(info.error).toBe("OOM killed");
  });
});

describe("toInstanceInfo — InstanceInfoSource 路径（无 getCoreRuntime 调用）", () => {
  it("status 为函数时调用取值", () => {
    const source: InstanceInfoSource = {
      id: "inst-fn",
      status: () => "running",
      port: 4000,
    };
    const info = toInstanceInfo(source);
    expect(info.status).toBe("running");
  });

  it("status 为 undefined 时默认 starting", () => {
    const source: InstanceInfoSource = { id: "inst-default" };
    const info = toInstanceInfo(source);
    expect(info.status).toBe("starting");
  });

  it("所有可选字段缺失时使用默认值", () => {
    const source: InstanceInfoSource = { id: "minimal" };
    const info = toInstanceInfo(source);
    expect(info.id).toBe("minimal");
    expect(info.port).toBe(0);
    expect(info.error).toBeNull();
    expect(info.session_id).toBeNull();
    expect(info.instance_number).toBe(0);
    expect(info.created_at).toBe(0);
    expect(info.group_id).toBe("");
    expect(info.environment_id).toBeNull();
  });
});

// ── toInstanceActivityInfo ──

describe("toInstanceActivityInfo", () => {
  it("基础信息字段正确", () => {
    const inst = makeInstance();
    const sup = makeSupplement();
    const now = Date.now();
    const info = toInstanceActivityInfo(inst, sup, 300, 600, now);
    expect(info.id).toBe("inst-001");
    expect(info.user?.id).toBe("user-1");
    expect(info.user?.name).toBeNull();
    expect(info.user?.email).toBeNull();
    expect(info.spawn_source).toBe("interactive");
  });

  it("idle_timeout_seconds 和 activity_timeout_seconds 透传参数", () => {
    const info = toInstanceActivityInfo(makeInstance(), makeSupplement(), 300, 600);
    expect(info.idle_timeout_seconds).toBe(300);
    expect(info.activity_timeout_seconds).toBe(600);
  });

  it("relayCount > 0 时 idle_seconds 为 0", () => {
    const now = 1718448000000;
    const sup = makeSupplement({ relayCount: 2, lastRelayDetachedAt: now - 60000 });
    const info = toInstanceActivityInfo(makeInstance(), sup, 300, 600, now);
    expect(info.idle_seconds).toBe(0);
    expect(info.idle_kill_eligible).toBe(false);
  });

  it("relayCount === 0 时 idle_seconds 从 lastRelayDetachedAt 计算", () => {
    const now = 1718448000000;
    const sup = makeSupplement({ relayCount: 0, lastRelayDetachedAt: now - 30000 });
    const info = toInstanceActivityInfo(makeInstance(), sup, 300, 600, now);
    expect(info.idle_seconds).toBe(30);
  });

  it("lastRelayDetachedAt 为 null 时使用 now 作为 idleSince", () => {
    const now = 1718448000000;
    const sup = makeSupplement({ relayCount: 0, lastRelayDetachedAt: null });
    const info = toInstanceActivityInfo(makeInstance(), sup, 300, 600, now);
    expect(info.idle_seconds).toBe(0); // (now - now) / 1000 = 0
  });

  it("inactivity_seconds 从 lastActivityAt 计算", () => {
    const now = 1718448000000;
    const sup = makeSupplement({ lastActivityAt: now - 45000 });
    const info = toInstanceActivityInfo(makeInstance(), sup, 300, 600, now);
    expect(info.inactivity_seconds).toBe(45);
  });

  it("idle_kill_eligible 条件：relayCount === 0 且 idle_seconds >= idleTimeout", () => {
    const now = 1718448000000;
    const sup = makeSupplement({ relayCount: 0, lastRelayDetachedAt: now - 300000 });
    const info = toInstanceActivityInfo(makeInstance(), sup, 300, 600, now);
    expect(info.idle_seconds).toBe(300);
    expect(info.idle_kill_eligible).toBe(true);
  });

  it("idle_kill_eligible 为 false 当 idle_seconds < idleTimeout", () => {
    const now = 1718448000000;
    const sup = makeSupplement({ relayCount: 0, lastRelayDetachedAt: now - 100000 });
    const info = toInstanceActivityInfo(makeInstance(), sup, 300, 600, now);
    expect(info.idle_seconds).toBe(100);
    expect(info.idle_kill_eligible).toBe(false);
  });

  it("idle_kill_eligible 为 false 当 relayCount > 0", () => {
    const now = 1718448000000;
    const sup = makeSupplement({ relayCount: 1, lastRelayDetachedAt: now - 300000 });
    const info = toInstanceActivityInfo(makeInstance(), sup, 300, 600, now);
    expect(info.idle_kill_eligible).toBe(false);
  });

  it("activity_kill_eligible 条件：inactivity_seconds >= activityTimeout", () => {
    const now = 1718448000000;
    const sup = makeSupplement({ lastActivityAt: now - 600000 });
    const info = toInstanceActivityInfo(makeInstance(), sup, 300, 600, now);
    expect(info.inactivity_seconds).toBe(600);
    expect(info.activity_kill_eligible).toBe(true);
  });

  it("activity_kill_eligible 为 false 当 inactivity_seconds < activityTimeout", () => {
    const now = 1718448000000;
    const sup = makeSupplement({ lastActivityAt: now - 300000 });
    const info = toInstanceActivityInfo(makeInstance(), sup, 300, 600, now);
    expect(info.inactivity_seconds).toBe(300);
    expect(info.activity_kill_eligible).toBe(false);
  });

  it("last_relay_detached_at 为 null 时透传 null", () => {
    const sup = makeSupplement({ lastRelayDetachedAt: null });
    const info = toInstanceActivityInfo(makeInstance(), sup, 300, 600);
    expect(info.last_relay_detached_at).toBeNull();
  });

  it("last_relay_detached_at 有值时转为 Unix 秒", () => {
    const ts = 1718448000000;
    const sup = makeSupplement({ lastRelayDetachedAt: ts });
    const info = toInstanceActivityInfo(makeInstance(), sup, 300, 600);
    expect(info.last_relay_detached_at).toBe(Math.floor(ts / 1000));
  });

  it("last_activity_at 转为 Unix 秒", () => {
    const ts = 1718448000000;
    const sup = makeSupplement({ lastActivityAt: ts });
    const info = toInstanceActivityInfo(makeInstance(), sup, 300, 600);
    expect(info.last_activity_at).toBe(Math.floor(ts / 1000));
  });

  it("relay_count 透传", () => {
    const sup = makeSupplement({ relayCount: 5 });
    const info = toInstanceActivityInfo(makeInstance(), sup, 300, 600);
    expect(info.relay_count).toBe(5);
  });
});
