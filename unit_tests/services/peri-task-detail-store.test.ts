// peri-task-detail-store.test.ts — Peri 任务详情 Y.Doc 读取层测试
// 测试目标：createPeriTaskDetailStore.get 的 Y.Doc → 记录映射
// 业务意图：确保从 Y.Doc map 中正确投影 kind/availability/summary 字段
//
// 注意：@fenix/chat-channel/server 的 getPeriTasksMap 在 preload 下不易 mock.module 覆盖，
// 因此本测试提供一个最小 Y.Doc-like 替身，让真实 getPeriTasksMap 通过嵌套 getMap/get 调用
// 走到我们控制的数据层，从而测试 store 的字段投影逻辑。

import { describe, expect, test, beforeEach, mock } from "bun:test";

import { createPeriTaskDetailStore } from "@fenix/services/peri-task-detail-store";

// ── Y.Doc 替身（最小接口，让真实 getPeriTasksMap 走通） ──

interface TaskFields {
  kind?: string;
  detailAvailability?: string;
  summary?: unknown;
}

function makeYMap<T = unknown>(entries: Record<string, T>): { get: (key: string) => T | undefined } {
  return {
    get: (key: string) => entries[key],
  };
}

function makeYDoc(tasks: Record<string, TaskFields>): { getMap: (name: string) => any } {
  const taskMaps: Record<string, any> = {};
  for (const [taskId, fields] of Object.entries(tasks)) {
    taskMaps[taskId] = makeYMap(fields);
  }
  const tasksMap = makeYMap(taskMaps);
  const rootMap = makeYMap({ tasks: tasksMap, sessions: makeYMap({}) });
  return {
    getMap: (_name: string) => rootMap,
  };
}

// ── DocManager 桩 ──

let currentYDoc: any = null;
const mockDocManager = {
  getSessionYdoc: mock((_rcsSessionId: string): unknown => currentYDoc),
};

describe("createPeriTaskDetailStore", () => {
  const store = createPeriTaskDetailStore(mockDocManager);

  beforeEach(() => {
    mock.restore();
    currentYDoc = null;
    mockDocManager.getSessionYdoc.mockImplementation(() => currentYDoc);
  });

  describe("get — 无数据场景", () => {
    test("无 Y.Doc 时返回 null", () => {
      currentYDoc = null;
      expect(store.get("rcs-session-1", "task-1")).toBeNull();
    });

    test("Y.Doc 中无对应 taskId 时返回 null", () => {
      currentYDoc = makeYDoc({});
      expect(store.get("rcs-session-1", "task-missing")).toBeNull();
    });
  });

  describe("get — kind 过滤", () => {
    test("kind=subagent + availability=preview 正常返回", () => {
      currentYDoc = makeYDoc({
        "task-1": { kind: "subagent", detailAvailability: "preview", summary: "some summary" },
      });

      const result = store.get("rcs-session-1", "task-1");
      expect(result).toEqual({
        taskId: "task-1",
        kind: "subagent",
        summary: "some summary",
        detailAvailability: "preview",
      });
    });

    test("kind=background + availability=preview 正常返回", () => {
      currentYDoc = makeYDoc({
        "task-bg": { kind: "background", detailAvailability: "preview", summary: "bg summary" },
      });

      const result = store.get("rcs-session-1", "task-bg");
      expect(result?.kind).toBe("background");
    });

    test("kind=main（非法）返回 null", () => {
      currentYDoc = makeYDoc({
        "task-main": { kind: "main", detailAvailability: "preview", summary: "main summary" },
      });

      expect(store.get("rcs-session-1", "task-main")).toBeNull();
    });

    test("kind 缺失返回 null", () => {
      currentYDoc = makeYDoc({
        "task-nk": { detailAvailability: "preview", summary: "s" },
      });

      expect(store.get("rcs-session-1", "task-nk")).toBeNull();
    });
  });

  describe("get — availability 过滤", () => {
    test("availability=unavailable 通过", () => {
      currentYDoc = makeYDoc({
        "task-ua": { kind: "subagent", detailAvailability: "unavailable", summary: null },
      });

      const result = store.get("rcs-session-1", "task-ua");
      expect(result?.detailAvailability).toBe("unavailable");
    });

    test("availability=expired 通过", () => {
      currentYDoc = makeYDoc({
        "task-exp": { kind: "subagent", detailAvailability: "expired", summary: null },
      });

      expect(store.get("rcs-session-1", "task-exp")?.detailAvailability).toBe("expired");
    });

    test("availability=full（非法）返回 null", () => {
      currentYDoc = makeYDoc({
        "task-full": { kind: "subagent", detailAvailability: "full", summary: "s" },
      });

      expect(store.get("rcs-session-1", "task-full")).toBeNull();
    });
  });

  describe("get — summary 处理", () => {
    test("非空字符串 summary 保留", () => {
      currentYDoc = makeYDoc({
        "task-s": { kind: "subagent", detailAvailability: "preview", summary: "hello world" },
      });

      expect(store.get("rcs-session-1", "task-s")?.summary).toBe("hello world");
    });

    test("空字符串 summary 归一化为 null", () => {
      currentYDoc = makeYDoc({
        "task-es": { kind: "subagent", detailAvailability: "preview", summary: "" },
      });

      expect(store.get("rcs-session-1", "task-es")?.summary).toBeNull();
    });

    test("null summary 保持 null", () => {
      currentYDoc = makeYDoc({
        "task-ns": { kind: "subagent", detailAvailability: "preview", summary: null },
      });

      expect(store.get("rcs-session-1", "task-ns")?.summary).toBeNull();
    });

    test("undefined summary 归一化为 null", () => {
      currentYDoc = makeYDoc({
        "task-us": { kind: "subagent", detailAvailability: "preview", summary: undefined },
      });

      expect(store.get("rcs-session-1", "task-us")?.summary).toBeNull();
    });

    test("数字类型 summary 归一化为 null（非字符串）", () => {
      currentYDoc = makeYDoc({
        "task-ns2": { kind: "subagent", detailAvailability: "preview", summary: 12345 as any },
      });

      expect(store.get("rcs-session-1", "task-ns2")?.summary).toBeNull();
    });
  });
});
