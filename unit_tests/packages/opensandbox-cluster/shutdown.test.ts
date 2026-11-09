// shutdown.test.ts — opensandbox-cluster 关闭编排测试
// 测试目标：createShutdown 的停止顺序、首次调用记忆与失败传播
// 业务意图：关闭时必须先停监控与两个 HTTP host，再释放运行时资源；重复信号不得重复释放
// 源：packages/opensandbox-cluster/src/shutdown.ts（main 37ba68877）

import { describe, expect, test } from "bun:test";

// ── 复制实现 ──

function createShutdown(
  runtime: { monitor: { stop(): void }; close(): Promise<void> },
  api: { stop(): Promise<unknown> },
  plugin: { stop(): Promise<unknown> },
): () => Promise<void> {
  let stopping: Promise<void> | undefined;
  return () => {
    stopping ??= (async () => {
      runtime.monitor.stop();
      await Promise.all([api.stop(), plugin.stop()]);
      await runtime.close();
    })();
    return stopping;
  };
}

// ── 辅助 ──

function deferred<T = void>() {
  let resolve: (value: T) => void = () => {};
  let reject: (error: unknown) => void = () => {};
  const promise = new Promise<T>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}

// ── tests ──

describe("createShutdown 停止顺序", () => {
  test("先停监控与两个 HTTP host，最后释放运行时", async () => {
    const events: string[] = [];
    const shutdown = createShutdown(
      {
        monitor: { stop: () => events.push("monitor.stop") },
        close: async () => {
          events.push("runtime.close");
        },
      },
      {
        stop: async () => {
          events.push("api.stop");
          return {};
        },
      },
      {
        stop: async () => {
          events.push("plugin.stop");
          return {};
        },
      },
    );

    await shutdown();

    expect(events[0]).toBe("monitor.stop");
    expect(events.at(-1)).toBe("runtime.close");
    expect(events).toContain("api.stop");
    expect(events).toContain("plugin.stop");
    expect(events).toHaveLength(4);
  });

  test("任一 host 未停止完成前不释放运行时资源", async () => {
    const apiStop = deferred();
    const events: string[] = [];
    const shutdown = createShutdown(
      { monitor: { stop: () => events.push("monitor.stop") }, close: async () => events.push("runtime.close") },
      { stop: () => apiStop.promise },
      {
        stop: async () => {
          events.push("plugin.stop");
          return {};
        },
      },
    );

    const pending = shutdown();
    await Bun.sleep(1);
    expect(events).toEqual(["monitor.stop", "plugin.stop"]);

    apiStop.resolve();
    await pending;
    expect(events).toEqual(["monitor.stop", "plugin.stop", "runtime.close"]);
  });

  test("两个 host 并行停止，不串行等待", async () => {
    const order: string[] = [];
    const apiStop = deferred();
    const pluginStop = deferred();
    const shutdown = createShutdown(
      { monitor: { stop: () => {} }, close: async () => order.push("close") },
      {
        stop: () => {
          order.push("api.start");
          return apiStop.promise;
        },
      },
      {
        stop: () => {
          order.push("plugin.start");
          return pluginStop.promise;
        },
      },
    );

    const pending = shutdown();
    await Bun.sleep(1);
    // 两者都已启动；串行实现此时只会出现第一个。
    expect(order).toEqual(["api.start", "plugin.start"]);

    pluginStop.resolve();
    await Bun.sleep(1);
    expect(order).toEqual(["api.start", "plugin.start"]);

    apiStop.resolve();
    await pending;
    expect(order).toEqual(["api.start", "plugin.start", "close"]);
  });
});

describe("createShutdown 首次调用记忆", () => {
  test("重复调用返回同一 Promise，且只停止一次", async () => {
    let monitorStops = 0;
    let closes = 0;
    const shutdown = createShutdown(
      {
        monitor: {
          stop: () => {
            monitorStops++;
          },
        },
        close: async () => {
          closes++;
        },
      },
      { stop: async () => [] },
      { stop: async () => [] },
    );

    const first = shutdown();
    const second = shutdown();
    expect(second).toBe(first);
    await Promise.all([first, second]);

    expect(monitorStops).toBe(1);
    expect(closes).toBe(1);
  });

  test("host 停止失败时不再释放运行时，且重复调用复用同一拒绝", async () => {
    let monitorStops = 0;
    let closes = 0;
    const shutdown = createShutdown(
      {
        monitor: {
          stop: () => {
            monitorStops++;
          },
        },
        close: async () => {
          closes++;
        },
      },
      {
        stop: async () => {
          throw new Error("api stop failed");
        },
      },
      { stop: async () => [] },
    );

    const first = shutdown();
    const second = shutdown();
    expect(second).toBe(first);

    await expect(first).rejects.toThrow("api stop failed");
    await expect(second).rejects.toThrow("api stop failed");
    expect(monitorStops).toBe(1);
    expect(closes).toBe(0);
  });
});
