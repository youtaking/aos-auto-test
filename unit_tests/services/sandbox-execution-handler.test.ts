import { afterEach, describe, expect, test } from "bun:test";
import { resetAllStubs } from "@fenix/platform-sdk/testing";
import {
  SandboxRuntimeNotReadyError,
  SandboxStateError,
} from "@src/resource-sandbox/server/services/sandbox-errors";
import { SandboxExecutionHandler } from "@src/resource-sandbox/server/services/sandbox-execution-handler";

afterEach(() => {
  resetAllStubs();
});

// Sandbox 启动等待 Machine online 后，寻址节点必须返回 machine_id。
test("waits for the machine to become online and returns its id", async () => {
  const manager = {
    getPool: async () => ({ id: "pool_default", providerKey: "test-provider", image: "sandbox:test" }),
    createOrReuse: async () => ({ id: "sbi_test", machineId: "mach_sandbox_sbi_test", status: "starting" }),
    markError: async () => {
      throw new Error("must not be called");
    },
  } as never;
  const handler = new SandboxExecutionHandler(manager, async () => true);

  const preparing = handler.prepare({
    sandboxId: "sbi_test",
    sandboxPoolId: "pool_default",
    providerKey: "ignored",
    userId: "user_test",
    template: { type: "image", value: "ignored" },
    runtimeConnectTimeoutMs: 1000,
  } as never);
  await expect(preparing).resolves.toEqual({
    nodeId: "mach_sandbox_sbi_test",
    source: "sandbox",
    sandboxId: "sbi_test",
  });
});

// Machine 已经 online 时，准备流程必须立即复用当前连接。
test("accepts a machine that is already online", async () => {
  const manager = {
    getPool: async () => ({ id: "pool_default", providerKey: "test-provider", image: "sandbox:test" }),
    createOrReuse: async () => ({ id: "sbi_early", machineId: "mach_sandbox_sbi_early", status: "starting" }),
    markError: async () => {
      throw new Error("must not be called");
    },
  } as never;
  const handler = new SandboxExecutionHandler(manager, async () => true);

  await expect(
    handler.prepare({
      sandboxId: "sbi_early",
      sandboxPoolId: "pool_default",
      providerKey: "ignored",
      userId: "user_test",
      template: { type: "image", value: "ignored" },
      runtimeConnectTimeoutMs: 1000,
    } as never),
  ).resolves.toEqual({
    nodeId: "mach_sandbox_sbi_early",
    source: "sandbox",
    sandboxId: "sbi_early",
  });
});

// ACP 首次等待超时后，优先复用原 Provider 资源重试，而不是立即销毁重建。
test("retries the existing provider resource after the first ACP timeout", async () => {
  const repairCalls: Array<{ recreate?: boolean }> = [];
  let online = false;
  const instance = {
    id: "sbi_recover",
    machineId: "mach_sandbox_sbi_recover",
    externalSandboxId: "provider-sandbox",
    status: "starting",
  };
  const manager = {
    getPool: async () => ({ id: "pool_default", providerKey: "test-provider", image: "sandbox:test" }),
    createOrReuse: async () => instance,
    // 复用现有 Provider 资源（不带 recreate），恢复后机器回连。
    repairRuntime: async (_id: string, options: { recreate?: boolean } = {}) => {
      repairCalls.push(options);
      online = true;
      return { instance, replaced: false };
    },
    markRuntimeNotReady: async () => {
      throw new Error("must not be called");
    },
  } as never;
  const handler = new SandboxExecutionHandler(manager, async () => online);

  await expect(
    handler.prepare({
      sandboxId: "sbi_recover",
      sandboxPoolId: "pool_default",
      providerKey: "ignored",
      userId: "user_test",
      template: { type: "image", value: "ignored" },
      runtimeConnectTimeoutMs: 15,
    } as never),
  ).resolves.toMatchObject({ nodeId: "mach_sandbox_sbi_recover" });

  expect(repairCalls).toHaveLength(1);
  expect(repairCalls[0].recreate).toBeUndefined();
});

// 原 Provider 资源无法恢复且再次等待仍失败时，才销毁旧资源并重建。
test("recreates the sandbox when retrying the existing provider resource fails", async () => {
  const repairCalls: Array<{ recreate?: boolean }> = [];
  let online = false;
  const instance = {
    id: "sbi_rebuild",
    machineId: "mach_sandbox_sbi_rebuild",
    externalSandboxId: "provider-sandbox",
    status: "starting",
  };
  const rebuilt = { ...instance, externalSandboxId: "rebuilt-provider-sandbox" };
  const manager = {
    getPool: async () => ({ id: "pool_default", providerKey: "test-provider", image: "sandbox:test" }),
    createOrReuse: async () => instance,
    repairRuntime: async (_id: string, options: { recreate?: boolean } = {}) => {
      repairCalls.push(options);
      // 首次复用后机器仍不可用；只有带 recreate 的重建才恢复连接。
      if (options.recreate) {
        online = true;
        return { instance: rebuilt, replaced: true };
      }
      return { instance, replaced: false };
    },
    markRuntimeNotReady: async () => {
      throw new Error("must not be called");
    },
  } as never;
  const handler = new SandboxExecutionHandler(manager, async () => online);

  await expect(
    handler.prepare({
      sandboxId: "sbi_rebuild",
      sandboxPoolId: "pool_default",
      providerKey: "ignored",
      userId: "user_test",
      template: { type: "image", value: "ignored" },
      runtimeConnectTimeoutMs: 10,
    } as never),
  ).resolves.toMatchObject({ nodeId: "mach_sandbox_sbi_rebuild" });

  expect(repairCalls).toHaveLength(2);
  expect(repairCalls[0].recreate).toBeUndefined();
  expect(repairCalls[1].recreate).toBe(true);
});

// 协调阶段已经替换过资源（replace）时，第二次等待超时不能再次重建，必须直接回写不可用。
test("fails fast when reconciliation already replaced the provider resource", async () => {
  const marked: unknown[] = [];
  const instance = {
    id: "sbi_replace",
    machineId: "mach_sandbox_sbi_replace",
    externalSandboxId: "replaced-provider-sandbox",
    status: "starting",
  };
  const manager = {
    getPool: async () => ({ id: "pool_default", providerKey: "test-provider", image: "sandbox:test" }),
    createOrReuse: async (_input: unknown, onRecovery?: (action: "resume" | "replace") => void) => {
      onRecovery?.("replace");
      return instance;
    },
    repairRuntime: async () => {
      throw new Error("must not be called");
    },
    markRuntimeNotReady: async (expected: unknown) => {
      marked.push(expected);
    },
  } as never;
  const handler = new SandboxExecutionHandler(manager, async () => false);

  await expect(
    handler.prepare({
      sandboxId: "sbi_replace",
      sandboxPoolId: "pool_default",
      providerKey: "ignored",
      userId: "user_test",
      template: { type: "image", value: "ignored" },
      runtimeConnectTimeoutMs: 10,
    } as never),
  ).rejects.toThrow(SandboxRuntimeNotReadyError);

  expect(marked).toEqual([instance]);
});

// 协调阶段已 resume 但机器仍不可用时，跳过“复用原资源”的修复，直接走重建。
test("recreates directly when reconciliation already resumed the provider resource", async () => {
  const repairCalls: Array<{ recreate?: boolean }> = [];
  let online = false;
  const instance = {
    id: "sbi_resume",
    machineId: "mach_sandbox_sbi_resume",
    externalSandboxId: "provider-sandbox",
    status: "recovering",
  };
  const manager = {
    getPool: async () => ({ id: "pool_default", providerKey: "test-provider", image: "sandbox:test" }),
    createOrReuse: async (_input: unknown, onRecovery?: (action: "resume" | "replace") => void) => {
      onRecovery?.("resume");
      return instance;
    },
    repairRuntime: async (_id: string, options: { recreate?: boolean } = {}) => {
      repairCalls.push(options);
      if (options.recreate) online = true;
      return { instance, replaced: false };
    },
    markRuntimeNotReady: async () => {
      throw new Error("must not be called");
    },
  } as never;
  const handler = new SandboxExecutionHandler(manager, async () => online);

  await expect(
    handler.prepare({
      sandboxId: "sbi_resume",
      sandboxPoolId: "pool_default",
      providerKey: "ignored",
      userId: "user_test",
      template: { type: "image", value: "ignored" },
      runtimeConnectTimeoutMs: 10,
    } as never),
  ).resolves.toMatchObject({ nodeId: "mach_sandbox_sbi_resume" });

  expect(repairCalls).toHaveLength(1);
  expect(repairCalls[0].recreate).toBe(true);
});

// 重建后机器仍未回连时，必须把“不可用”写回重建后的资源并抛出，调用方不能继续等待。
test("marks the rebuilt resource not ready when the machine still does not connect", async () => {
  const repairCalls: Array<{ recreate?: boolean }> = [];
  const marked: unknown[] = [];
  const instance = {
    id: "sbi_still_down",
    machineId: "mach_sandbox_sbi_still_down",
    externalSandboxId: "provider-sandbox",
    status: "starting",
  };
  const rebuilt = { ...instance, externalSandboxId: "rebuilt-provider-sandbox" };
  const manager = {
    getPool: async () => ({ id: "pool_default", providerKey: "test-provider", image: "sandbox:test" }),
    createOrReuse: async () => instance,
    repairRuntime: async (_id: string, options: { recreate?: boolean } = {}) => {
      repairCalls.push(options);
      return options.recreate ? { instance: rebuilt, replaced: false } : { instance, replaced: false };
    },
    markRuntimeNotReady: async (expected: unknown) => {
      marked.push(expected);
    },
  } as never;
  const handler = new SandboxExecutionHandler(manager, async () => false);

  await expect(
    handler.prepare({
      sandboxId: "sbi_still_down",
      sandboxPoolId: "pool_default",
      providerKey: "ignored",
      userId: "user_test",
      template: { type: "image", value: "ignored" },
      runtimeConnectTimeoutMs: 10,
    } as never),
  ).rejects.toThrow(SandboxRuntimeNotReadyError);

  expect(repairCalls).toHaveLength(2);
  expect(repairCalls[1].recreate).toBe(true);
  expect(marked).toEqual([rebuilt]);
});

// 同一沙盒的并发进入必须合并到同一轮恢复，避免对同一个资源重复探测与修复。
test("shares a single recovery round across concurrent prepares", async () => {
  let readyChecks = 0;
  const instance = {
    id: "sbi_shared",
    machineId: "mach_sandbox_sbi_shared",
    externalSandboxId: "provider-sandbox",
    status: "starting",
  };
  const manager = {
    getPool: async () => ({ id: "pool_default", providerKey: "test-provider", image: "sandbox:test" }),
    createOrReuse: async () => instance,
    repairRuntime: async () => {
      throw new Error("must not be called");
    },
    markRuntimeNotReady: async () => {
      throw new Error("must not be called");
    },
  } as never;
  const handler = new SandboxExecutionHandler(manager, async () => {
    readyChecks += 1;
    await new Promise((resolve) => setTimeout(resolve, 50));
    return true;
  });

  const input = {
    sandboxId: "sbi_shared",
    sandboxPoolId: "pool_default",
    providerKey: "ignored",
    userId: "user_test",
    template: { type: "image", value: "ignored" },
    runtimeConnectTimeoutMs: 1000,
  } as never;
  const [first, second] = await Promise.all([handler.prepare(input), handler.prepare(input)]);

  expect(first).toEqual(second);
  expect(first.nodeId).toBe("mach_sandbox_sbi_shared");
  expect(readyChecks).toBe(1);
});

describe("recoverDisconnectedMachine", () => {
  // 机器没有归属当前用户的实例时，不触发任何恢复动作。
  test("does nothing when no instance belongs to the machine", async () => {
    let readyChecks = 0;
    const lookedUp: Array<[string, string]> = [];
    const manager = {
      getByMachineForUser: async (machineId: string, userId: string) => {
        lookedUp.push([machineId, userId]);
        return null;
      },
    } as never;
    const handler = new SandboxExecutionHandler(manager, async () => {
      readyChecks += 1;
      return true;
    });

    await handler.recoverDisconnectedMachine({
      machineId: "mach_unknown",
      ownerUserId: "user_test",
      isCurrent: () => true,
      runtimeConnectTimeoutMs: 10,
    });

    expect(lookedUp).toEqual([["mach_unknown", "user_test"]]);
    expect(readyChecks).toBe(0);
  });

  // 请求已被新的意图取代时，恢复流程必须保持静默，不触碰 Provider。
  test("does nothing when the request intent is already superseded", async () => {
    let readyChecks = 0;
    let repaired = false;
    const manager = {
      getByMachineForUser: async () => ({ id: "sbi_superseded", machineId: "mach_sb", externalSandboxId: null }),
      repairRuntime: async () => {
        repaired = true;
        throw new Error("must not be called");
      },
    } as never;
    const handler = new SandboxExecutionHandler(manager, async () => {
      readyChecks += 1;
      return true;
    });

    await handler.recoverDisconnectedMachine({
      machineId: "mach_sb",
      ownerUserId: "user_test",
      isCurrent: () => false,
      runtimeConnectTimeoutMs: 10,
    });

    expect(readyChecks).toBe(0);
    expect(repaired).toBe(false);
  });

  // 恢复已经开始后请求被取消，恢复轮次必须以 SandboxStateError 结束，不能继续修复资源。
  test("aborts the recovery round when the intent changes mid-flight", async () => {
    let intentChecks = 0;
    let repaired = false;
    const manager = {
      getByMachineForUser: async () => ({
        id: "sbi_midflight",
        machineId: "mach_sb",
        externalSandboxId: "provider-sandbox",
        status: "recovering",
      }),
      repairRuntime: async () => {
        repaired = true;
        throw new Error("must not be called");
      },
    } as never;
    const handler = new SandboxExecutionHandler(manager, async () => false);

    await expect(
      handler.recoverDisconnectedMachine({
        machineId: "mach_sb",
        ownerUserId: "user_test",
        // 入口校验通过，进入恢复轮次后意图已被替换。
        isCurrent: () => {
          intentChecks += 1;
          return intentChecks === 1;
        },
        runtimeConnectTimeoutMs: 10,
      }),
    ).rejects.toThrow(SandboxStateError);

    expect(repaired).toBe(false);
  });

  // AbortSignal 已取消时必须在任何查询之前退出。
  test("throws before querying when the signal is already aborted", async () => {
    let queried = false;
    const manager = {
      getByMachineForUser: async () => {
        queried = true;
        return null;
      },
    } as never;
    const handler = new SandboxExecutionHandler(manager, async () => true);
    const controller = new AbortController();
    controller.abort();

    await expect(
      handler.recoverDisconnectedMachine({
        machineId: "mach_sb",
        ownerUserId: "user_test",
        isCurrent: () => true,
        signal: controller.signal,
      }),
    ).rejects.toThrow();

    expect(queried).toBe(false);
  });

  // 机器已回连时直接结束，不创建也不重建资源。
  test("returns immediately when the machine is already back online", async () => {
    let readyChecks = 0;
    const manager = {
      getByMachineForUser: async () => ({
        id: "sbi_online",
        machineId: "mach_sb",
        externalSandboxId: "provider-sandbox",
        status: "recovering",
      }),
      repairRuntime: async () => {
        throw new Error("must not be called");
      },
    } as never;
    const handler = new SandboxExecutionHandler(manager, async () => {
      readyChecks += 1;
      return true;
    });

    await handler.recoverDisconnectedMachine({
      machineId: "mach_sb",
      ownerUserId: "user_test",
      isCurrent: () => true,
      runtimeConnectTimeoutMs: 10,
    });

    expect(readyChecks).toBe(1);
  });

  // 机器离线时在原 Provider 资源上修复并等待回连，不销毁重建。
  test("repairs the existing resource and waits for the machine to reconnect", async () => {
    const repairCalls: Array<{ expectedExternalSandboxId?: string | null }> = [];
    let online = false;
    const instance = {
      id: "sbi_disconnected",
      machineId: "mach_sb",
      externalSandboxId: "provider-sandbox",
      status: "recovering",
    };
    const manager = {
      getByMachineForUser: async () => instance,
      repairRuntime: async (_id: string, options: { expectedExternalSandboxId?: string | null } = {}) => {
        repairCalls.push(options);
        online = true;
        return { instance, replaced: false };
      },
      markRuntimeNotReady: async () => {
        throw new Error("must not be called");
      },
    } as never;
    const handler = new SandboxExecutionHandler(manager, async () => online);

    await handler.recoverDisconnectedMachine({
      machineId: "mach_sb",
      ownerUserId: "user_test",
      isCurrent: () => true,
      runtimeConnectTimeoutMs: 10,
    });

    expect(repairCalls).toHaveLength(1);
    expect(repairCalls[0].expectedExternalSandboxId).toBe("provider-sandbox");
  });
});
