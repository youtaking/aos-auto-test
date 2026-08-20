// engine-plugin.test.ts — plugin-sdk EnginePlugin 接口结构测试
// 测试目标：验证 EnginePlugin / EngineRuntime 接口的结构兼容性
// 业务意图：确保插件实现者能正确实现接口

import { describe, test, expect } from "bun:test";

// ── 复制接口定义（来自 packages/plugin-sdk/src/engine-plugin.ts）──

interface EnginePluginMeta {
  id: string;
  displayName: string;
  version: string;
}

interface PrepareEnvironmentInput {
  instanceId: string;
  launchSpec: unknown;
  engineType?: string;
}

interface StartInstanceInput {
  instanceId: string;
}

interface StopInstanceInput {
  instanceId: string;
}

interface ConnectRelayInput {
  instanceId: string;
  sessionId?: string;
}

interface EngineRelayHandle {
  readonly state: "open" | "closed";
  send(message: { type: string; payload?: unknown }): Promise<void> | void;
  close(code?: number, reason?: string): Promise<void> | void;
  onMessage?(listener: (message: { type: string; payload?: unknown }) => void): () => void;
  ready?: Promise<void>;
}

interface EngineRuntime {
  prepareEnvironment(input: PrepareEnvironmentInput): Promise<void>;
  startInstance(input: StartInstanceInput): Promise<void>;
  stopInstance(input: StopInstanceInput): Promise<void>;
  connectRelay(input: ConnectRelayInput): Promise<EngineRelayHandle>;
}

interface EnginePlugin {
  meta: EnginePluginMeta;
  createRuntime(): EngineRuntime;
}

// ── 测试 ──

describe("EnginePlugin 接口结构", () => {
  function makeMockPlugin(): EnginePlugin {
    return {
      meta: { id: "test-engine", displayName: "Test Engine", version: "1.0.0" },
      createRuntime(): EngineRuntime {
        return {
          async prepareEnvironment() {},
          async startInstance() {},
          async stopInstance() {},
          async connectRelay(): Promise<EngineRelayHandle> {
            return {
              state: "open",
              send() {},
              close() {},
            };
          },
        };
      },
    };
  }

  test("正向 - meta 包含 id/displayName/version", () => {
    const plugin = makeMockPlugin();
    expect(plugin.meta.id).toBe("test-engine");
    expect(plugin.meta.displayName).toBe("Test Engine");
    expect(plugin.meta.version).toBe("1.0.0");
  });

  test("正向 - createRuntime 返回 EngineRuntime", async () => {
    const plugin = makeMockPlugin();
    const runtime = plugin.createRuntime();
    expect(typeof runtime.prepareEnvironment).toBe("function");
    expect(typeof runtime.startInstance).toBe("function");
    expect(typeof runtime.stopInstance).toBe("function");
    expect(typeof runtime.connectRelay).toBe("function");
  });

  test("正向 - connectRelay 返回 EngineRelayHandle", async () => {
    const plugin = makeMockPlugin();
    const runtime = plugin.createRuntime();
    const relay = await runtime.connectRelay({ instanceId: "i1" });
    expect(relay.state).toBe("open");
    expect(typeof relay.send).toBe("function");
    expect(typeof relay.close).toBe("function");
  });

  test("正向 - EngineRelayHandle onMessage 可选", async () => {
    const plugin = makeMockPlugin();
    const runtime = plugin.createRuntime();
    const relay = await runtime.connectRelay({ instanceId: "i1" });
    expect(relay.onMessage).toBeUndefined();
  });

  test("正向 - EngineRelayHandle ready 可选", async () => {
    const plugin = makeMockPlugin();
    const runtime = plugin.createRuntime();
    const relay = await runtime.connectRelay({ instanceId: "i1" });
    expect(relay.ready).toBeUndefined();
  });

  test("正向 - PrepareEnvironmentInput engineType 可选", () => {
    const input: PrepareEnvironmentInput = { instanceId: "i1", launchSpec: {} };
    expect(input.engineType).toBeUndefined();
  });

  test("正向 - ConnectRelayInput sessionId 可选", () => {
    const input: ConnectRelayInput = { instanceId: "i1" };
    expect(input.sessionId).toBeUndefined();
  });

  test("正向 - 每次 createRuntime 返回新实例", () => {
    const plugin = makeMockPlugin();
    const r1 = plugin.createRuntime();
    const r2 = plugin.createRuntime();
    expect(r1).not.toBe(r2);
  });
});
