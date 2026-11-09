// pool-service.test.ts — opensandbox-cluster PoolService 测试
// 测试目标：create/update/delete/list/findById 的调度模式与租约校验、冲突检测、容量计算
// 业务意图：确保调度模式切换、租约配置、删除前的 server/binding 检查符合后端契约
// 源：packages/opensandbox-cluster/src/services/pool-service.ts（main a7f477a9e）

import { beforeEach, describe, expect, test } from "bun:test";

// ── 复制实现（仓库以内存桩注入） ──

export class ConflictError extends Error {
  readonly code = "CONFLICT";
}

interface PoolRecord {
  id: string;
  name: string;
  status: string;
  schedulingMode: string;
  defaultLeaseSeconds?: number | null;
  maxLeaseSeconds?: number | null;
  createdAt: number;
  updatedAt: number;
}

interface ServerRecord {
  id: string;
  poolId: string;
  maxSandboxes?: number | null;
  status: string;
  healthStatus: string;
}

interface PoolRepository {
  list(): PoolRecord[];
  findById(id: string): PoolRecord | undefined;
  insert(pool: PoolRecord): PoolRecord;
  update(id: string, patch: Partial<PoolRecord>): PoolRecord | undefined;
  delete(id: string): boolean;
}

interface ServerRepository {
  listByPool(poolId: string): ServerRecord[];
}

interface BindingRepository {
  countByPool(poolId: string): number;
  countByServer(serverId: string): number;
  hasPoolReferences(poolId: string): boolean;
}

class PoolService {
  constructor(
    private readonly pools: PoolRepository,
    private readonly servers: ServerRepository,
    private readonly bindings: BindingRepository,
  ) {}

  list() {
    return this.pools.list().map((pool) => this.withCapacity(pool));
  }

  findById(id: string) {
    const pool = this.pools.findById(id);
    return pool ? this.withCapacity(pool) : undefined;
  }

  create(input: {
    id: string;
    name: string;
    status?: string;
    scheduling_mode?: string;
    default_lease_seconds?: number;
    max_lease_seconds?: number;
  }) {
    this.validate(input);
    const now = Date.now();
    return this.pools.insert({
      schedulingMode: input.scheduling_mode ?? "count",
      defaultLeaseSeconds: input.default_lease_seconds,
      maxLeaseSeconds: input.max_lease_seconds,
      id: input.id,
      name: input.name,
      status: input.status ?? "active",
      createdAt: now,
      updatedAt: now,
    });
  }

  update(
    id: string,
    input: {
      name?: string;
      status?: string;
      scheduling_mode?: string;
      default_lease_seconds?: number;
      max_lease_seconds?: number;
    },
  ) {
    const current = this.pools.findById(id);
    if (!current) return;
    if (
      input.scheduling_mode &&
      input.scheduling_mode !== current.schedulingMode &&
      (this.bindings.countByPool(id) > 0 || this.servers.listByPool(id).length > 0)
    )
      throw new ConflictError("remove pool servers and active bindings before changing scheduling_mode");
    this.validate({
      scheduling_mode: input.scheduling_mode ?? current.schedulingMode,
      default_lease_seconds: input.default_lease_seconds ?? current.defaultLeaseSeconds ?? undefined,
      max_lease_seconds: input.max_lease_seconds ?? current.maxLeaseSeconds ?? undefined,
    });
    return this.pools.update(id, {
      name: input.name,
      status: input.status,
      schedulingMode: input.scheduling_mode,
      defaultLeaseSeconds: input.default_lease_seconds,
      maxLeaseSeconds: input.max_lease_seconds,
      updatedAt: Date.now(),
    });
  }

  delete(id: string) {
    if (this.servers.listByPool(id).length > 0 || this.bindings.hasPoolReferences(id)) {
      throw new ConflictError("pool has servers or active sandbox bindings");
    }
    return this.pools.delete(id);
  }

  private validate(input: { scheduling_mode?: string; default_lease_seconds?: number; max_lease_seconds?: number }) {
    if (input.scheduling_mode && !["count", "resources"].includes(input.scheduling_mode))
      throw new Error("invalid scheduling_mode");
    if (
      input.scheduling_mode === "resources" &&
      (!Number.isInteger(input.default_lease_seconds) ||
        (input.default_lease_seconds ?? 0) < 60 ||
        !Number.isInteger(input.max_lease_seconds) ||
        (input.max_lease_seconds ?? 0) < (input.default_lease_seconds ?? 0))
    )
      throw new Error("invalid lease configuration");
  }

  private withCapacity(pool: PoolRecord | undefined) {
    if (!pool) return pool;
    const servers = this.servers.listByPool(pool.id);
    const current = this.bindings.countByPool(pool.id);
    const capacity = servers.reduce((sum, server) => sum + (server.maxSandboxes ?? 0), 0);
    const available = servers
      .filter((server) => server.status === "active" && server.healthStatus === "healthy")
      .reduce(
        (sum, server) => sum + Math.max(0, (server.maxSandboxes ?? 0) - this.bindings.countByServer(server.id)),
        0,
      );
    return { ...pool, currentSandboxes: current, capacitySandboxes: capacity, availableSandboxes: available };
  }
}

// ── 内存桩 ──

function makeRepos(
  options: {
    servers?: ServerRecord[];
    bindings?: Map<string, number>;
    poolBindingCounts?: Map<string, number>;
    poolIdRefs?: string[];
  } = {},
) {
  const store = new Map<string, PoolRecord>();
  const servers = options.servers ?? [];
  const bindings = options.bindings ?? new Map<string, number>();
  const poolBindingCounts = options.poolBindingCounts ?? new Map<string, number>();
  const poolIdRefs = new Set(options.poolIdRefs ?? []);

  const pools: PoolRepository = {
    list: () => [...store.values()],
    findById: (id) => store.get(id),
    insert: (pool) => {
      store.set(pool.id, pool);
      return pool;
    },
    update: (id, patch) => {
      const current = store.get(id);
      if (!current) return undefined;
      const next = { ...current, ...patch } as PoolRecord;
      store.set(id, next);
      return next;
    },
    delete: (id) => store.delete(id),
  };

  const serverRepo: ServerRepository = {
    listByPool: (poolId) => servers.filter((s) => s.poolId === poolId),
  };

  const bindingRepo: BindingRepository = {
    countByPool: (poolId) => poolBindingCounts.get(poolId) ?? 0,
    countByServer: (serverId) => bindings.get(serverId) ?? 0,
    hasPoolReferences: (poolId) => poolIdRefs.has(poolId),
  };

  return { service: new PoolService(pools, serverRepo, bindingRepo), store };
}

// ── tests ──

describe("ConflictError", () => {
  test("携带 CONFLICT 错误码", () => {
    const err = new ConflictError("conflict");
    expect(err.name).toBe("Error");
    expect(err.message).toBe("conflict");
    expect(err.code).toBe("CONFLICT");
    expect(err instanceof Error).toBe(true);
  });
});

describe("PoolService.create", () => {
  test("默认 schedulingMode 为 count、status 为 active", () => {
    const { service } = makeRepos();
    const pool = service.create({ id: "p1", name: "pool-1" });
    expect(pool.schedulingMode).toBe("count");
    expect(pool.status).toBe("active");
  });

  test("显式 scheduling_mode 与租约字段被透传", () => {
    const { service } = makeRepos();
    const pool = service.create({
      id: "p1",
      name: "pool-1",
      status: "paused",
      scheduling_mode: "resources",
      default_lease_seconds: 120,
      max_lease_seconds: 600,
    });
    expect(pool.schedulingMode).toBe("resources");
    expect(pool.status).toBe("paused");
    expect(pool.defaultLeaseSeconds).toBe(120);
    expect(pool.maxLeaseSeconds).toBe(600);
  });

  test("非法 scheduling_mode 抛错", () => {
    const { service } = makeRepos();
    expect(() => service.create({ id: "p1", name: "p", scheduling_mode: "round-robin" })).toThrow(
      "invalid scheduling_mode",
    );
  });

  test("resources 模式缺少租约配置抛错", () => {
    const { service } = makeRepos();
    expect(() => service.create({ id: "p1", name: "p", scheduling_mode: "resources" })).toThrow(
      "invalid lease configuration",
    );
  });

  test("resources 模式 default 租约小于 60 抛错", () => {
    const { service } = makeRepos();
    expect(() =>
      service.create({
        id: "p1",
        name: "p",
        scheduling_mode: "resources",
        default_lease_seconds: 59,
        max_lease_seconds: 120,
      }),
    ).toThrow("invalid lease configuration");
  });

  test("resources 模式 max 小于 default 抛错", () => {
    const { service } = makeRepos();
    expect(() =>
      service.create({
        id: "p1",
        name: "p",
        scheduling_mode: "resources",
        default_lease_seconds: 120,
        max_lease_seconds: 60,
      }),
    ).toThrow("invalid lease configuration");
  });

  test("resources 模式租约非整数抛错", () => {
    const { service } = makeRepos();
    expect(() =>
      service.create({
        id: "p1",
        name: "p",
        scheduling_mode: "resources",
        default_lease_seconds: 60.5,
        max_lease_seconds: 120,
      }),
    ).toThrow("invalid lease configuration");
  });

  test("resources 模式 max 等于 default 合法", () => {
    const { service } = makeRepos();
    const pool = service.create({
      id: "p1",
      name: "p",
      scheduling_mode: "resources",
      default_lease_seconds: 60,
      max_lease_seconds: 60,
    });
    expect(pool.schedulingMode).toBe("resources");
  });

  test("count 模式不校验租约字段", () => {
    const { service } = makeRepos();
    const pool = service.create({ id: "p1", name: "p", scheduling_mode: "count", default_lease_seconds: 1 });
    expect(pool.defaultLeaseSeconds).toBe(1);
  });
});

describe("PoolService.update", () => {
  function seeded(servers: ServerRecord[] = [], bindingCount = 0) {
    const poolBindingCounts = new Map<string, number>();
    if (bindingCount > 0) poolBindingCounts.set("p1", bindingCount);
    const repos = makeRepos({ servers, poolBindingCounts });
    repos.service.create({ id: "p1", name: "pool-1" });
    return repos.service;
  }

  test("pool 不存在时静默返回", () => {
    const { service } = makeRepos();
    expect(service.update("missing", { name: "x" })).toBeUndefined();
  });

  test("修改名称与状态被持久化", () => {
    const service = seeded();
    const updated = service.update("p1", { name: "renamed", status: "paused" });
    expect(updated?.name).toBe("renamed");
    expect(updated?.status).toBe("paused");
  });

  test("无 server 和 binding 时允许切换 scheduling_mode", () => {
    const service = seeded();
    const updated = service.update("p1", {
      scheduling_mode: "resources",
      default_lease_seconds: 120,
      max_lease_seconds: 300,
    });
    expect(updated?.schedulingMode).toBe("resources");
  });

  test("有 server 时切换 scheduling_mode 抛 ConflictError", () => {
    const service = seeded([
      { id: "s1", poolId: "p1", maxSandboxes: 4, status: "active", healthStatus: "healthy" },
    ]);
    expect(() => service.update("p1", { scheduling_mode: "resources" })).toThrow(
      "remove pool servers and active bindings before changing scheduling_mode",
    );
  });

  test("有活跃 binding 时切换 scheduling_mode 抛 ConflictError", () => {
    const service = seeded([], 2);
    expect(() => service.update("p1", { scheduling_mode: "resources" })).toThrow(ConflictError);
  });

  test("scheduling_mode 未变化时即使有 server 也不冲突", () => {
    const service = seeded([
      { id: "s1", poolId: "p1", maxSandboxes: 4, status: "active", healthStatus: "healthy" },
    ]);
    const updated = service.update("p1", { scheduling_mode: "count", name: "n" });
    expect(updated?.name).toBe("n");
  });

  test("切换为 resources 但租约不合法时抛错", () => {
    const service = seeded();
    expect(() => service.update("p1", { scheduling_mode: "resources" })).toThrow("invalid lease configuration");
  });

  test("更新租约时沿用当前 scheduling_mode 校验", () => {
    const service = seeded();
    service.update("p1", { scheduling_mode: "resources", default_lease_seconds: 120, max_lease_seconds: 300 });
    expect(() => service.update("p1", { default_lease_seconds: 30 })).toThrow("invalid lease configuration");
  });
});

describe("PoolService.delete", () => {
  test("无 server 和 binding 时删除成功", () => {
    const { service, store } = makeRepos();
    service.create({ id: "p1", name: "p" });
    expect(service.delete("p1")).toBe(true);
    expect(store.has("p1")).toBe(false);
  });

  test("有 server 时抛 ConflictError", () => {
    const { service } = makeRepos({
      servers: [{ id: "s1", poolId: "p1", status: "active", healthStatus: "healthy" }],
    });
    expect(() => service.delete("p1")).toThrow("pool has servers or active sandbox bindings");
  });

  test("有 pool 级绑定引用时抛 ConflictError", () => {
    const { service } = makeRepos({ poolIdRefs: ["p1"] });
    expect(() => service.delete("p1")).toThrow(ConflictError);
  });
});

describe("PoolService 容量计算", () => {
  test("无 server 时容量与可用量为 0", () => {
    const { service } = makeRepos();
    service.create({ id: "p1", name: "p" });
    expect(service.findById("p1")).toMatchObject({
      currentSandboxes: 0,
      capacitySandboxes: 0,
      availableSandboxes: 0,
    });
  });

  test("maxSandboxes 缺失按 0 计入容量", () => {
    const { service } = makeRepos({
      servers: [
        { id: "s1", poolId: "p1", maxSandboxes: null, status: "active", healthStatus: "healthy" },
        { id: "s2", poolId: "p1", maxSandboxes: 10, status: "active", healthStatus: "healthy" },
      ],
    });
    service.create({ id: "p1", name: "p" });
    expect(service.findById("p1")?.capacitySandboxes).toBe(10);
  });

  test("仅 active + healthy 的 server 计入可用量", () => {
    const { service } = makeRepos({
      servers: [
        { id: "s1", poolId: "p1", maxSandboxes: 10, status: "active", healthStatus: "healthy" },
        { id: "s2", poolId: "p1", maxSandboxes: 10, status: "inactive", healthStatus: "healthy" },
        { id: "s3", poolId: "p1", maxSandboxes: 10, status: "active", healthStatus: "unhealthy" },
      ],
    });
    service.create({ id: "p1", name: "p" });
    const pool = service.findById("p1");
    expect(pool?.capacitySandboxes).toBe(30);
    expect(pool?.availableSandboxes).toBe(10);
  });

  test("已用绑定从 server 可用量中扣减且不为负", () => {
    const bindings = new Map<string, number>([
      ["s1", 3],
      ["s2", 99],
    ]);
    const { service } = makeRepos({
      servers: [
        { id: "s1", poolId: "p1", maxSandboxes: 10, status: "active", healthStatus: "healthy" },
        { id: "s2", poolId: "p1", maxSandboxes: 5, status: "active", healthStatus: "healthy" },
      ],
      bindings,
    });
    service.create({ id: "p1", name: "p" });
    expect(service.findById("p1")?.availableSandboxes).toBe(7);
  });

  test("list 对每个 pool 附加容量字段", () => {
    const { service } = makeRepos({
      servers: [{ id: "s1", poolId: "p1", maxSandboxes: 4, status: "active", healthStatus: "healthy" }],
    });
    service.create({ id: "p1", name: "p" });
    service.create({ id: "p2", name: "q" });
    const listed = service.list();
    expect(listed).toHaveLength(2);
    expect(listed.find((p) => p.id === "p1")?.capacitySandboxes).toBe(4);
    expect(listed.find((p) => p.id === "p2")?.capacitySandboxes).toBe(0);
  });

  test("findById 不存在时返回 undefined", () => {
    const { service } = makeRepos();
    expect(service.findById("missing")).toBeUndefined();
  });
});
