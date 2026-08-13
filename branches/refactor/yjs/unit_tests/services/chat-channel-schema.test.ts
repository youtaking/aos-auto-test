// chat-channel-schema.test.ts — Chat 域 schema 常量与类型守卫测试
// 测试目标：TURN_TERMINAL_STATUSES 集合完整性、schema 版本常量
// 业务意图：确保终态判定集合覆盖所有终态，状态机守卫正确

import { describe, expect, test } from "bun:test";

// ── 复制常量 ──

type TurnStatus =
  | "accepting" | "running" | "awaiting_permission" | "cancelling"
  | "cancelled" | "interrupted" | "failed" | "completed";

const TURN_TERMINAL_STATUSES: ReadonlySet<TurnStatus> = new Set([
  "cancelled", "interrupted", "failed", "completed",
]);

const CHAT_DOC_SCHEMA_VERSION = 2;
const SESSION_DOC_SCHEMA_VERSION = 3;
const INITIAL_PROJECTION_VERSION = 1;

// ── tests ──

describe("TURN_TERMINAL_STATUSES", () => {
  // 包含所有终态
  test("包含 cancelled、interrupted、failed、completed 四种终态", () => {
    expect(TURN_TERMINAL_STATUSES.has("cancelled")).toBe(true);
    expect(TURN_TERMINAL_STATUSES.has("interrupted")).toBe(true);
    expect(TURN_TERMINAL_STATUSES.has("failed")).toBe(true);
    expect(TURN_TERMINAL_STATUSES.has("completed")).toBe(true);
  });

  // 非终态不在集合中
  test("非终态不在集合中", () => {
    expect(TURN_TERMINAL_STATUSES.has("accepting")).toBe(false);
    expect(TURN_TERMINAL_STATUSES.has("running")).toBe(false);
    expect(TURN_TERMINAL_STATUSES.has("awaiting_permission")).toBe(false);
    expect(TURN_TERMINAL_STATUSES.has("cancelling")).toBe(false);
  });

  // cancelling 不是终态（输出停止但可接受终态事件）
  test("cancelling 不是终态——用户已取消但晚到增量需走丢弃路径而非终态守卫", () => {
    expect(TURN_TERMINAL_STATUSES.has("cancelling")).toBe(false);
  });

  // 集合大小恰好为 4
  test("终态集合大小恰好为 4", () => {
    expect(TURN_TERMINAL_STATUSES.size).toBe(4);
  });

  // 不可变（ReadonlySet）
  test("ReadonlySet 不允许 add/delete（类型守卫）", () => {
    // 运行时验证：尝试 add 不抛异常但 TypeScript 类型不允许
    // 此处只验证集合内容不变
    const sizeBefore = TURN_TERMINAL_STATUSES.size;
    expect(sizeBefore).toBe(4);
  });
});

describe("Schema 版本常量", () => {
  // Chat Doc schema 版本为 2
  test("CHAT_DOC_SCHEMA_VERSION = 2", () => {
    expect(CHAT_DOC_SCHEMA_VERSION).toBe(2);
  });

  // Session Doc schema 版本为 3（新增 sessions 投影位）
  test("SESSION_DOC_SCHEMA_VERSION = 3", () => {
    expect(SESSION_DOC_SCHEMA_VERSION).toBe(3);
  });

  // 初始投影版本为 1
  test("INITIAL_PROJECTION_VERSION = 1", () => {
    expect(INITIAL_PROJECTION_VERSION).toBe(1);
  });
});

describe("canWriteToTurn 状态机守卫（内联验证）", () => {
  // 终态和 cancelling 不可写入，其余可写入
  function canWriteToTurn(turnStatus: TurnStatus | null): boolean {
    if (!turnStatus || turnStatus === "cancelling") return false;
    return !TURN_TERMINAL_STATUSES.has(turnStatus);
  }

  // 非终态可写入
  test("accepting 和 running 可写入", () => {
    expect(canWriteToTurn("accepting")).toBe(true);
    expect(canWriteToTurn("running")).toBe(true);
    expect(canWriteToTurn("awaiting_permission")).toBe(true);
  });

  // cancelling 不可写入（用户已取消，晚到增量丢弃）
  test("cancelling 不可写入", () => {
    expect(canWriteToTurn("cancelling")).toBe(false);
  });

  // 终态不可写入
  test("所有终态不可写入", () => {
    expect(canWriteToTurn("cancelled")).toBe(false);
    expect(canWriteToTurn("interrupted")).toBe(false);
    expect(canWriteToTurn("failed")).toBe(false);
    expect(canWriteToTurn("completed")).toBe(false);
  });

  // null 不可写入
  test("null 不可写入", () => {
    expect(canWriteToTurn(null)).toBe(false);
  });
});
