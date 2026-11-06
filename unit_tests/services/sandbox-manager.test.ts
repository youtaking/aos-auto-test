import { describe, expect, test } from "bun:test";
import type { SandboxInstance, SandboxPool } from "@fenix/resource-sandbox/db";
import { SandboxManager } from "@src/resource-sandbox/server/services/sandbox-manager";

// Machine 身份创建 / 运行时路由释放已改为 SandboxManager 的显式注入点
// （deps.createMachine / deps.releaseRuntime），不再经宿主 test-utils 的替身注册表，
// 因此本文件不再 import stubRegistry / stubCoreBootstrap / resetAllStubs。

const resources = {
  cpu: 0.5,
  memoryMb: 512,
  diskGb: 5,
  gpuCount: 0,
  environment: { LANG: "C.UTF-8" },
  volumes: [],
};

const pool = {
  id: "pool_default",
  providerKey: "test-provider",
  image: "sandbox:test",
  defaultResources: resources,
  extra: {},
} as unknown as SandboxPool;

function makeInstance(overrides: Partial<SandboxInstance> = {}): SandboxInstance {
  return {
    id: "sbi_test",
    machineId: "mach_sandbox_sbi_test",
    providerKey: "test-provider",
    sandboxPoolId: "pool_default",
    userId: "user_test",
    externalSandboxId: null,
    status: "creating",
    resolvedConfig: {},
    resourceOverrides: null,
    providerPayload: null,
    lastHeartbeatAt: null,
    createdAt: new Date(),
    updatedAt: new Date(),
    ...overrides,
  };
}

describe("SandboxManager machine identity", () => {
  // 新建 Instance 必须先绑定稳定的 machine_id，并把它注入 Provider 配置环境变量。
  test("creates a machine identity and passes RCS_MACHINE_ID to the provider", async () => {
    let machineInput: Record<string, unknown> | undefined;
    let providerInput: Record<string, unknown> | undefined;
    const instance = makeInstance({ resolvedConfig: undefined as never });

    const manager = new SandboxManager({
      pools: { findById: async () => pool },
      createMachine: (async (input: Record<string, unknown>) => {
        machineInput = input;
      }) as never,
      instances: {
        findActive: async () => null,
        create: async (input) => {
          Object.assign(instance, input);
          return instance;
        },
        findByIdForUser: async () => instance,
        update: async (_id: string, status: string, patch?: Record<string, unknown>) =>
          Object.assign(instance, { status, ...patch }),
      },
      providers: {
        get: () => ({
          create: async (input: Record<string, unknown>) => {
            providerInput = input as unknown as Record<string, unknown>;
            return { sandboxId: "provider-sandbox", status: "creating" };
          },
          get: async () => null,
          resume: async () => ({ sandboxId: "provider-sandbox", status: "ready" }),
          destroy: async () => {},
        }),
      } as never,
    });

    await manager.createOrReuse({
      sandboxId: "sbi_test",
      poolId: "pool_default",
      providerKey: "test-provider",
      userId: "user_test",
      template: { type: "image", value: "ignored" },
    });

    expect(machineInput).toMatchObject({ id: "mach_sandbox_sbi_test", userId: "user_test" });
    expect(instance.machineId).toBe("mach_sandbox_sbi_test");
    expect((providerInput?.resources as { environment: Record<string, string> }).environment.RCS_MACHINE_ID).toBe(
      "mach_sandbox_sbi_test",
    );
  });

  // 创建 Sandbox Machine 时应使用资源池声明的 Agent 类型，而不是固定写入 opencode。
  test("uses the agent type configured by the sandbox pool", async () => {
    let machineInput: Record<string, unknown> | undefined;
    const periPool = { ...pool, extra: { agent_type: "peri" } } as SandboxPool;
    const instance = makeInstance({ resolvedConfig: undefined as never });

    const manager = new SandboxManager({
      pools: { findById: async () => periPool },
      createMachine: (async (input: Record<string, unknown>) => {
        machineInput = input;
      }) as never,
      instances: {
        findActive: async () => null,
        create: async (input) => {
          Object.assign(instance, input);
          return instance;
        },
        findByIdForUser: async () => instance,
        update: async (_id: string, status: string, patch?: Record<string, unknown>) =>
          Object.assign(instance, { status, ...patch }),
      },
      providers: {
        get: () => ({
          create: async () => ({ sandboxId: "provider-sandbox", status: "creating" as const }),
          get: async () => null,
          resume: async () => ({ sandboxId: "provider-sandbox", status: "ready" as const }),
          destroy: async () => {},
        }),
      } as never,
    });

    await manager.createOrReuse({
      sandboxId: "sbi_test",
      poolId: "pool_default",
      providerKey: "test-provider",
      userId: "user_test",
      template: { type: "image", value: "ignored" },
    });

    expect(machineInput?.agentName).toBe("peri");
  });

  // 创建 Instance 时，Provider 必须收到稳定用户目录下的宿主机逻辑路径。
  test("passes the stable user workspace path when creating a sandbox", async () => {
    let providerInput: Record<string, unknown> | undefined;
    const instance = makeInstance({ resolvedConfig: undefined as never });
    const workspacePool = {
      ...pool,
      defaultResources: { ...resources, volumes: [{ name: "workspace", source: "ws", target: "/workspace" }] },
    } as SandboxPool;
    const manager = new SandboxManager({
      pools: { findById: async () => workspacePool },
      createMachine: (async () => {}) as never,
      instances: {
        findActive: async () => null,
        create: async (input) => {
          Object.assign(instance, input);
          return instance;
        },
        findByIdForUser: async () => instance,
        update: async (_id: string, status: string, patch?: Record<string, unknown>) =>
          Object.assign(instance, { status, ...patch }),
      },
      providers: {
        get: () => ({
          create: async (input: Record<string, unknown>) => {
            providerInput = input;
            return { sandboxId: "provider-sandbox", status: "creating" as const };
          },
          get: async () => null,
          resume: async () => ({ sandboxId: "provider-sandbox", status: "ready" as const }),
          destroy: async () => {},
        }),
      } as never,
    });

    await manager.createOrReuse({
      sandboxId: instance.id,
      poolId: "pool_default",
      providerKey: "test-provider",
      userId: instance.userId,
      template: { type: "image", value: "ignored" },
    });

    expect(
      (providerInput?.resources as { volumes: Array<{ name: string; source?: string; target: string }> }).volumes,
    ).toEqual([{ name: "workspace", source: "user_test/ws", target: "/workspace" }]);
  });

  // 修改 Instance 配置后，新的快照仍使用同一用户目录，不能退回到 Sandbox ID。
  test("keeps the stable user workspace path when updating instance config", async () => {
    const instance = makeInstance({
      resolvedConfig: {
        image: "sandbox:test",
        resources: { ...resources, volumes: [{ name: "workspace", source: "user_test/old", target: "/workspace" }] },
        providerExtra: {},
      },
      externalSandboxId: "provider-sandbox",
    });
    let updatedPatch: Record<string, unknown> | undefined;
    const workspacePool = {
      ...pool,
      defaultResources: { ...resources, volumes: [{ name: "workspace", source: "ws", target: "/workspace" }] },
    } as SandboxPool;
    const manager = new SandboxManager({
      pools: { findById: async () => workspacePool },
      instances: {
        findById: async () => instance,
        findByIdForUser: async () => instance,
        update: async (_id: string, status: string, patch?: Record<string, unknown>) => {
          updatedPatch = patch;
          return Object.assign(instance, { status, ...patch });
        },
      } as never,
      providers: {
        get: () => ({
          create: async () => ({ sandboxId: "provider-sandbox", status: "creating" as const }),
          get: async () => null,
          resume: async () => ({ sandboxId: "provider-sandbox", status: "ready" as const }),
          destroy: async () => {},
        }),
      } as never,
    });

    await manager.updateInstanceConfig(instance.id, {
      volumes: [{ name: "workspace", source: "/new", target: "/workspace" }],
    });

    expect(
      (
        updatedPatch?.resolvedConfig as {
          resources: { volumes: Array<{ name: string; source?: string; target: string }> };
        }
      ).resources.volumes,
    ).toEqual([{ name: "workspace", source: "user_test/new", target: "/workspace" }]);
  });

  // 根据 Pool 最新默认值 rebuild 时，用户目录路径必须保持稳定。
  test("keeps the stable user workspace path when rebuilding an instance", async () => {
    const instance = makeInstance({
      externalSandboxId: "provider-sandbox",
      resolvedConfig: {
        image: "sandbox:old",
        resources: { ...resources, volumes: [{ name: "workspace", source: "user_test/old", target: "/workspace" }] },
        providerExtra: {},
      },
    });
    let updatedPatch: Record<string, unknown> | undefined;
    const workspacePool = {
      ...pool,
      defaultResources: { ...resources, volumes: [{ name: "workspace", source: "ws", target: "/workspace" }] },
      image: "sandbox:new",
    } as SandboxPool;
    const manager = new SandboxManager({
      pools: { findById: async () => workspacePool },
      instances: {
        findByIdForUser: async () => instance,
        list: async () => [instance],
        update: async (_id: string, status: string, patch?: Record<string, unknown>) => {
          updatedPatch = patch;
          return Object.assign(instance, { status, ...patch });
        },
      } as never,
      providers: {
        get: () => ({
          create: async () => ({ sandboxId: "provider-sandbox", status: "creating" as const }),
          get: async () => null,
          resume: async () => ({ sandboxId: "provider-sandbox", status: "ready" as const }),
          destroy: async () => {},
        }),
      } as never,
    });

    await manager.rebuildInstances({ sandboxPoolId: instance.sandboxPoolId, instanceIds: [instance.id] });

    expect(
      (
        updatedPatch?.resolvedConfig as {
          resources: { volumes: Array<{ name: string; source?: string; target: string }> };
        }
      ).resources.volumes,
    ).toEqual([{ name: "workspace", source: "user_test/ws", target: "/workspace" }]);
  });

  // 重试同一 Sandbox 时必须复用已有 machine_id，不能生成第二条 Machine 身份。
  test("reuses the existing machine identity on retry", async () => {
    const existing = makeInstance({ machineId: "mach_original", status: "starting" });
    let createCalled = false;
    const manager = new SandboxManager({
      pools: { findById: async () => pool },
      instances: {
        findActive: async () => existing,
        findByIdForUser: async () => existing,
        update: async (_id: string, status: string, patch?: Record<string, unknown>) =>
          Object.assign(existing, { status, ...patch }),
      } as never,
      providers: {
        get: () => ({
          create: async () => {
            createCalled = true;
            throw new Error("unexpected");
          },
          get: async () => null,
          resume: async () => ({ sandboxId: "x", status: "ready" }),
          destroy: async () => {},
        }),
      } as never,
    });

    const result = await manager.createOrReuse({
      sandboxId: "sbi_new-request",
      poolId: "pool_default",
      providerKey: "test-provider",
      userId: "user_test",
      template: { type: "image", value: "ignored" },
    });

    expect(result.machineId).toBe("mach_original");
    expect(createCalled).toBe(false);
  });

  // 主动删除必须按 machine_id 清理连接路由，并删除对应 Instance 记录。
  test("destroys the provider resource and unregisters by machine id", async () => {
    const instance = makeInstance({ externalSandboxId: "provider-sandbox" });
    let destroyed = false;
    let unregistered: string | undefined;
    let deleted: string | undefined;
    const manager = new SandboxManager({
      releaseRuntime: (machineId: string) => {
        unregistered = machineId;
      },
      instances: {
        findActive: async () => instance,
        findByIdForUser: async () => instance,
        update: async (_id: string, status: string, patch?: Record<string, unknown>) =>
          Object.assign(instance, { status, ...patch }),
        delete: async (id: string) => {
          deleted = id;
          return instance;
        },
      } as never,
      providers: {
        get: () => ({
          create: async () => ({ sandboxId: "x", status: "creating" }),
          get: async () => null,
          resume: async () => ({ sandboxId: "x", status: "ready" }),
          destroy: async () => {
            destroyed = true;
          },
        }),
      } as never,
    });

    await manager.deleteForUser(instance.id, instance.userId);

    expect(destroyed).toBe(true);
    expect(unregistered).toBe(instance.machineId);
    expect(deleted).toBe(instance.id);
  });

  // FenixAgent 重启后保留 Instance 和 machine_id，仅进入 recovering 等待恢复。
  test("marks active instances recovering after restart", async () => {
    const instance = makeInstance({ status: "ready" });
    let nextStatus: string | undefined;
    const manager = new SandboxManager({
      instances: {
        findActive: async () => instance,
        findByIdForUser: async () => instance,
        list: async () => [instance],
        update: async (_id: string, status: string) => {
          nextStatus = status;
          return Object.assign(instance, { status });
        },
      } as never,
      providers: { get: () => ({}) } as never,
    });

    await manager.recoverAfterRestart();

    expect(nextStatus).toBe("recovering");
    expect(instance.machineId).toBe("mach_sandbox_sbi_test");
  });

  // Pool 默认配置变化后，重建使用原 machine_id，删除 Provider 资源并保存新快照。
  test("rebuilds changed instances without replacing machine identity", async () => {
    const instance = makeInstance({
      externalSandboxId: "provider-sandbox",
      resolvedConfig: {
        image: "sandbox:old",
        providerExtra: {},
        resources: { ...resources, environment: { LANG: "C.UTF-8" } },
      },
    });
    let destroyed = false;
    let updated: { status: string; patch?: Record<string, unknown> } | undefined;
    const manager = new SandboxManager({
      pools: { findById: async () => ({ ...pool, image: "sandbox:new" }) as SandboxPool },
      instances: {
        findActive: async () => instance,
        findByIdForUser: async () => instance,
        list: async () => [instance],
        update: async (_id: string, status: string, patch?: Record<string, unknown>) => {
          updated = { status, patch };
          return Object.assign(instance, { status, ...patch });
        },
      } as never,
      providers: {
        get: () => ({
          create: async () => ({ sandboxId: "x", status: "creating" }),
          get: async () => null,
          resume: async () => ({ sandboxId: "x", status: "ready" }),
          destroy: async () => {
            destroyed = true;
          },
        }),
      } as never,
    });

    const result = await manager.rebuildInstances({ sandboxPoolId: "pool_default", instanceIds: [instance.id] });

    expect(result.items[0].changed).toBe(true);
    expect(destroyed).toBe(true);
    expect(updated?.status).toBe("stopped");
    expect(
      (updated?.patch?.resolvedConfig as { resources: { environment: Record<string, string> } }).resources.environment
        .RCS_MACHINE_ID,
    ).toBe(instance.machineId);
  });

  // dry-run 只返回配置实际发生变化的实例。
  test("dry-run only returns changed instances", async () => {
    const unchanged = makeInstance({
      id: "sbi_unchanged",
      machineId: "mach_sandbox_sbi_unchanged",
      resolvedConfig: {
        image: "sandbox:test",
        providerExtra: {},
        resources: {
          volumes: [],
          environment: { LANG: "C.UTF-8", RCS_MACHINE_ID: "mach_sandbox_sbi_unchanged" },
          gpuCount: 0,
          diskGb: 5,
          memoryMb: 512,
          cpu: 0.5,
        },
      },
    });
    const changed = makeInstance({
      id: "sbi_changed",
      resolvedConfig: {
        image: "sandbox:old",
        providerExtra: {},
        resources,
      },
    });
    const manager = new SandboxManager({
      pools: { findById: async () => pool },
      instances: {
        findActive: async () => null,
        findByIdForUser: async () => null,
        list: async () => [unchanged, changed],
        update: async () => null,
      } as never,
      providers: { get: () => ({}) } as never,
    });

    const result = await manager.rebuildInstances({ sandboxPoolId: "pool_default", dryRun: true });

    expect(result.items.map((item) => item.instanceId)).toEqual(["sbi_changed"]);
  });

  // recovering 实例存在已停止的外部资源时，恢复原资源而不是创建第二个沙盒。
  test("resumes the existing provider resource during recovery", async () => {
    const instance = makeInstance({ status: "recovering", externalSandboxId: "provider-sandbox" });
    let resumed = false;
    let updatedExternalId: string | undefined;
    const manager = new SandboxManager({
      pools: { findById: async () => pool },
      instances: {
        findActive: async () => instance,
        findByIdForUser: async () => instance,
        update: async (_id: string, status: string, patch?: Record<string, unknown>) => {
          updatedExternalId = patch?.externalSandboxId as string | undefined;
          return Object.assign(instance, { status, ...patch });
        },
      } as never,
      providers: {
        get: () => ({
          create: async () => {
            throw new Error("must not create a second sandbox");
          },
          get: async () => ({ sandboxId: "provider-sandbox", status: "stopped" as const }),
          resume: async () => {
            resumed = true;
            return { sandboxId: "provider-sandbox", status: "ready" as const };
          },
          destroy: async () => {},
        }),
      } as never,
    });

    await manager.createOrReuse({
      sandboxId: instance.id,
      poolId: instance.sandboxPoolId,
      providerKey: instance.providerKey,
      userId: instance.userId,
      template: { type: "image", value: "ignored" },
    });

    expect(resumed).toBe(true);
    expect(updatedExternalId).toBe("provider-sandbox");
  });

  // ACP 等待超时后的重试必须复用现有 Provider 资源，不能因为等待失败就删除并创建第二个资源。
  test("repairs an existing provider resource without destroying it", async () => {
    const instance = makeInstance({ status: "recovering", externalSandboxId: "provider-sandbox" });
    let resumed = false;
    let destroyed = false;
    let created = false;
    const manager = new SandboxManager({
      isMachineOnline: async () => false,
      releaseRuntime: () => {},
      instances: {
        findActive: async () => instance,
        findById: async () => instance,
        findByIdForUser: async () => instance,
        update: async (_id: string, status: string, patch?: Record<string, unknown>) =>
          Object.assign(instance, { status, ...patch }),
      } as never,
      providers: {
        get: () => ({
          create: async () => {
            created = true;
            return { sandboxId: "new-provider-sandbox", status: "creating" as const };
          },
          get: async () => ({ sandboxId: "provider-sandbox", status: "stopped" as const }),
          resume: async () => {
            resumed = true;
            return { sandboxId: "provider-sandbox", status: "ready" as const };
          },
          destroy: async () => {
            destroyed = true;
          },
        }),
      } as never,
    });

    const result = await manager.repairRuntime(instance.id);

    expect(result.replaced).toBe(false);
    expect(result.instance.externalSandboxId).toBe("provider-sandbox");
    expect(resumed).toBe(true);
    expect(created).toBe(false);
    expect(destroyed).toBe(false);
  });

  // ready 实例对应的 Machine 已离线时，业务请求必须重新检查 Provider，而不是直接复用旧状态。
  test("reconciles a ready instance when its machine is offline", async () => {
    const instance = makeInstance({ status: "ready", externalSandboxId: "provider-sandbox" });
    let providerGetCalled = false;
    const manager = new SandboxManager({
      pools: { findById: async () => pool },
      isMachineOnline: async () => false,
      instances: {
        findActive: async () => instance,
        findByIdForUser: async () => instance,
        update: async (_id: string, status: string, patch?: Record<string, unknown>) =>
          Object.assign(instance, { status, ...patch }),
      } as never,
      providers: {
        get: () => ({
          create: async () => ({ sandboxId: "new-provider-sandbox", status: "creating" as const }),
          get: async () => {
            providerGetCalled = true;
            return { sandboxId: "provider-sandbox", status: "stopped" as const };
          },
          resume: async () => ({ sandboxId: "provider-sandbox", status: "ready" as const }),
          destroy: async () => {},
        }),
      } as never,
    });

    await manager.createOrReuse({
      sandboxId: instance.id,
      poolId: instance.sandboxPoolId,
      providerKey: instance.providerKey,
      userId: instance.userId,
      template: { type: "image", value: "ignored" },
    });

    expect(providerGetCalled).toBe(true);
  });

  // Provider 返回 error 时，业务请求必须重建资源，而不是只等待已失效的 ACP 连接。
  test("recreates the provider resource when the existing resource is errored", async () => {
    const instance = makeInstance({
      status: "ready",
      externalSandboxId: "provider-sandbox",
      resolvedConfig: { image: "sandbox:test", resources, providerExtra: {} },
    });
    let destroyed = false;
    let created = false;
    const manager = new SandboxManager({
      pools: { findById: async () => pool },
      isMachineOnline: async () => false,
      instances: {
        findActive: async () => instance,
        findByIdForUser: async () => instance,
        update: async (_id: string, status: string, patch?: Record<string, unknown>) =>
          Object.assign(instance, { status, ...patch }),
      } as never,
      providers: {
        get: () => ({
          create: async () => {
            created = true;
            return { sandboxId: "new-provider-sandbox", status: "creating" as const };
          },
          get: async () => ({ sandboxId: "provider-sandbox", status: "error" as const }),
          resume: async () => ({ sandboxId: "provider-sandbox", status: "ready" as const }),
          destroy: async () => {
            destroyed = true;
          },
        }),
      } as never,
    });

    await manager.createOrReuse({
      sandboxId: instance.id,
      poolId: instance.sandboxPoolId,
      providerKey: instance.providerKey,
      userId: instance.userId,
      template: { type: "image", value: "ignored" },
    });

    expect(destroyed).toBe(true);
    expect(created).toBe(true);
    expect(instance.externalSandboxId).toBe("new-provider-sandbox");
  });
});

describe("SandboxManager runtime recovery bookkeeping", () => {
  function recordingManager(
    instance: SandboxInstance,
    options: {
      isMachineOnline?: () => Promise<boolean>;
      updates?: Array<{ status: string; patch?: Record<string, unknown> }>;
      destroy?: () => Promise<void>;
      releaseRuntime?: (machineId: string) => void;
      deleteInstance?: () => Promise<SandboxInstance | null>;
      findByIdForUser?: () => Promise<SandboxInstance | null>;
      /** 生产 repository 提供行锁；打开后删除流程会走 deleting → 副作用 → 删除/回写。 */
      useLock?: boolean;
    } = {},
  ) {
    const updates = options.updates ?? [];
    const update = async (_id: string, status: string, patch?: Record<string, unknown>) => {
      updates.push({ status, patch });
      return Object.assign(instance, { status, ...patch });
    };
    const instances: Record<string, unknown> = {
      findActive: async () => instance,
      findById: async () => instance,
      findByMachineId: async () => instance,
      findByIdForUser: options.findByIdForUser ?? (async () => instance),
      update,
      delete: options.deleteInstance ?? (async () => instance),
    };
    if (options.useLock) {
      instances.withLock = async <T>(
        _id: string,
        operation: (scope: {
          findById: (key: string) => Promise<SandboxInstance | null>;
          update: (key: string, status: string, patch?: Record<string, unknown>) => Promise<SandboxInstance | null>;
          delete: (key: string) => Promise<SandboxInstance | null>;
        }) => Promise<T>,
      ) =>
        operation({
          findById: async () => instance,
          update,
          delete: async () => instance,
        });
    }
    return new SandboxManager({
      isMachineOnline: options.isMachineOnline ?? (async () => false),
      releaseRuntime: options.releaseRuntime ?? (() => {}),
      instances: instances as never,
      providers: {
        get: () => ({
          create: async () => ({ sandboxId: "provider-sandbox", status: "creating" as const }),
          get: async () => null,
          resume: async () => ({ sandboxId: "provider-sandbox", status: "ready" as const }),
          destroy: options.destroy ?? (async () => {}),
        }),
      } as never,
    });
  }

  // ACP 等待超时且机器仍离线时，只把匹配的 Instance 标记为 error。
  test("marks the matching instance error when its machine stays offline", async () => {
    const instance = makeInstance({ status: "starting", externalSandboxId: "provider-sandbox" });
    const updates: Array<{ status: string; patch?: Record<string, unknown> }> = [];
    const manager = recordingManager(instance, { updates });

    await manager.markRuntimeNotReady(instance);

    expect(updates).toHaveLength(1);
    expect(updates[0].status).toBe("error");
    expect(updates[0].patch?.providerPayload).toEqual({ reason: "sandbox_acp_connection_timeout" });
  });

  // 机器已经回连时，旧的超时不能把健康 Instance 覆盖为 error。
  test("skips the error write when the machine is back online", async () => {
    const instance = makeInstance({ status: "starting", externalSandboxId: "provider-sandbox" });
    const updates: Array<{ status: string; patch?: Record<string, unknown> }> = [];
    const manager = recordingManager(instance, { updates, isMachineOnline: async () => true });

    await manager.markRuntimeNotReady(instance);

    expect(updates).toHaveLength(0);
  });

  // 资源身份已被替换时，旧一轮的超时不得污染新资源的状态。
  test("skips the error write when the resource identity changed", async () => {
    const current = makeInstance({ status: "starting", externalSandboxId: "new-provider-sandbox" });
    const updates: Array<{ status: string; patch?: Record<string, unknown> }> = [];
    const manager = recordingManager(current, { updates });

    await manager.markRuntimeNotReady(makeInstance({ externalSandboxId: "old-provider-sandbox" }));

    expect(updates).toHaveLength(0);
  });

  // 正在删除的 Instance 不应被恢复失败改写成 error，避免打断删除流程。
  test("skips the error write while the instance is being deleted", async () => {
    const instance = makeInstance({ status: "deleting", externalSandboxId: "provider-sandbox" });
    const updates: Array<{ status: string; patch?: Record<string, unknown> }> = [];
    const manager = recordingManager(instance, { updates });

    await manager.markRuntimeNotReady(instance);

    expect(updates).toHaveLength(0);
  });

  // 断连机器只能恢复该用户自己的实例。
  test("only returns instances owned by the requesting user", async () => {
    const instance = makeInstance({ userId: "user_test" });
    const manager = recordingManager(instance);

    await expect(manager.getByMachineForUser(instance.machineId, "user_test")).resolves.toBe(instance);
    await expect(manager.getByMachineForUser(instance.machineId, "user_other")).resolves.toBeNull();
  });

  // Provider 销毁失败时必须把失败原因回写到 Instance 并继续抛出。
  test("records the delete failure and rethrows", async () => {
    const instance = makeInstance({ externalSandboxId: "provider-sandbox" });
    const updates: Array<{ status: string; patch?: Record<string, unknown> }> = [];
    const manager = recordingManager(instance, {
      updates,
      useLock: true,
      destroy: async () => {
        throw new Error("provider down");
      },
    });

    await expect(manager.deleteForUser(instance.id, instance.userId)).rejects.toThrow("provider down");

    expect(updates[0].status).toBe("deleting");
    const last = updates[updates.length - 1];
    expect(last.status).toBe("error");
    expect(last.patch?.providerPayload).toEqual({
      reason: "sandbox_delete_failed",
      message: "provider down",
    });
  });

  // 资源身份已经变化时，旧一轮的修复只能报告“已替换”，不得销毁或创建任何资源。
  test("reports replacement without side effects when the resource identity changed", async () => {
    const instance = makeInstance({ status: "recovering", externalSandboxId: "new-provider-sandbox" });
    let destroyed = false;
    let created = false;
    const manager = new SandboxManager({
      isMachineOnline: async () => false,
      instances: {
        findById: async () => instance,
        findByIdForUser: async () => instance,
        update: async () => instance,
      } as never,
      providers: {
        get: () => ({
          create: async () => {
            created = true;
            return { sandboxId: "created", status: "creating" as const };
          },
          get: async () => {
            throw new Error("must not query a superseded resource");
          },
          resume: async () => ({ sandboxId: "resumed", status: "ready" as const }),
          destroy: async () => {
            destroyed = true;
          },
        }),
      } as never,
    });

    const result = await manager.repairRuntime(instance.id, {
      expectedExternalSandboxId: "old-provider-sandbox",
    });

    expect(result.replaced).toBe(true);
    expect(result.instance).toBe(instance);
    expect(destroyed).toBe(false);
    expect(created).toBe(false);
  });

  // 请求意图被替换后必须立即中止修复，避免旧请求破坏新请求接管后的资源。
  test("aborts repair when the recovery intent is superseded", async () => {
    const instance = makeInstance({ status: "recovering", externalSandboxId: "provider-sandbox" });
    let destroyed = false;
    const manager = new SandboxManager({
      isMachineOnline: async () => false,
      instances: {
        findById: async () => instance,
        findByIdForUser: async () => instance,
        update: async () => instance,
      } as never,
      providers: {
        get: () => ({
          create: async () => ({ sandboxId: "created", status: "creating" as const }),
          get: async () => ({ sandboxId: "provider-sandbox", status: "stopped" as const }),
          resume: async () => ({ sandboxId: "provider-sandbox", status: "ready" as const }),
          destroy: async () => {
            destroyed = true;
          },
        }),
      } as never,
    });

    await expect(
      manager.repairRuntime(instance.id, { isCurrent: () => false }),
    ).rejects.toThrow("sandbox recovery intent superseded");

    expect(destroyed).toBe(false);
  });

  // 非属主请求删除时不得触碰 Provider 资源。
  test("does not destroy a resource when the requester is not the owner", async () => {
    const instance = makeInstance();
    let destroyed = false;
    const manager = recordingManager(instance, {
      findByIdForUser: async () => null,
      destroy: async () => {
        destroyed = true;
      },
    });

    await manager.deleteForUser(instance.id, "user_other");

    expect(destroyed).toBe(false);
  });
});
