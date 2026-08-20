// scheduler-lock.test.ts — opensandbox-cluster 调度锁测试
// 测试目标：SchedulerLock 的 BEGIN/COMMIT/ROLLBACK 事务语义
// 业务意图：确保调度操作在 SQLite 事务中原子执行，失败时回滚

import { describe, test, expect } from "bun:test";

// ── 复制纯函数（来自 packages/opensandbox-cluster/src/services/scheduler-lock.ts）──

interface MockDatabase {
  execLog: string[];
  exec(sql: string): void;
}

function createMockDb(): MockDatabase {
  const execLog: string[] = [];
  return {
    execLog,
    exec(sql: string) {
      execLog.push(sql);
    },
  };
}

class SchedulerLock {
  constructor(private readonly sqlite: MockDatabase) {}

  run<T>(operation: () => T): T {
    this.sqlite.exec("BEGIN IMMEDIATE");
    try {
      const result = operation();
      this.sqlite.exec("COMMIT");
      return result;
    } catch (error) {
      this.sqlite.exec("ROLLBACK");
      throw error;
    }
  }
}

// ── 测试 ──

describe("SchedulerLock", () => {
  test("正向 - 操作成功执行 BEGIN→操作→COMMIT", () => {
    const db = createMockDb();
    const lock = new SchedulerLock(db);
    const result = lock.run(() => 42);
    expect(result).toBe(42);
    expect(db.execLog).toEqual(["BEGIN IMMEDIATE", "COMMIT"]);
  });

  test("正向 - 操作失败执行 BEGIN→操作→ROLLBACK", () => {
    const db = createMockDb();
    const lock = new SchedulerLock(db);
    expect(() => lock.run(() => { throw new Error("boom"); })).toThrow("boom");
    expect(db.execLog).toEqual(["BEGIN IMMEDIATE", "ROLLBACK"]);
  });

  test("正向 - 返回操作的返回值", () => {
    const db = createMockDb();
    const lock = new SchedulerLock(db);
    expect(lock.run(() => ({ id: "a", count: 3 }))).toEqual({ id: "a", count: 3 });
  });

  test("正向 - 返回 undefined 也正常提交", () => {
    const db = createMockDb();
    const lock = new SchedulerLock(db);
    expect(lock.run(() => undefined)).toBeUndefined();
    expect(db.execLog).toEqual(["BEGIN IMMEDIATE", "COMMIT"]);
  });

  test("分支 - 操作抛非 Error 类型也回滚", () => {
    const db = createMockDb();
    const lock = new SchedulerLock(db);
    expect(() => lock.run(() => { throw "string error"; })).toThrow("string error");
    expect(db.execLog).toEqual(["BEGIN IMMEDIATE", "ROLLBACK"]);
  });

  test("隔离 - 多次 run 独立事务", () => {
    const db = createMockDb();
    const lock = new SchedulerLock(db);
    lock.run(() => 1);
    lock.run(() => 2);
    expect(db.execLog).toEqual([
      "BEGIN IMMEDIATE", "COMMIT",
      "BEGIN IMMEDIATE", "COMMIT",
    ]);
  });

  test("隔离 - 连续失败不影响后续成功", () => {
    const db = createMockDb();
    const lock = new SchedulerLock(db);
    try { lock.run(() => { throw new Error("fail"); }); } catch { /* ignore */ }
    const result = lock.run(() => "ok");
    expect(result).toBe("ok");
    expect(db.execLog.length).toBe(4);
    expect(db.execLog[3]).toBe("COMMIT");
  });
});
