// count-recovery.test.ts — 数量模式关联恢复与在途栅栏测试
// 测试目标：CountRecoveryService 的 uniqueProviderId / begin-hasInFlight-drain / reconcileDue / retry 退避
// 业务意图：只有唯一且元数据匹配的原生沙盒能认领绑定；在途创建期间不得重复发现；失败必须保留预留并退避
// 源：packages/opensandbox-cluster/src/services/count-recovery-service.ts（main a7f477a9e）
// 说明：SQL 过滤与 HTTP 客户端以依赖注入替代（上游为 SQLite 集成测试）

import { describe, expect, test } from "bun:test";

// ── 复制实现 ──

const COUNT_ATTEMPT_METADATA_KEY = "opensandbox.cluster.attempt_id";

interface BindingRow {
  sandboxId: string;
  serverId: string;
  attemptId: string | null;
  retryCount: number;
  state: string;
  providerSandboxId: string | null;
  lastError: string | null;
  nextRetryAt: number | null;
}

function uniqueProviderId(result: unknown, attemptId: string): string | undefined {
  if (
    !result ||
    typeof result !== "object" ||
    !("items" in result) ||
    !Array.isArray(result.items) ||
    result.items.length !== 1 ||
    !("pagination" in result)
  )
    return;
  const pagination = result.pagination;
  if (
    !pagination ||
    typeof pagination !== "object" ||
    !("totalItems" in pagination) ||
    pagination.totalItems !== 1 ||
    !("hasNextPage" in pagination) ||
    pagination.hasNextPage !== false
  )
    return;
  const item: unknown = result.items[0];
  if (
    !item ||
    typeof item !== "object" ||
    !("id" in item) ||
    typeof item.id !== "string" ||
    !item.id ||
    !("metadata" in item) ||
    !item.metadata ||
    typeof item.metadata !== "object" ||
    !(COUNT_ATTEMPT_METADATA_KEY in item.metadata) ||
    (item.metadata as Record<string, unknown>)[COUNT_ATTEMPT_METADATA_KEY] !== attemptId
  )
    return;
  return item.id;
}

interface RecoveryDeps {
  selectDue(): BindingRow[];
  servers: { getCredentials(serverId: string): { apiKey: string } | undefined };
  allocations: { rememberProviderId(row: BindingRow, providerId: string): void };
  request(path: string, row: BindingRow): Promise<Response>;
  dbUpdate(patch: Record<string, unknown>, row: BindingRow): void;
  now(): number;
  onError(event: string, detail: Record<string, unknown>): void;
}

class CountRecoveryService {
  private readonly inFlight = new Map<string, Set<Promise<void>>>();

  constructor(private readonly deps: RecoveryDeps) {}

  begin(row: BindingRow): () => void {
    const attemptId = row.attemptId!;
    let complete!: () => void;
    const pending = new Promise<void>((resolve) => {
      complete = resolve;
    });
    const operations = this.inFlight.get(attemptId) ?? new Set<Promise<void>>();
    operations.add(pending);
    this.inFlight.set(attemptId, operations);
    return () => {
      operations.delete(pending);
      if (operations.size === 0 && this.inFlight.get(attemptId) === operations) this.inFlight.delete(attemptId);
      complete();
    };
  }

  hasInFlight(attemptId: string | null): boolean {
    return attemptId !== null && this.inFlight.has(attemptId);
  }

  async drain(): Promise<void> {
    await Promise.allSettled([...this.inFlight.values()].flatMap((operations) => [...operations]));
  }

  async reconcileDue(): Promise<void> {
    const rows = this.deps.selectDue();
    let cursor = 0;
    await Promise.all(
      Array.from({ length: 4 }, async () => {
        while (cursor < rows.length) {
          const row = rows[cursor++];
          if (row && !this.inFlight.has(row.attemptId!)) await this.reconcile(row);
        }
      }),
    );
  }

  private async reconcile(row: BindingRow): Promise<void> {
    try {
      const server = this.deps.servers.getCredentials(row.serverId);
      if (!server) throw new Error("count recovery server unavailable");
      const query = new URLSearchParams({
        metadata: new URLSearchParams({ [COUNT_ATTEMPT_METADATA_KEY]: row.attemptId! }).toString(),
        page: "1",
        pageSize: "200",
      });
      const path = `/v1/sandboxes?${query}`;
      const response = await this.deps.request(path, row);
      if (!response.ok) throw new Error(`native count lookup HTTP ${response.status}`);
      const result: unknown = await response.json();
      const providerId = uniqueProviderId(result, row.attemptId!);
      if (!providerId) {
        this.retry(row, "native count association unresolved");
        return;
      }
      if (!this.inFlight.has(row.attemptId!)) this.deps.allocations.rememberProviderId(row, providerId);
    } catch (error) {
      const errorKind = error instanceof Error ? error.name : "UnknownError";
      this.deps.onError("count association recovery failed", {
        sandboxId: row.sandboxId,
        serverId: row.serverId,
        attemptId: row.attemptId,
        errorKind,
      });
      try {
        this.retry(row, `native count association recovery failed (${errorKind})`);
      } catch (retryError) {
        this.deps.onError("count recovery retry scheduling failed", {
          sandboxId: row.sandboxId,
          attemptId: row.attemptId,
          errorKind: retryError instanceof Error ? retryError.name : "UnknownError",
        });
      }
    }
  }

  private retry(row: BindingRow, lastError: string): void {
    const retryCount = row.retryCount + 1;
    const now = this.deps.now();
    this.deps.dbUpdate(
      {
        retryCount,
        lastError,
        updatedAt: now,
        nextRetryAt: now + Math.min(300000, 5000 * 2 ** Math.min(retryCount - 1, 6)),
      },
      row,
    );
  }
}

// ── 辅助 ──

function row(overrides: Partial<BindingRow> = {}): BindingRow {
  return {
    sandboxId: "job",
    serverId: "node",
    attemptId: "attempt-1",
    retryCount: 0,
    state: "uncertain",
    providerSandboxId: null,
    lastError: null,
    nextRetryAt: null,
    ...overrides,
  };
}

function payload(attemptId: string, id = "native") {
  return {
    items: [{ id, metadata: { [COUNT_ATTEMPT_METADATA_KEY]: attemptId } }],
    pagination: { totalItems: 1, hasNextPage: false },
  };
}

function discovered(attemptId: string, id = "native") {
  return Response.json(payload(attemptId, id));
}

interface Harness {
  service: CountRecoveryService;
  requests: string[];
  updates: Array<Record<string, unknown>>;
  remembered: Array<[string, string]>;
  errors: Array<[string, Record<string, unknown>]>;
}

function harness(
  options: {
    rows?: BindingRow[];
    request?: (path: string, row: BindingRow) => Promise<Response>;
    credentials?: { apiKey: string } | undefined;
    dbUpdate?: (patch: Record<string, unknown>, row: BindingRow) => void;
    now?: number;
  } = {},
): Harness {
  const requests: string[] = [];
  const updates: Array<Record<string, unknown>> = [];
  const remembered: Array<[string, string]> = [];
  const errors: Array<[string, Record<string, unknown>]> = [];
  const service = new CountRecoveryService({
    selectDue: () => options.rows ?? [row()],
    servers: { getCredentials: () => ("credentials" in options ? options.credentials : { apiKey: "k" }) },
    allocations: { rememberProviderId: (r, id) => remembered.push([r.sandboxId, id]) },
    request: (path, r) => {
      requests.push(path);
      return options.request ? options.request(path, r) : Promise.resolve(discovered(r.attemptId!));
    },
    dbUpdate:
      options.dbUpdate ??
      ((patch) => {
        updates.push(patch);
      }),
    now: () => options.now ?? 1_000_000,
    onError: (event, detail) => errors.push([event, detail]),
  });
  return { service, requests, updates, remembered, errors };
}

// ── tests ──

describe("uniqueProviderId 唯一匹配判定", () => {
  test("唯一且元数据匹配时返回原生 ID", () => {
    expect(uniqueProviderId(payload("a-1", "native-1"), "a-1")).toBe("native-1");
  });

  test("空列表或多项都不认领", () => {
    expect(uniqueProviderId({ items: [], pagination: { totalItems: 0, hasNextPage: false } }, "a-1")).toBeUndefined();
    expect(
      uniqueProviderId(
        { items: [{ id: "one" }, { id: "two" }], pagination: { totalItems: 2, hasNextPage: false } },
        "a-1",
      ),
    ).toBeUndefined();
  });

  test("分页不完整或不一致时不认领", () => {
    const item = { id: "one", metadata: { [COUNT_ATTEMPT_METADATA_KEY]: "a-1" } };
    expect(uniqueProviderId({ items: [item] }, "a-1")).toBeUndefined();
    expect(uniqueProviderId({ items: [item], pagination: { totalItems: 2, hasNextPage: false } }, "a-1")).toBeUndefined();
    expect(uniqueProviderId({ items: [item], pagination: { totalItems: 1, hasNextPage: true } }, "a-1")).toBeUndefined();
    expect(uniqueProviderId({ items: [item], pagination: { totalItems: 1 } }, "a-1")).toBeUndefined();
  });

  test("ID 缺失、非字符串或为空时不认领", () => {
    for (const id of [undefined, 42, ""]) {
      expect(
        uniqueProviderId(
          {
            items: [{ id, metadata: { [COUNT_ATTEMPT_METADATA_KEY]: "a-1" } }],
            pagination: { totalItems: 1, hasNextPage: false },
          },
          "a-1",
        ),
      ).toBeUndefined();
    }
  });

  test("元数据缺失或尝试标识不一致时不认领", () => {
    const pagination = { totalItems: 1, hasNextPage: false };
    expect(uniqueProviderId({ items: [{ id: "native" }], pagination }, "a-1")).toBeUndefined();
    expect(
      uniqueProviderId({ items: [{ id: "native", metadata: null }], pagination }, "a-1"),
    ).toBeUndefined();
    expect(
      uniqueProviderId({ items: [{ id: "native", metadata: {} }], pagination }, "a-1"),
    ).toBeUndefined();
    expect(
      uniqueProviderId(
        { items: [{ id: "native", metadata: { [COUNT_ATTEMPT_METADATA_KEY]: "other" } }], pagination },
        "a-1",
      ),
    ).toBeUndefined();
  });

  test("非对象输入不抛错", () => {
    for (const result of [null, undefined, "text", 42, []]) {
      expect(uniqueProviderId(result, "a-1")).toBeUndefined();
    }
  });
});

describe("在途栅栏 begin / hasInFlight / drain", () => {
  test("begin 后在途，释放后清除", () => {
    const { service } = harness();
    const release = service.begin(row());
    expect(service.hasInFlight("attempt-1")).toBe(true);
    expect(service.hasInFlight(null)).toBe(false);
    release();
    expect(service.hasInFlight("attempt-1")).toBe(false);
  });

  test("同一尝试的多个操作需全部释放", () => {
    const { service } = harness();
    const first = service.begin(row());
    const second = service.begin(row());
    first();
    expect(service.hasInFlight("attempt-1")).toBe(true);
    second();
    expect(service.hasInFlight("attempt-1")).toBe(false);
  });

  test("重复释放幂等", () => {
    const { service } = harness();
    const release = service.begin(row());
    release();
    expect(() => release()).not.toThrow();
    expect(service.hasInFlight("attempt-1")).toBe(false);
  });

  test("drain 等待全部在途操作结束", async () => {
    const { service } = harness();
    let settled = false;
    const release = service.begin(row());
    const draining = service.drain().then(() => {
      settled = true;
    });
    await Promise.resolve();
    expect(settled).toBe(false);
    release();
    await draining;
    expect(settled).toBe(true);
  });

  test("无在途操作时 drain 立即完成", async () => {
    const { service } = harness();
    await expect(service.drain()).resolves.toBeUndefined();
  });
});

describe("reconcileDue 协调流程", () => {
  test("查询参数携带元数据、页码与页大小", async () => {
    const { service, requests } = harness({ rows: [row({ attemptId: "a/b c" })] });
    await service.reconcileDue();
    expect(requests).toHaveLength(1);
    const url = new URL(requests[0]!, "http://cluster");
    expect(url.pathname).toBe("/v1/sandboxes");
    expect(url.searchParams.get("page")).toBe("1");
    expect(url.searchParams.get("pageSize")).toBe("200");
    expect(new URLSearchParams(url.searchParams.get("metadata")!).get(COUNT_ATTEMPT_METADATA_KEY)).toBe("a/b c");
  });

  test("唯一匹配恢复关联且不写退避", async () => {
    const { service, remembered, updates } = harness();
    await service.reconcileDue();
    expect(remembered).toEqual([["job", "native"]]);
    expect(updates).toEqual([]);
  });

  test("无匹配时保留预留并写入退避", async () => {
    const { service, remembered, updates } = harness({
      request: async () => Response.json({ items: [], pagination: { totalItems: 0, hasNextPage: false } }),
    });
    await service.reconcileDue();
    expect(remembered).toEqual([]);
    expect(updates).toHaveLength(1);
    expect(updates[0]).toEqual({
      retryCount: 1,
      lastError: "native count association unresolved",
      updatedAt: 1_000_000,
      nextRetryAt: 1_005_000,
    });
  });

  test("试图在途期间不发起查询", async () => {
    const { service, requests } = harness();
    const release = service.begin(row());
    await service.reconcileDue();
    expect(requests).toEqual([]);
    release();
    await service.reconcileDue();
    expect(requests).toHaveLength(1);
  });

  test("请求期间新出现的在途保护阻止迟到关联", async () => {
    let release!: () => void;
    let started!: () => void;
    const startedPromise = new Promise<void>((resolve) => {
      started = resolve;
    });
    let harnessRef!: Harness;
    harnessRef = harness({
      request: async (path, r) => {
        release = harnessRef.service.begin(r);
        started();
        return discovered(r.attemptId!);
      },
    });
    const pending = harnessRef.service.reconcileDue();
    await startedPromise;
    await pending;
    expect(harnessRef.remembered).toEqual([]);
    release();
  });

  test("节点凭据缺失时记录错误并退避", async () => {
    const { service, updates, errors, remembered } = harness({ credentials: undefined });
    await service.reconcileDue();
    expect(remembered).toEqual([]);
    expect(updates[0]).toMatchObject({
      lastError: "native count association recovery failed (Error)",
    });
    expect(errors[0]![0]).toBe("count association recovery failed");
    expect(errors[0]![1]).toMatchObject({ sandboxId: "job", serverId: "node", attemptId: "attempt-1", errorKind: "Error" });
  });

  test("HTTP 失败按状态码记录退避", async () => {
    const { service, updates, errors } = harness({
      request: async () => new Response(null, { status: 503 }),
    });
    await service.reconcileDue();
    expect(updates).toHaveLength(1);
    expect(errors).toHaveLength(1);
  });

  test("响应体非 JSON 时退避且不认领", async () => {
    const { service, remembered, updates } = harness({
      request: async () => new Response("not json", { status: 200 }),
    });
    await service.reconcileDue();
    expect(remembered).toEqual([]);
    expect(updates).toHaveLength(1);
  });

  test("写退避本身失败不向外冒泡", async () => {
    const { service, errors, remembered } = harness({
      request: async () => {
        throw new TypeError("network down");
      },
      dbUpdate: () => {
        throw new Error("db gone");
      },
    });
    await expect(service.reconcileDue()).resolves.toBeUndefined();
    expect(remembered).toEqual([]);
    expect(errors.map(([event]) => event)).toEqual([
      "count association recovery failed",
      "count recovery retry scheduling failed",
    ]);
    expect(errors[0]![1]).toMatchObject({ errorKind: "TypeError" });
    expect(errors[1]![1]).toMatchObject({ errorKind: "Error" });
  });

  test("单行失败不影响其它行", async () => {
    const { service, remembered } = harness({
      rows: [
        row({ sandboxId: "bad", attemptId: "a-bad", serverId: "missing" }),
        row({ sandboxId: "ok", attemptId: "a-ok" }),
      ],
      request: async (_path, r) => {
        if (r.attemptId === "a-bad") throw new Error("boom");
        return discovered(r.attemptId!);
      },
    });
    await service.reconcileDue();
    expect(remembered).toEqual([["ok", "native"]]);
  });

  test("并发上限为 4", async () => {
    let active = 0;
    let maxActive = 0;
    const rows = Array.from({ length: 12 }, (_, i) => row({ sandboxId: `job-${i}`, attemptId: `a-${i}` }));
    const { service, remembered } = harness({
      rows,
      request: async (_path, r) => {
        active++;
        maxActive = Math.max(maxActive, active);
        await new Promise((resolve) => setTimeout(resolve, 5));
        active--;
        return discovered(r.attemptId!);
      },
    });
    await service.reconcileDue();
    expect(remembered).toHaveLength(12);
    expect(maxActive).toBeLessThanOrEqual(4);
    expect(maxActive).toBeGreaterThan(1);
  });

  test("全部行都已处理且只处理一次", async () => {
    const rows = Array.from({ length: 9 }, (_, i) => row({ sandboxId: `job-${i}`, attemptId: `a-${i}` }));
    const { service, requests } = harness({ rows });
    await service.reconcileDue();
    expect(requests).toHaveLength(9);
    expect(new Set(requests).size).toBe(9);
  });
});

describe("retry 退避", () => {
  test("退避按重试次数指数增长并封顶 300000ms", async () => {
    for (const previous of [1, 2, 3, 4, 5, 6, 7, 8, 20]) {
      const updates: Array<Record<string, unknown>> = [];
      const { service } = harness({
        rows: [row({ retryCount: previous })],
        request: async () => {
          throw new Error("x");
        },
        dbUpdate: (patch) => {
          updates.push(patch);
        },
      });
      await service.reconcileDue();
      expect(updates[0]).toMatchObject({
        retryCount: previous + 1,
        updatedAt: 1_000_000,
        nextRetryAt: 1_000_000 + Math.min(300000, 5000 * 2 ** Math.min(previous, 6)),
      });
    }
  });
});
