import { describe, expect, test } from "bun:test";
import { randomUUID } from "node:crypto";

// ── generateTaskId / generateLogId UUID 格式验证 ──
// R38 修复：ID 生成从 task_xxx 改为标准 UUID，兼容 PG uuid 列类型

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function generateTaskId(): string {
  return randomUUID();
}

function generateLogId(): string {
  return randomUUID();
}

describe("task/log ID generation: UUID format", () => {
  test("generateTaskId returns valid UUID", () => {
    const id = generateTaskId();
    expect(UUID_RE.test(id)).toBe(true);
  });

  test("generateLogId returns valid UUID", () => {
    const id = generateLogId();
    expect(UUID_RE.test(id)).toBe(true);
  });

  test("generates unique IDs across calls", () => {
    const ids = new Set<string>();
    for (let i = 0; i < 100; i++) {
      ids.add(generateTaskId());
      ids.add(generateLogId());
    }
    expect(ids.size).toBe(200);
  });

  test("no longer uses task_ or log_ prefix", () => {
    for (let i = 0; i < 20; i++) {
      expect(generateTaskId().startsWith("task_")).toBe(false);
      expect(generateLogId().startsWith("log_")).toBe(false);
    }
  });
});
