// peri-task-detail-service.test.ts — Peri 任务详情服务层测试
// 测试目标：getPeriTaskDetail 的 preview 构建 + unavailable 分支 + 错误处理
// 业务意图：确保任务详情接口正确投影 Y.Doc 摘要、按字节截断、处理过期/缺失场景

import { describe, expect, test, mock, beforeEach } from "bun:test";

// ── Mock chat-channel ──

mock.module("@fenix/chat-channel", () => ({
  createDeterministicRcsSessionId: (envId: string, userId: string, sessionId: string) =>
    `rcs_${envId}_${userId}_${sessionId}`,
}));

// ── Mock errors ──

class NotFoundError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NotFoundError";
  }
}

mock.module("@fenix/errors", () => ({
  NotFoundError,
}));

// ── 类型 ──

interface PeriTaskDetailRecord {
  taskId: string;
  kind: string;
  summary: string | null;
  detailAvailability: string;
}

interface PeriTaskDetailContext {
  organizationId: string;
  userId: string;
  environmentId: string;
  sessionId: string;
  taskId: string;
}

interface PeriTaskDetailQuery {
  byteLimit: number;
}

// ── 纯函数副本（truncateByUtf8Bytes） ──

const MAX_PREVIEW_CODE_POINTS = 500;

function truncateByUtf8Bytes(value: string, byteLimit: number): string {
  let bytes = 0;
  let output = "";
  for (const char of Array.from(value).slice(0, MAX_PREVIEW_CODE_POINTS)) {
    const size = new TextEncoder().encode(char).byteLength;
    if (bytes + size > byteLimit) break;
    bytes += size;
    output += char;
  }
  return output;
}

// ── 导入被测函数 ──

import { getPeriTaskDetail } from "@fenix/services/peri-task-detail-service";

// ── 测试辅助 ──

const baseContext: PeriTaskDetailContext = {
  organizationId: "org-1",
  userId: "user-1",
  environmentId: "env-1",
  sessionId: "session-1",
  taskId: "task-1",
};

function buildDeps(task: PeriTaskDetailRecord | null) {
  return {
    getOwnedEnvironment: mock(async () => ({})),
    store: {
      get: mock((_rcsSessionId: string, _taskId: string) => task),
    },
  };
}

describe("getPeriTaskDetail", () => {
  beforeEach(() => {
    mock.restore();
  });

  // ── 正常 preview 路径 ──

  test("preview 可用时返回截断后的文本内容", async () => {
    const deps = buildDeps({
      taskId: "task-1",
      kind: "subagent",
      summary: "Hello World 你好世界",
      detailAvailability: "preview",
    });

    const result = await getPeriTaskDetail(baseContext, { byteLimit: 1000 }, deps as any);
    expect(result.kind).toBe("preview");
    if (result.kind === "preview") {
      expect(result.taskId).toBe("task-1");
      expect(result.taskKind).toBe("subagent");
      expect(result.complete).toBe(false);
      expect(result.limitation).toBe("source_only_provides_preview");
      expect(result.nextCursor).toBeNull();
      expect(result.items[0].type).toBe("text");
      expect(result.items[0].content).toBe("Hello World 你好世界");
    }
  });

  // ── 权限校验 ──

  test("环境权限校验失败时抛出原始错误", async () => {
    const deps = {
      getOwnedEnvironment: mock(async () => {
        throw new Error("forbidden");
      }),
      store: {
        get: mock(() => null),
      },
    };

    await expect(getPeriTaskDetail(baseContext, { byteLimit: 100 }, deps as any)).rejects.toThrow(
      "forbidden",
    );
    expect(deps.store.get).not.toHaveBeenCalled();
  });

  // ── 任务不存在 ──

  test("任务不存在时抛出 NotFoundError", async () => {
    const deps = buildDeps(null);
    await expect(getPeriTaskDetail(baseContext, { byteLimit: 100 }, deps as any)).rejects.toThrow(
      NotFoundError,
    );
  });

  // ── detailAvailability 分支 ──

  test("detailAvailability=expired 返回 unavailable + reason=expired", async () => {
    const deps = buildDeps({
      taskId: "task-1",
      kind: "subagent",
      summary: "old summary",
      detailAvailability: "expired",
    });

    const result = await getPeriTaskDetail(baseContext, { byteLimit: 1000 }, deps as any);
    expect(result.kind).toBe("unavailable");
    if (result.kind === "unavailable") {
      expect(result.reason).toBe("expired");
      expect(result.taskId).toBe("task-1");
    }
  });

  test("detailAvailability=unavailable 返回 unavailable + reason=not_provided", async () => {
    const deps = buildDeps({
      taskId: "task-1",
      kind: "subagent",
      summary: "s",
      detailAvailability: "unavailable",
    });

    const result = await getPeriTaskDetail(baseContext, { byteLimit: 1000 }, deps as any);
    expect(result.kind).toBe("unavailable");
    if (result.kind === "unavailable") {
      expect(result.reason).toBe("not_provided");
    }
  });

  test("detailAvailability=preview 但 summary 为 null 返回 unavailable", async () => {
    const deps = buildDeps({
      taskId: "task-1",
      kind: "subagent",
      summary: null,
      detailAvailability: "preview",
    });

    const result = await getPeriTaskDetail(baseContext, { byteLimit: 1000 }, deps as any);
    expect(result.kind).toBe("unavailable");
    if (result.kind === "unavailable") {
      expect(result.reason).toBe("not_provided");
    }
  });

  // ── 字节截断 ──

  test("按字节限制截断 ASCII 内容", async () => {
    const deps = buildDeps({
      taskId: "task-1",
      kind: "subagent",
      summary: "abcdefghijklmnop",
      detailAvailability: "preview",
    });

    const result = await getPeriTaskDetail(baseContext, { byteLimit: 5 }, deps as any);
    if (result.kind === "preview") {
      expect(result.items[0].content).toBe("abcde");
    }
  });

  test("UTF-8 多字节字符按字节精确截断（不切断字符）", async () => {
    // 每个中文字符 3 字节，byteLimit=7 → 只能容纳 2 个字符（6 字节）
    const deps = buildDeps({
      taskId: "task-1",
      kind: "subagent",
      summary: "你好世界abc",
      detailAvailability: "preview",
    });

    const result = await getPeriTaskDetail(baseContext, { byteLimit: 7 }, deps as any);
    if (result.kind === "preview") {
      expect(result.items[0].content).toBe("你好");
    }
  });

  test("byteLimit=0 时截断为空 → 返回 unavailable", async () => {
    const deps = buildDeps({
      taskId: "task-1",
      kind: "subagent",
      summary: "some content",
      detailAvailability: "preview",
    });

    const result = await getPeriTaskDetail(baseContext, { byteLimit: 0 }, deps as any);
    expect(result.kind).toBe("unavailable");
    if (result.kind === "unavailable") {
      expect(result.reason).toBe("not_provided");
    }
  });

  test("空字符串 summary 即使 availability=preview 也返回 unavailable", async () => {
    const deps = buildDeps({
      taskId: "task-1",
      kind: "subagent",
      summary: "",
      detailAvailability: "preview",
    });

    const result = await getPeriTaskDetail(baseContext, { byteLimit: 1000 }, deps as any);
    expect(result.kind).toBe("unavailable");
  });

  // ── 纯函数副本测试：truncateByUtf8Bytes ──

  describe("truncateByUtf8Bytes（纯函数）", () => {
    test("ASCII 字符串按字节截断", () => {
      expect(truncateByUtf8Bytes("abcdef", 3)).toBe("abc");
    });

    test("UTF-8 中文字符不切断单个字符", () => {
      // 每个中文字 3 字节，limit=5 → 只能装 1 个（3 字节，再加 3 就超过 5）
      expect(truncateByUtf8Bytes("你好世界", 5)).toBe("你");
    });

    test("UTF-8 limit=6 可容纳 2 个中文字符", () => {
      expect(truncateByUtf8Bytes("你好世界", 6)).toBe("你好");
    });

    test("空字符串返回空", () => {
      expect(truncateByUtf8Bytes("", 10)).toBe("");
    });

    test("byteLimit=0 返回空", () => {
      expect(truncateByUtf8Bytes("abc", 0)).toBe("");
    });

    test("超出 MAX_PREVIEW_CODE_POINTS 的输入先切片再按字节截断", () => {
      // 600 个 ASCII 字符，先被 slice(0, 500)，然后按 byteLimit=100 截断
      const input = "a".repeat(600);
      expect(truncateByUtf8Bytes(input, 100)).toBe("a".repeat(100));
    });

    test("混合 ASCII 和 UTF-8 内容", () => {
      // "a好b" = 1+3+1=5 字节，limit=4 → "a好"（4 字节）
      expect(truncateByUtf8Bytes("a好b", 4)).toBe("a好");
    });
  });
});
