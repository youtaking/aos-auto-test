// relay-agent-recovery.test.ts — Agent 子进程死亡后的断连自愈测试
// 测试目标：RelayEventHandler 的 connected:false 限次收敛、agentPid 去重与额度清零
// 业务意图：首次死亡必须以 1011 关闭客户端触发重连；窗口内二次死亡说明重启无法收敛，
//           下发公开错误并以 4502 终态关闭；同一进程的重复广播与无人连接不得消耗额度
// 源：packages/chat-channel/src/channel/relay-event-handler.ts（main 37ba68877）

import { describe, expect, test } from "bun:test";

// ── 复制实现 ──

const AGENT_RECOVERY_MAX_ATTEMPTS = 1;
const AGENT_RECOVERY_WINDOW_MS = 60_000;
const WEBSOCKET_CODES = { SPAWN_REJECTED: { code: 4502 } };

function readAgentPid(payload: Record<string, unknown>): number | null {
  return typeof payload.agentPid === "number" ? payload.agentPid : null;
}

interface FakeClient {
  readonly messages: unknown[];
  readonly closed: Array<[number, string]>;
  readonly failing: boolean;
  close(code: number, reason: string): void;
  send(message: unknown): void;
}

interface RecoveryDeps {
  now(): number;
  clientsOf(rcsSessionId: string): FakeClient[];
  sendToYjsWs(client: FakeClient, message: unknown): void;
  publicError(): unknown;
}

class AgentRecovery {
  private readonly agentRecoveryAttempts = new Map<string, { count: number; startedAt: number }>();
  private readonly lastDisconnectedAgentPid = new Map<string, number>();

  constructor(private readonly deps: RecoveryDeps) {}

  /** 断连入口：同一 agent 进程的重复广播只处理一次；返回是否继续收敛。 */
  handleDisconnect(rcsSessionId: string, payload: Record<string, unknown>): boolean {
    const disconnectedPid = readAgentPid(payload);
    if (disconnectedPid !== null) {
      if (this.lastDisconnectedAgentPid.get(rcsSessionId) === disconnectedPid) return false;
      this.lastDisconnectedAgentPid.set(rcsSessionId, disconnectedPid);
    }
    this.scheduleAgentRecovery(rcsSessionId);
    return true;
  }

  /** 新进程就绪（capabilities 非空）后清零，允许后续再次自愈。 */
  resetForReady(rcsSessionId: string): void {
    this.agentRecoveryAttempts.delete(rcsSessionId);
    this.lastDisconnectedAgentPid.delete(rcsSessionId);
  }

  /** 实时资源回收时清零。 */
  disposeRealtime(rcsSessionId: string): void {
    this.agentRecoveryAttempts.delete(rcsSessionId);
    this.lastDisconnectedAgentPid.delete(rcsSessionId);
  }

  private scheduleAgentRecovery(rcsSessionId: string): void {
    const clients = this.deps.clientsOf(rcsSessionId);
    // 没有可重连的客户端时不消耗额度。
    if (clients.length === 0) return;

    const now = this.deps.now();
    const previous = this.agentRecoveryAttempts.get(rcsSessionId);
    const withinWindow = previous != null && now - previous.startedAt <= AGENT_RECOVERY_WINDOW_MS;
    const count = withinWindow ? previous.count + 1 : 1;

    if (count > AGENT_RECOVERY_MAX_ATTEMPTS) {
      this.agentRecoveryAttempts.set(rcsSessionId, {
        count,
        startedAt: withinWindow ? previous.startedAt : now,
      });
      const publicError = this.deps.publicError();
      for (const entry of clients) {
        try {
          this.deps.sendToYjsWs(entry, { type: "error", payload: publicError });
        } catch {
          /* ignore */
        }
        try {
          entry.close(WEBSOCKET_CODES.SPAWN_REJECTED.code, "agent unavailable");
        } catch {
          /* ignore */
        }
      }
      return;
    }

    let closed = 0;
    for (const entry of clients) {
      try {
        entry.close(1011, "agent restarting");
        closed++;
      } catch {
        /* ignore */
      }
    }
    // 全部关闭失败等于没有触发重连：不记这一次。
    if (closed === 0) return;
    this.agentRecoveryAttempts.set(rcsSessionId, {
      count,
      startedAt: withinWindow ? previous.startedAt : now,
    });
  }
}

// ── 辅助 ──

function createClient(failing = false): FakeClient {
  const messages: unknown[] = [];
  const closed: Array<[number, string]> = [];
  return {
    messages,
    closed,
    failing,
    close(code, reason) {
      if (failing) throw new Error("socket already closed");
      closed.push([code, reason]);
    },
    send(message) {
      messages.push(message);
    },
  };
}

function harness(rcsSessionId = "rcs-1") {
  let now = 1_000;
  const clients = new Map<string, FakeClient[]>();
  const publicError = { type: "CONTROL_PLANE.INSTANCE_START_FAILED", id: "err-1", message: "agent unavailable" };
  const recovery = new AgentRecovery({
    now: () => now,
    clientsOf: (id) => clients.get(id) ?? [],
    sendToYjsWs: (client, message) => client.send(message),
    publicError: () => publicError,
  });
  return {
    recovery,
    publicError,
    rcsSessionId,
    setNow: (value: number) => {
      now = value;
    },
    addClient: (client: FakeClient, id = rcsSessionId) => {
      clients.set(id, [...(clients.get(id) ?? []), client]);
    },
  };
}

// ── tests ──

describe("断连自愈额度", () => {
  test("首次死亡以 1011 关闭客户端且不下发错误", () => {
    const h = harness();
    const client = createClient();
    h.addClient(client);

    expect(h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: 100 })).toBe(true);
    expect(client.closed).toEqual([[1011, "agent restarting"]]);
    expect(client.messages).toEqual([]);
  });

  test("窗口内不同进程的二次死亡下发公开错误并以 4502 终态关闭", () => {
    const h = harness();
    const client = createClient();
    h.addClient(client);

    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: 100 });
    h.setNow(2_000);
    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: 200 });

    expect(client.closed).toEqual([
      [1011, "agent restarting"],
      [4502, "agent unavailable"],
    ]);
    expect(client.messages).toEqual([{ type: "error", payload: h.publicError }]);
  });

  test("窗口边界含等号：恰好 60s 仍视为同一窗口", () => {
    const h = harness();
    const client = createClient();
    h.addClient(client);

    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: 100 });
    h.setNow(61_000);
    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: 200 });

    expect(client.closed.at(-1)).toEqual([4502, "agent unavailable"]);
  });

  test("窗口过期后重新获得一次自愈额度", () => {
    const h = harness();
    const client = createClient();
    h.addClient(client);

    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: 100 });
    h.setNow(61_001);
    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: 200 });
    h.setNow(62_001);
    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: 300 });

    expect(client.closed).toEqual([
      [1011, "agent restarting"],
      [1011, "agent restarting"],
      [4502, "agent unavailable"],
    ]);
    expect(client.messages).toHaveLength(1);
  });
});

describe("同一进程去重", () => {
  test("同 pid 的重复广播只消费一次额度且不重复关闭", () => {
    const h = harness();
    const client = createClient();
    h.addClient(client);

    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: 100 });
    const handled = h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: 100 });

    expect(handled).toBe(false);
    expect(client.closed).toEqual([[1011, "agent restarting"]]);
    expect(client.messages).toEqual([]);
  });

  test("旧版 acp-link 不带 pid 时不去重，二次死亡仍判终态", () => {
    const h = harness();
    const client = createClient();
    h.addClient(client);

    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false });
    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false });

    expect(client.closed).toEqual([
      [1011, "agent restarting"],
      [4502, "agent unavailable"],
    ]);
  });

  test("pid 不是数字时按旧版处理", () => {
    const h = harness();
    const client = createClient();
    h.addClient(client);

    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: "100" });
    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: "100" });

    expect(client.closed.at(-1)).toEqual([4502, "agent unavailable"]);
  });
});

describe("额度不被无效事件消耗", () => {
  test("无人连接时的死亡不消耗额度", () => {
    const h = harness();
    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: 100 });

    const client = createClient();
    h.addClient(client);
    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: 200 });

    expect(client.closed).toEqual([[1011, "agent restarting"]]);
  });

  test("全部关闭失败等于没有触发重连，不消耗额度", () => {
    const h = harness();
    const failing = createClient(true);
    h.addClient(failing);
    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: 100 });

    const working = createClient();
    h.addClient(working);
    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: 200 });

    expect(failing.closed).toEqual([]);
    expect(working.closed).toEqual([[1011, "agent restarting"]]);
  });
});

describe("额度清零", () => {
  test("新进程就绪后清零，后续死亡重新获得一次额度", () => {
    const h = harness();
    const client = createClient();
    h.addClient(client);

    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: 100 });
    h.recovery.resetForReady(h.rcsSessionId);
    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: 200 });

    expect(client.closed).toEqual([
      [1011, "agent restarting"],
      [1011, "agent restarting"],
    ]);
    expect(client.messages).toEqual([]);
  });

  test("实时资源回收后清零，且不跳过去重记录", () => {
    const h = harness();
    const client = createClient();
    h.addClient(client);

    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: 100 });
    h.recovery.disposeRealtime(h.rcsSessionId);
    h.recovery.handleDisconnect(h.rcsSessionId, { connected: false, agentPid: 100 });

    expect(client.closed).toEqual([
      [1011, "agent restarting"],
      [1011, "agent restarting"],
    ]);
  });

  test("不同 rcsSessionId 的额度互不影响", () => {
    const h = harness("rcs-a");
    const first = createClient();
    h.addClient(first, "rcs-a");
    const second = createClient();
    h.addClient(second, "rcs-b");

    h.recovery.handleDisconnect("rcs-a", { connected: false, agentPid: 100 });
    h.recovery.handleDisconnect("rcs-b", { connected: false, agentPid: 100 });

    expect(first.closed).toEqual([[1011, "agent restarting"]]);
    expect(second.closed).toEqual([[1011, "agent restarting"]]);
  });
});
