// api-v1-knowledge.test.ts — v1 知识库远端状态探测测试
// 测试目标：checkApiKnowledgeStatus 的存在性判定、并发上限、中止传播与安全投影
// 业务意图：远端缺失(false)/不可用(null)必须区分，本地行不得被改写，探测结果不得泄露内部标识
// 源：packages/resources/knowledge/src/server/services/api-v1-knowledge.ts（main a7f477a9e）

import { describe, expect, test } from "bun:test";

// ── 复制实现（provider 与 resolveKey 以参数注入） ──

interface KnowledgeBaseListItem {
  id: string;
  name: string;
  description: string | null;
  provider: string;
  status: string;
  resourcesCount: number;
  bindingsCount: number;
  embeddingModel?: string | null;
  parseMethod?: string | null;
  chunkMethod?: string | null;
  remoteId?: string | null;
  remoteExists?: boolean | null;
  userId: string;
  organizationId?: string | null;
}

interface KnowledgeProvider {
  getDataset?: (input: {
    datasetId: string;
    apiKey: string;
    signal: AbortSignal;
  }) => Promise<unknown>;
}

function project(item: KnowledgeBaseListItem, remoteExists: boolean | null) {
  return {
    id: item.id,
    name: item.name,
    description: item.description,
    provider: item.provider,
    status: item.status,
    resourcesCount: item.resourcesCount,
    bindingsCount: item.bindingsCount,
    embeddingModel: item.embeddingModel ?? null,
    parseMethod: item.parseMethod ?? null,
    chunkMethod: item.chunkMethod ?? null,
    remoteExists,
  };
}

async function checkApiKnowledgeStatus(
  items: KnowledgeBaseListItem[],
  signal: AbortSignal | undefined,
  resolveKey: (scope: string, userId: string, organizationId: string) => Promise<string>,
  provider: KnowledgeProvider,
) {
  const results = new Array<ReturnType<typeof project>>(items.length);
  let cursor = 0;
  await Promise.all(
    Array.from({ length: Math.min(4, items.length) }, async () => {
      while (cursor < items.length) {
        signal?.throwIfAborted();
        const index = cursor++;
        const item = items[index]!;
        let exists: boolean | null = null;
        if (item.remoteId && provider.getDataset) {
          const timer = new AbortController();
          const deadline = setTimeout(() => timer.abort(), 3000);
          const combined = signal ? AbortSignal.any([signal, timer.signal]) : timer.signal;
          let onAbort: () => void = () => {};
          const cancelled = new Promise<never>((_, reject) => {
            onAbort = () => reject(new DOMException("Knowledge check cancelled", "AbortError"));
            combined.addEventListener("abort", onAbort, { once: true });
          });
          try {
            const work = (async () => {
              const apiKey = await resolveKey("global", item.userId, item.organizationId ?? "");
              combined.throwIfAborted();
              return provider.getDataset!({ datasetId: item.remoteId!, apiKey, signal: combined });
            })();
            exists = (await Promise.race([work, cancelled])) !== null;
          } catch (error) {
            signal?.throwIfAborted();
          } finally {
            clearTimeout(deadline);
            combined.removeEventListener("abort", onAbort);
          }
        }
        results[index] = project(item, exists);
      }
    }),
  );
  return results;
}

// ── 辅助 ──

const resolveKey = async () => "fixture-key";

function item(overrides: Partial<KnowledgeBaseListItem> = {}): KnowledgeBaseListItem {
  return {
    id: "kb-1",
    name: "demo",
    description: null,
    provider: "ragflow",
    status: "ready",
    resourcesCount: 1,
    bindingsCount: 2,
    userId: "user-1",
    organizationId: "org-1",
    ...overrides,
  };
}

// ── tests ──

describe("checkApiKnowledgeStatus 远端状态探测", () => {
  test("存在/缺失/不可用分别投影为 true/false/null", async () => {
    const provider: KnowledgeProvider = {
      getDataset: async ({ datasetId }) => {
        if (datasetId === "offline") throw new Error("offline");
        return datasetId === "missing" ? null : {};
      },
    };
    const rows = ["exists", "missing", "offline"].map((id) => item({ id, remoteId: id, remoteExists: true }));

    const result = await checkApiKnowledgeStatus(rows, undefined, resolveKey, provider);

    expect(result.map((row) => row.remoteExists)).toEqual([true, false, null]);
    expect(rows.map((row) => row.remoteExists)).toEqual([true, true, true]);
  });

  test("投影不含 remoteId/userId 等内部字段", async () => {
    const provider: KnowledgeProvider = { getDataset: async () => ({}) };
    const [row] = await checkApiKnowledgeStatus([item({ remoteId: "r1" })], undefined, resolveKey, provider);
    expect(row).not.toHaveProperty("remoteId");
    expect(row).not.toHaveProperty("userId");
    expect(row).not.toHaveProperty("organizationId");
  });

  test("投影保留展示字段并为可空字段补 null", async () => {
    const provider: KnowledgeProvider = { getDataset: async () => ({}) };
    const [row] = await checkApiKnowledgeStatus([item({ remoteId: "r1" })], undefined, resolveKey, provider);
    expect(row).toEqual({
      id: "kb-1",
      name: "demo",
      description: null,
      provider: "ragflow",
      status: "ready",
      resourcesCount: 1,
      bindingsCount: 2,
      embeddingModel: null,
      parseMethod: null,
      chunkMethod: null,
      remoteExists: true,
    });
  });

  test("无 remoteId 时不发起远端请求，remoteExists 为 null", async () => {
    let calls = 0;
    const provider: KnowledgeProvider = {
      getDataset: async () => {
        calls++;
        return {};
      },
    };
    const [row] = await checkApiKnowledgeStatus([item({ remoteId: null })], undefined, resolveKey, provider);
    expect(calls).toBe(0);
    expect(row!.remoteExists).toBeNull();
  });

  test("provider 未实现 getDataset 时 remoteExists 为 null", async () => {
    const [row] = await checkApiKnowledgeStatus([item({ remoteId: "r1" })], undefined, resolveKey, {});
    expect(row!.remoteExists).toBeNull();
  });

  test("resolveKey 以 global 作用域和行的用户/组织调用", async () => {
    const calls: Array<[string, string, string]> = [];
    const provider: KnowledgeProvider = { getDataset: async () => ({}) };
    await checkApiKnowledgeStatus([item({ remoteId: "r1", userId: "u9", organizationId: null })], undefined, async (...args) => {
      calls.push(args);
      return "k";
    }, provider);
    expect(calls).toEqual([["global", "u9", ""]]);
  });

  test("并发上限为 4", async () => {
    let active = 0;
    let maxActive = 0;
    const provider: KnowledgeProvider = {
      getDataset: async () => {
        active++;
        maxActive = Math.max(maxActive, active);
        await new Promise((resolve) => setTimeout(resolve, 10));
        active--;
        return {};
      },
    };
    const rows = Array.from({ length: 12 }, (_, i) => item({ id: `kb-${i}`, remoteId: `r-${i}` }));

    const result = await checkApiKnowledgeStatus(rows, undefined, resolveKey, provider);

    expect(result).toHaveLength(12);
    expect(maxActive).toBeLessThanOrEqual(4);
    expect(maxActive).toBeGreaterThan(1);
  });

  test("结果顺序与输入顺序一致", async () => {
    const provider: KnowledgeProvider = {
      getDataset: async ({ datasetId }) => {
        await new Promise((resolve) => setTimeout(resolve, datasetId === "slow" ? 20 : 1));
        return {};
      },
    };
    const rows = [item({ id: "slow", remoteId: "slow" }), item({ id: "fast", remoteId: "fast" })];
    const result = await checkApiKnowledgeStatus(rows, undefined, resolveKey, provider);
    expect(result.map((row) => row.id)).toEqual(["slow", "fast"]);
  });

  test("空列表返回空数组", async () => {
    expect(await checkApiKnowledgeStatus([], undefined, resolveKey, {})).toEqual([]);
  });

  test("已中止的信号立即拒绝", async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(
      checkApiKnowledgeStatus([item({ remoteId: "r1" })], controller.signal, resolveKey, {}),
    ).rejects.toMatchObject({ name: "AbortError" });
  });

  test("飞行中中止会拒绝且不吞掉中止", async () => {
    const controller = new AbortController();
    let started!: () => void;
    const startedPromise = new Promise<void>((resolve) => {
      started = resolve;
    });
    const provider: KnowledgeProvider = {
      getDataset: ({ signal }) => {
        started();
        return new Promise((_, reject) => {
          signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
        });
      },
    };
    const pending = checkApiKnowledgeStatus([item({ remoteId: "r1" })], controller.signal, resolveKey, provider);
    await startedPromise;
    controller.abort();
    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });

  test("远端普通失败不影响其它行", async () => {
    const provider: KnowledgeProvider = {
      getDataset: async ({ datasetId }) => {
        if (datasetId === "bad") throw new Error("boom");
        return {};
      },
    };
    const rows = [item({ id: "bad", remoteId: "bad" }), item({ id: "ok", remoteId: "ok" })];
    const result = await checkApiKnowledgeStatus(rows, undefined, resolveKey, provider);
    expect(result.map((row) => row.remoteExists)).toEqual([null, true]);
  });
});
