// command-history.test.ts — 命令历史保留与防重放证据测试
// 测试目标：CommandHistory 的 forgotten 证据、代次换代与容量淘汰顺序
// 业务意图：结果到期只释放结果、不能遗忘本代命令身份；容量耗尽必须先换代再释放精确证据；
//           已接纳命令在重放窗口内必须始终被 epoch 或 forgotten 围栏拒绝
// 源：packages/chat-channel/src/channel/command-history.ts（main 37ba68877）

import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { randomUUID } from "node:crypto";

// ── 复制实现 ──

const MAX_ACTIVE_SESSIONS = 256;
const MAX_ACTIVE_COMMANDS_PER_SESSION = 512;
const CANCEL_RESERVE = 2;
const MAX_HISTORY_RECORDS = 16_384;
const MAX_FORGOTTEN_COMMANDS = 16_384;
const HISTORY_RETENTION_MS = 10 * 60_000;

interface ActionAck {
  readonly commandId: string;
  readonly status: string;
}
interface ActionError {
  readonly commandId: string;
  readonly error: { type: string };
}
interface Command {
  readonly commandId: string;
  readonly type: string;
  readonly rcsSessionId: string;
  readonly sessionId: string;
  readonly payload: Record<string, unknown>;
}

interface CommandRecord {
  readonly commandId: string;
  readonly rcsSessionId: string;
  readonly epoch: string;
  admitted: boolean;
  result: CommandRecordResult;
  expiresAt: number;
}

type CommandRecordResult =
  | { state: "in_flight"; ack: ActionAck }
  | { state: "committed"; ack: ActionAck }
  | { state: "failed"; error: ActionError }
  | { state: "unknown" };

class CommandHistory {
  private epoch = randomUUID();
  private readonly active = new Map<string, Map<string, CommandRecord>>();
  private readonly history = new Map<string, CommandRecord>();
  private readonly forgotten = new Set<string>();
  private readonly epochListeners = new Set<(epoch: string) => void>();
  private nextExpiry = Number.POSITIVE_INFINITY;
  private expiryTimer: ReturnType<typeof setTimeout> | undefined;
  private scheduledExpiry = Number.POSITIVE_INFINITY;
  private maintaining = false;

  constructor(
    private readonly now: () => number,
    private readonly reportError?: (context: string, error: unknown) => void,
  ) {}

  getEpoch(): string {
    this.pruneHistory();
    return this.epoch;
  }

  onEpochChanged(listener: (epoch: string) => void): () => void {
    this.epochListeners.add(listener);
    return () => this.epochListeners.delete(listener);
  }

  find(rcsSessionId: string, commandId: string): CommandRecord | undefined {
    return this.active.get(rcsSessionId)?.get(commandId) ?? this.history.get(this.key(rcsSessionId, commandId));
  }

  isForgotten(rcsSessionId: string, commandId: string): boolean {
    return this.forgotten.has(this.key(rcsSessionId, commandId));
  }

  prepareAdmission(): void {
    this.pruneHistory();
  }

  admit(command: Command, ack: ActionAck): CommandRecord | undefined {
    const reserve = command.type === "cancel" ? CANCEL_RESERVE : 0;
    let session = this.active.get(command.rcsSessionId);
    if (!session && this.active.size >= MAX_ACTIVE_SESSIONS + reserve) return;
    if (session && session.size >= MAX_ACTIVE_COMMANDS_PER_SESSION + reserve) return;
    if (!session) {
      session = new Map();
      this.active.set(command.rcsSessionId, session);
    }
    const record: CommandRecord = {
      rcsSessionId: command.rcsSessionId,
      commandId: command.commandId,
      epoch: this.epoch,
      admitted: false,
      result: { state: "in_flight", ack },
      expiresAt: Number.POSITIVE_INFINITY,
    };
    session.set(command.commandId, record);
    return record;
  }

  discard(record: CommandRecord): void {
    if (record.admitted) throw new Error("An accepted command requires a retained outcome");
    this.removeActive(record);
  }

  settle(record: CommandRecord, result: CommandRecordResult): void {
    if (this.active.get(record.rcsSessionId)?.get(record.commandId) !== record) return;
    record.result = result;
    this.removeActive(record);
    record.expiresAt = this.now() + HISTORY_RETENTION_MS;
    this.nextExpiry = Math.min(this.nextExpiry, record.expiresAt);
    this.history.set(this.key(record.rcsSessionId, record.commandId), record);
    this.pruneHistory();
    this.scheduleExpiry();
  }

  private removeActive(record: CommandRecord): void {
    const session = this.active.get(record.rcsSessionId);
    if (session?.get(record.commandId) !== record) return;
    session.delete(record.commandId);
    if (session.size === 0) this.active.delete(record.rcsSessionId);
  }

  private pruneHistory(): void {
    if (this.maintaining) return;
    const now = this.now();
    const capacityReached = this.history.size >= MAX_HISTORY_RECORDS;
    if (!capacityReached && now < this.nextExpiry) return;
    this.maintaining = true;
    try {
      if (capacityReached) this.rotateEpoch();
      const target = Math.floor(MAX_HISTORY_RECORDS * 0.75);
      this.nextExpiry = Number.POSITIVE_INFINITY;
      for (const [key, record] of this.history) {
        if (record.expiresAt > now && (!capacityReached || this.history.size <= target)) {
          this.nextExpiry = Math.min(this.nextExpiry, record.expiresAt);
          continue;
        }
        if (record.epoch === this.epoch && record.admitted) {
          if (this.forgotten.size >= MAX_FORGOTTEN_COMMANDS) this.rotateEpoch();
          else this.forgotten.add(key);
        }
        this.history.delete(key);
      }
    } finally {
      this.maintaining = false;
      this.scheduleExpiry();
    }
  }

  private scheduleExpiry(): void {
    if (this.expiryTimer && this.scheduledExpiry === this.nextExpiry) return;
    if (this.expiryTimer) clearTimeout(this.expiryTimer);
    this.expiryTimer = undefined;
    this.scheduledExpiry = this.nextExpiry;
    if (!Number.isFinite(this.nextExpiry)) return;
    this.expiryTimer = setTimeout(
      () => {
        this.expiryTimer = undefined;
        this.pruneHistory();
        this.scheduleExpiry();
      },
      Math.max(1, this.nextExpiry - this.now()),
    );
    this.expiryTimer.unref();
  }

  private rotateEpoch(): void {
    this.epoch = randomUUID();
    this.forgotten.clear();
    for (const listener of this.epochListeners) {
      try {
        listener(this.epoch);
      } catch (error) {
        try {
          this.reportError?.("[CommandHistory] command epoch publication failed", error);
        } catch {
          // 诊断 sink 故障不能阻断其他订阅者。
        }
      }
    }
  }

  private key(rcsSessionId: string, commandId: string): string {
    return JSON.stringify([rcsSessionId, commandId]);
  }
}

// ── 辅助 ──

// 容量用例需要真实推进时钟 16k 次；定时器本身不参与断言，替换为空句柄避免调度开销。
let realSetTimeout: typeof setTimeout;
let realClearTimeout: typeof clearTimeout;

beforeEach(() => {
  realSetTimeout = globalThis.setTimeout;
  realClearTimeout = globalThis.clearTimeout;
  globalThis.setTimeout = (() => ({ unref() {} })) as unknown as typeof setTimeout;
  globalThis.clearTimeout = (() => {}) as unknown as typeof clearTimeout;
});

afterEach(() => {
  globalThis.setTimeout = realSetTimeout;
  globalThis.clearTimeout = realClearTimeout;
});

function makeCommand(rcsSessionId = "rcs-1"): Command {
  return {
    commandId: randomUUID(),
    type: "send_prompt",
    rcsSessionId,
    sessionId: "ses-1",
    payload: {},
  };
}

function ack(commandId: string): ActionAck {
  return { commandId, status: "accepted" };
}

function committed(record: CommandRecord): CommandRecordResult {
  return { state: "committed", ack: ack(record.commandId) };
}

/** 准入并结算一条记录；admitted 表示是否已进入执行（决定是否保留防重放证据）。 */
function settleOne(history: CommandHistory, command: Command, admitted = true): CommandRecord {
  const record = history.admit(command, ack(command.commandId))!;
  record.admitted = admitted;
  history.settle(record, committed(record));
  return record;
}

// ── tests ──

describe("结果到期仍保留本代身份", () => {
  test("已接纳结果到期后写入 forgotten，且 epoch 不变", () => {
    let now = 0;
    const history = new CommandHistory(() => now);
    const command = makeCommand();
    const epoch = history.getEpoch();
    settleOne(history, command);

    expect(history.find(command.rcsSessionId, command.commandId)).toBeDefined();
    now = HISTORY_RETENTION_MS;
    expect(history.getEpoch()).toBe(epoch);
    expect(history.find(command.rcsSessionId, command.commandId)).toBeUndefined();
    expect(history.isForgotten(command.rcsSessionId, command.commandId)).toBe(true);
  });

  test("未被接纳的记录到期不写入 forgotten（无外部副作用可重放）", () => {
    let now = 0;
    const history = new CommandHistory(() => now);
    const command = makeCommand();
    settleOne(history, command, false);

    now = HISTORY_RETENTION_MS;
    history.getEpoch();
    expect(history.find(command.rcsSessionId, command.commandId)).toBeUndefined();
    expect(history.isForgotten(command.rcsSessionId, command.commandId)).toBe(false);
  });

  test("未到期结果仍可精确查询且不进入 forgotten", () => {
    let now = 0;
    const history = new CommandHistory(() => now);
    const command = makeCommand();
    settleOne(history, command);

    now = HISTORY_RETENTION_MS - 1;
    history.getEpoch();
    expect(history.find(command.rcsSessionId, command.commandId)).toBeDefined();
    expect(history.isForgotten(command.rcsSessionId, command.commandId)).toBe(false);
  });
});

describe("forgotten 容量换代", () => {
  test("证据达到上限时先换代再释放，旧身份由 epoch 围栏接管", () => {
    let now = 0;
    const history = new CommandHistory(() => now);
    const epoch = history.getEpoch();
    const rotations: string[] = [];
    history.onEpochChanged((next) => rotations.push(next));

    let first: Command | undefined;
    for (let index = 0; index <= MAX_FORGOTTEN_COMMANDS; index++) {
      const command = makeCommand();
      if (index === 0) first = command;
      settleOne(history, command);
      now += HISTORY_RETENTION_MS;
      if (index < MAX_FORGOTTEN_COMMANDS) expect(history.getEpoch()).toBe(epoch);
    }

    expect(history.getEpoch()).not.toBe(epoch);
    expect(rotations).toHaveLength(1);
    // 换代后旧证据被释放，但旧命令已被 epoch 围栏拒绝。
    expect(history.isForgotten(first!.rcsSessionId, first!.commandId)).toBe(false);
  });

  test("换代先清空旧证据再通知订阅者", () => {
    let now = 0;
    const history = new CommandHistory(() => now);
    const expired = makeCommand();
    settleOne(history, expired);
    now = HISTORY_RETENTION_MS;
    history.getEpoch();
    expect(history.isForgotten(expired.rcsSessionId, expired.commandId)).toBe(true);

    const observed: boolean[] = [];
    history.onEpochChanged(() => {
      observed.push(history.isForgotten(expired.rcsSessionId, expired.commandId));
    });
    for (let index = 0; index < MAX_HISTORY_RECORDS; index++) {
      settleOne(history, makeCommand(), false);
    }

    expect(observed).toEqual([false]);
  });
});

describe("历史容量换代", () => {
  test("历史达到上限先换代再淘汰到 75%，保留的记录仍可查询", () => {
    const now = 0;
    const history = new CommandHistory(() => now);
    const epoch = history.getEpoch();
    const commands = Array.from({ length: MAX_HISTORY_RECORDS }, () => makeCommand());
    for (const command of commands) settleOne(history, command, false);

    expect(history.getEpoch()).not.toBe(epoch);
    // 最早 25% 被淘汰，剩余 75% 保留（均为换代码前的旧代记录）。
    expect(history.find(commands[0]!.rcsSessionId, commands[0]!.commandId)).toBeUndefined();
    expect(history.find(commands[4096]!.rcsSessionId, commands[4096]!.commandId)).toBeDefined();
    expect(history.isForgotten(commands[0]!.rcsSessionId, commands[0]!.commandId)).toBe(false);
  });

  test("每条连接的未结算记录不被容量淘汰影响", () => {
    const now = 0;
    const history = new CommandHistory(() => now);
    const hot = makeCommand("rcs-hot");
    const inFlight = history.admit(hot, ack(hot.commandId))!;
    expect(inFlight).toBeDefined();
    for (let index = 0; index < MAX_HISTORY_RECORDS; index++) settleOne(history, makeCommand(), false);
    expect(history.find(hot.rcsSessionId, hot.commandId)).toBe(inFlight);
  });
});

describe("订阅与容错", () => {
  test("退订后不再收到换代通知", () => {
    const now = 0;
    const history = new CommandHistory(() => now);
    const seen: string[] = [];
    const off = history.onEpochChanged((next) => seen.push(next));
    off();
    for (let index = 0; index < MAX_HISTORY_RECORDS; index++) settleOne(history, makeCommand(), false);
    expect(seen).toEqual([]);
  });

  test("单个订阅者异常不影响其它订阅者", () => {
    const now = 0;
    const history = new CommandHistory(() => now);
    const seen: string[] = [];
    history.onEpochChanged(() => {
      throw new Error("boom");
    });
    history.onEpochChanged((next) => seen.push(next));
    for (let index = 0; index < MAX_HISTORY_RECORDS; index++) settleOne(history, makeCommand(), false);
    expect(seen).toHaveLength(1);
  });
});
