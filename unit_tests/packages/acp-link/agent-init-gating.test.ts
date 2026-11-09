// agent-init-gating.test.ts — 冷启动 initialize 门控与断连广播去重测试
// 测试目标：waitForAgentCapabilities 的返回值语义、announceDisconnect 单次广播、session/new 门控顺序
// 业务意图：initialize 在途时必须等落定再建会话；超时/失败要明确拒绝而不是伪装成会话创建失败；
//           socket 关闭后不得再绑定会话；同一进程的 EOF 与 exit 只能广播一次断连
// 源：packages/acp-link/src/server.ts（main 37ba68877）

import { describe, expect, test } from "bun:test";

// ── 复制实现 ──

const AGENT_INIT_WAIT_TIMEOUT_MS = 10_000;

interface WaitOptions {
  inFlight: Promise<unknown> | null;
  timeoutMs?: number;
  warn?: (message: string) => void;
}

function createWaitForAgentCapabilities(options: WaitOptions) {
  const timeoutMs = options.timeoutMs ?? AGENT_INIT_WAIT_TIMEOUT_MS;
  return async function waitForAgentCapabilities(clientState: {
    agentCapabilities: unknown | null;
  }): Promise<boolean> {
    if (clientState.agentCapabilities !== null) return true;
    const inFlight = options.inFlight;
    if (inFlight === null) return false;

    let timedOut = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      await Promise.race([
        inFlight,
        new Promise<void>((resolve) => {
          timer = setTimeout(() => {
            timedOut = true;
            resolve();
          }, timeoutMs);
        }),
      ]);
      return !timedOut;
    } catch (error) {
      options.warn?.(error instanceof Error ? error.message : typeof error);
      return false;
    } finally {
      if (timer !== undefined) clearTimeout(timer);
    }
  };
}

function createDisconnectAnnouncer(broadcast: (message: unknown) => void) {
  let agentPid: number | undefined;
  let disconnectAnnounced = false;
  return {
    started(pid: number) {
      agentPid = pid;
    },
    announce() {
      if (disconnectAnnounced) return;
      disconnectAnnounced = true;
      broadcast({ type: "status", payload: { connected: false, agentPid } });
    },
  };
}

function errorResponse(message: string) {
  return { jsonrpc: "2.0", error: { code: -32000, message } };
}

interface GateOptions {
  state: { connection: object | null; agentCapabilities?: unknown | null };
  inFlight: Promise<unknown> | null;
  clients: Set<object>;
  timeoutMs?: number;
  warn?: (message: string) => void;
  newSession?: () => Promise<{ sessionId: string }>;
}

/** handleNewSession 的门控顺序：等待初始化 → 未连接 → 未完成 → socket 已关 → 建会话 → 建完再验 socket。 */
async function runNewSession(ws: object, options: GateOptions) {
  const sent: unknown[] = [];
  let bound: string | null = null;
  const waitForAgentCapabilities = createWaitForAgentCapabilities(options);

  const initialized = await waitForAgentCapabilities(options.state);
  if (!options.state.connection) {
    sent.push(errorResponse("Not connected to agent"));
    return { sent, bound, outcome: "not-connected" as const };
  }
  if (!initialized) {
    sent.push(errorResponse("Agent initialization is not complete"));
    return { sent, bound, outcome: "init-pending" as const };
  }
  if (!options.clients.has(ws)) {
    return { sent, bound, outcome: "socket-closed-early" as const };
  }

  const result = await (options.newSession ?? (async () => ({ sessionId: "ses-1" })))();
  if (!options.clients.has(ws)) {
    return { sent, bound, outcome: "socket-closed-during-create" as const };
  }
  bound = result.sessionId;
  return { sent, bound, outcome: "bound" as const };
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

function flush() {
  return Bun.sleep(5);
}

// ── tests ──

describe("waitForAgentCapabilities 返回值", () => {
  test("能力已知时立即返回真，不等待在途 initialize", async () => {
    const inFlight = deferred();
    let warnCount = 0;
    const wait = createWaitForAgentCapabilities({ inFlight: inFlight.promise, warn: () => warnCount++ });

    expect(await wait({ agentCapabilities: { loadSession: true } })).toBe(true);
    expect(warnCount).toBe(0);
  });

  test("没有在途 initialize 且能力未知时返回假", async () => {
    const wait = createWaitForAgentCapabilities({ inFlight: null });
    expect(await wait({ agentCapabilities: null })).toBe(false);
  });

  test("在途 initialize 落定后返回真（能力为空也算完成）", async () => {
    const inFlight = deferred();
    const wait = createWaitForAgentCapabilities({ inFlight: inFlight.promise });
    const pending = wait({ agentCapabilities: null });

    inFlight.resolve();
    expect(await pending).toBe(true);
  });

  test("initialize 拒绝时返回假并记录告警", async () => {
    const inFlight = deferred();
    const warnings: string[] = [];
    const wait = createWaitForAgentCapabilities({ inFlight: inFlight.promise, warn: (m) => warnings.push(m) });
    const pending = wait({ agentCapabilities: null });

    inFlight.reject(new Error("handshake failed"));
    expect(await pending).toBe(false);
    expect(warnings).toEqual(["handshake failed"]);
  });

  test("initialize 超时返回假且不抛错", async () => {
    const inFlight = deferred();
    const wait = createWaitForAgentCapabilities({ inFlight: inFlight.promise, timeoutMs: 10 });

    expect(await wait({ agentCapabilities: null })).toBe(false);
  });

  test("超时后 initialize 迟到落定不改变已返回的假", async () => {
    const inFlight = deferred();
    const wait = createWaitForAgentCapabilities({ inFlight: inFlight.promise, timeoutMs: 10 });
    const first = await wait({ agentCapabilities: null });
    inFlight.resolve();
    await flush();
    expect(first).toBe(false);
  });
});

describe("announceDisconnect 单次广播", () => {
  test("流 EOF 先到、子进程 exit 后到也只广播一次，并携带 pid", () => {
    const messages: unknown[] = [];
    const announcer = createDisconnectAnnouncer((message) => messages.push(message));
    announcer.started(4_242);

    announcer.announce();
    announcer.announce();

    expect(messages).toEqual([{ type: "status", payload: { connected: false, agentPid: 4_242 } }]);
  });

  test("子进程 exit 先到、流 EOF 后到同样只广播一次", () => {
    const messages: unknown[] = [];
    const announcer = createDisconnectAnnouncer((message) => messages.push(message));
    announcer.started(7);

    announcer.announce();
    announcer.announce();

    expect(messages).toHaveLength(1);
    expect(messages[0]).toMatchObject({ payload: { connected: false, agentPid: 7 } });
  });
});

describe("session/new 门控顺序", () => {
  test("initialize 在途时先等待，落定后再创建并绑定会话", async () => {
    const inFlight = deferred();
    const clients = new Set<object>([{}]);
    const ws = [...clients][0]!;
    const result = runNewSession(ws, {
      state: { connection: {}, agentCapabilities: null },
      inFlight: inFlight.promise,
      clients,
    });

    await flush();
    expect(clients.size).toBe(1);
    inFlight.resolve();

    expect(await result).toMatchObject({ outcome: "bound", bound: "ses-1", sent: [] });
  });

  test("初始化超时返回明确错误，不创建会话", async () => {
    let created = 0;
    const ws = {};
    const result = await runNewSession(ws, {
      state: { connection: {}, agentCapabilities: null },
      inFlight: deferred().promise,
      clients: new Set<object>([ws]),
      timeoutMs: 10,
      newSession: async () => {
        created++;
        return { sessionId: "ses" };
      },
    });

    expect(result.outcome).toBe("init-pending");
    expect(result.sent).toEqual([errorResponse("Agent initialization is not complete")]);
    expect(created).toBe(0);
  });

  test("等待期间状态断开则下发 Not connected 且不创建会话", async () => {
    const inFlight = deferred();
    const state: { connection: object | null; agentCapabilities?: unknown | null } = {
      connection: {},
      agentCapabilities: null,
    };
    let created = 0;
    const ws = {};
    const result = runNewSession(ws, {
      state,
      inFlight: inFlight.promise,
      clients: new Set<object>([ws]),
      newSession: async () => {
        created++;
        return { sessionId: "ses" };
      },
    });

    state.connection = null;
    inFlight.resolve();

    expect(await result).toEqual({
      sent: [errorResponse("Not connected to agent")],
      bound: null,
      outcome: "not-connected",
    });
    expect(created).toBe(0);
  });

  test("等待期间 socket 被清理则直接放弃，不发错误也不绑定", async () => {
    const inFlight = deferred();
    const clients = new Set<object>();
    const ws = {};
    const result = runNewSession(ws, {
      state: { connection: {}, agentCapabilities: null },
      inFlight: inFlight.promise,
      clients,
    });

    inFlight.resolve();
    expect(await result).toEqual({ sent: [], bound: null, outcome: "socket-closed-early" });
  });

  test("建会话期间 socket 关闭则不绑定该会话", async () => {
    const clients = new Set<object>();
    const ws = {};
    clients.add(ws);
    const result = await runNewSession(ws, {
      state: { connection: {}, agentCapabilities: null },
      inFlight: Promise.resolve(),
      clients,
      newSession: async () => {
        clients.delete(ws);
        return { sessionId: "ses-orphan" };
      },
    });

    expect(result).toEqual({ sent: [], bound: null, outcome: "socket-closed-during-create" });
  });
});
