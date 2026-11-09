// command-coordinator.test.ts — 命令重放围栏测试
// 测试目标：CommandCoordinator 准入顺序中的 isForgotten 围栏（结果到期仍拒绝重放）
// 业务意图：结果 TTL 回收后 epoch 可能未变，若只校验 epoch，已执行过的外部副作用命令会被再次执行；
//           未接纳记录没有外部副作用，不得被 forgotten 误伤
// 源：packages/chat-channel/src/channel/command-coordinator.ts（main 37ba68877）

import { describe, expect, test } from "bun:test";

// ── 复制实现：CommandHistory 的最小准入/证据部分 ──

const HISTORY_RETENTION_MS = 10 * 60_000;

type ResultState = "in_flight" | "committed" | "failed" | "unknown";

interface CommandRecord {
  commandId: string;
  rcsSessionId: string;
  epoch: string;
  admitted: boolean;
  result: ResultState;
  expiresAt: number;
}

class CommandHistory {
  private epoch = "epoch-1";
  private readonly active = new Map<string, Map<string, CommandRecord>>();
  private readonly history = new Map<string, CommandRecord>();
  private readonly forgotten = new Set<string>();

  constructor(private readonly now: () => number) {}

  getEpoch(): string {
    this.pruneHistory();
    return this.epoch;
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

  admit(rcsSessionId: string, commandId: string): CommandRecord {
    let session = this.active.get(rcsSessionId);
    if (!session) {
      session = new Map();
      this.active.set(rcsSessionId, session);
    }
    const record: CommandRecord = {
      commandId,
      rcsSessionId,
      epoch: this.epoch,
      admitted: false,
      result: "in_flight",
      expiresAt: Number.POSITIVE_INFINITY,
    };
    session.set(commandId, record);
    return record;
  }

  settle(record: CommandRecord, admitted: boolean, result: ResultState = "committed"): void {
    record.admitted = admitted;
    record.result = result;
    this.active.get(record.rcsSessionId)?.delete(record.commandId);
    record.expiresAt = this.now() + HISTORY_RETENTION_MS;
    this.history.set(this.key(record.rcsSessionId, record.commandId), record);
  }

  private pruneHistory(): void {
    const now = this.now();
    for (const [key, record] of this.history) {
      if (record.expiresAt > now) continue;
      if (record.epoch === this.epoch && record.admitted) this.forgotten.add(key);
      this.history.delete(key);
    }
  }

  private key(rcsSessionId: string, commandId: string): string {
    return JSON.stringify([rcsSessionId, commandId]);
  }
}

// ── 复制实现：CommandCoordinator.submitCommand 的准入分支 ──

type Verdict = "ADMIT" | "DUP" | "OUTCOME_UNKNOWN" | "FAILED";

function admissionVerdict(
  history: CommandHistory,
  rcsSessionId: string,
  commandId: string,
  clientEpoch?: string,
): Verdict {
  const existingRecord = history.find(rcsSessionId, commandId);
  if (existingRecord) {
    if (!existingRecord.admitted) return "OUTCOME_UNKNOWN";
    if (existingRecord.result === "unknown") return "OUTCOME_UNKNOWN";
    if (existingRecord.result === "committed") return "DUP";
    if (existingRecord.result === "failed") return "FAILED";
    return "DUP";
  }
  history.prepareAdmission();
  if (
    history.isForgotten(rcsSessionId, commandId) ||
    (clientEpoch !== undefined && clientEpoch !== history.getEpoch())
  ) {
    return "OUTCOME_UNKNOWN";
  }
  return "ADMIT";
}

// ── tests ──

describe("结果到期后的重放围栏", () => {
  test("已接纳命令结果到期且 epoch 未变时仍拒绝重放", () => {
    let now = 0;
    const history = new CommandHistory(() => now);
    const epoch = history.getEpoch();
    const commandId = "cmd-1";

    history.settle(history.admit("rcs-1", commandId), true);
    now = HISTORY_RETENTION_MS;

    // 结果已回收、epoch 未轮换：只有 forgotten 能拦住重放。
    expect(history.getEpoch()).toBe(epoch);
    expect(history.find("rcs-1", commandId)).toBeUndefined();
    expect(history.isForgotten("rcs-1", commandId)).toBe(true);
    expect(admissionVerdict(history, "rcs-1", commandId, epoch)).toBe("OUTCOME_UNKNOWN");
  });

  test("结果到期后不同代次同样拒绝", () => {
    let now = 0;
    const history = new CommandHistory(() => now);
    const commandId = "cmd-2";

    history.settle(history.admit("rcs-1", commandId), true);
    now = HISTORY_RETENTION_MS;
    history.prepareAdmission();

    expect(admissionVerdict(history, "rcs-1", commandId, "stale-epoch")).toBe("OUTCOME_UNKNOWN");
  });

  test("未接纳记录到期不进入 forgotten，重放可准入", () => {
    let now = 0;
    const history = new CommandHistory(() => now);
    const epoch = history.getEpoch();
    const commandId = "cmd-3";

    history.settle(history.admit("rcs-1", commandId), false);
    now = HISTORY_RETENTION_MS;
    history.prepareAdmission();

    expect(history.find("rcs-1", commandId)).toBeUndefined();
    expect(history.isForgotten("rcs-1", commandId)).toBe(false);
    expect(admissionVerdict(history, "rcs-1", commandId, epoch)).toBe("ADMIT");
  });

  test("未到期已提交结果命中精确记录，返回重复确认", () => {
    let now = 0;
    const history = new CommandHistory(() => now);
    const epoch = history.getEpoch();
    const commandId = "cmd-4";

    history.settle(history.admit("rcs-1", commandId), true, "committed");
    now = HISTORY_RETENTION_MS - 1;

    expect(history.find("rcs-1", commandId)).toBeDefined();
    expect(history.isForgotten("rcs-1", commandId)).toBe(false);
    expect(admissionVerdict(history, "rcs-1", commandId, epoch)).toBe("DUP");
  });

  test("未到期失败结果命中精确记录，返回失败回执", () => {
    const history = new CommandHistory(() => 0);
    const epoch = history.getEpoch();
    const commandId = "cmd-5";

    history.settle(history.admit("rcs-1", commandId), true, "failed");

    expect(admissionVerdict(history, "rcs-1", commandId, epoch)).toBe("FAILED");
  });

  test("未接纳的在途记录命中时返回结果未知", () => {
    const history = new CommandHistory(() => 0);
    const epoch = history.getEpoch();
    const commandId = "cmd-6";

    history.admit("rcs-1", commandId);

    expect(admissionVerdict(history, "rcs-1", commandId, epoch)).toBe("OUTCOME_UNKNOWN");
  });

  test("同代次从未出现的命令可准入", () => {
    const history = new CommandHistory(() => 0);
    const epoch = history.getEpoch();
    expect(admissionVerdict(history, "rcs-1", "cmd-new", epoch)).toBe("ADMIT");
  });

  test("不同 rcsSessionId 的同名 commandId 证据互不影响", () => {
    let now = 0;
    const history = new CommandHistory(() => now);
    const epoch = history.getEpoch();

    history.settle(history.admit("rcs-a", "cmd-x"), true);
    now = HISTORY_RETENTION_MS;
    history.prepareAdmission();

    expect(admissionVerdict(history, "rcs-a", "cmd-x", epoch)).toBe("OUTCOME_UNKNOWN");
    expect(admissionVerdict(history, "rcs-b", "cmd-x", epoch)).toBe("ADMIT");
  });
});
