// session-mutation-projection.test.ts — 会话删除后投影清理测试
// 测试目标：SessionTitleState.project 的删除过滤、delete 不依赖持久化存储、
//           removeSessionSummary 按 ID 清理 sessions 投影
// 业务意图：Agent 已确认删除的会话不能被迟到的 session_list 复活，也不能残留 Fenix 标题

import { describe, expect, test } from "bun:test";

// ── 复制纯逻辑（packages/chat-channel/src/state/session-title-store.ts） ──

interface TitleState {
  deleted: Map<string, Set<string>>;
  confirmed: Map<string, Set<string>>;
  titles: Map<string, Map<string, string>>;
  revisions: Map<string, number>;
}

interface TitleStore {
  delete: (rcsSessionId: string, sessionId: string) => Promise<void>;
}

function createTitleState(): TitleState {
  return {
    deleted: new Map(),
    confirmed: new Map(),
    titles: new Map(),
    revisions: new Map(),
  };
}

/** 复制 SessionTitleState.delete：先标记删除，再清理（可选）持久化标题。 */
async function deleteTitle(
  state: TitleState,
  store: TitleStore | undefined,
  rcsSessionId: string,
  sessionId: string,
): Promise<void> {
  let deleted = state.deleted.get(rcsSessionId);
  if (!deleted) {
    deleted = new Set();
    state.deleted.set(rcsSessionId, deleted);
  }
  deleted.add(sessionId);
  state.confirmed.get(rcsSessionId)?.delete(sessionId);
  state.titles.get(rcsSessionId)?.delete(sessionId);
  state.revisions.set(rcsSessionId, (state.revisions.get(rcsSessionId) ?? 0) + 1);
  await store?.delete(rcsSessionId, sessionId);
}

/** 复制 SessionTitleState.project 的 session_list 分支。 */
function projectSessionList(
  state: TitleState,
  rcsSessionId: string,
  sessions: unknown[],
): { sessions: unknown[]; confirmed: Set<string> } {
  const confirmed = new Set<string>();
  const projected = sessions
    .filter((entry) => {
      if (!entry || typeof entry !== "object") return true;
      const sessionId = (entry as Record<string, unknown>).sessionId;
      return typeof sessionId !== "string" || !state.deleted.get(rcsSessionId)?.has(sessionId);
    })
    .map((entry) => {
      if (!entry || typeof entry !== "object" || Array.isArray(entry)) return entry;
      const record = entry as Record<string, unknown>;
      const sessionId = record.sessionId;
      if (typeof sessionId !== "string") return entry;
      confirmed.add(sessionId);
      const title = state.titles.get(rcsSessionId)?.get(sessionId);
      return title === undefined ? entry : { ...record, title };
    });
  state.confirmed.set(rcsSessionId, confirmed);
  return { sessions: projected, confirmed };
}

// ── 复制纯逻辑（packages/chat-channel/src/state/session-list.ts） ──

/** 复制 removeSessionSummary：按 ID 清理投影并返回是否实际删除。 */
function removeSessionSummary(sessions: Map<string, unknown> | undefined, sessionId: string): boolean {
  if (!sessions) return false;
  if (!sessions.has(sessionId)) return false;
  sessions.delete(sessionId);
  return true;
}

// ── 测试 ──

const RCS = "rcs_session-1";

describe("SessionTitleState.delete 删除回执", () => {
  test("没有持久化存储时仍记录删除并推进修订号", async () => {
    const state = createTitleState();
    await deleteTitle(state, undefined, RCS, "s-1");
    expect(state.deleted.get(RCS)?.has("s-1")).toBe(true);
    expect(state.revisions.get(RCS)).toBe(1);
  });

  test("有持久化存储时先标记删除再调用 store.delete", async () => {
    const state = createTitleState();
    state.deleted.set(RCS, new Set());
    state.confirmed.set(RCS, new Set(["s-1"]));
    state.titles.set(RCS, new Map([["s-1", "旧标题"]]));
    const calls: Array<[string, string]> = [];
    const store: TitleStore = {
      delete: async (rcs, sid) => {
        // store 调用时内存已标记删除
        expect(state.deleted.get(RCS)?.has(sid)).toBe(true);
        calls.push([rcs, sid]);
      },
    };

    await deleteTitle(state, store, RCS, "s-1");

    expect(calls).toEqual([[RCS, "s-1"]]);
    expect(state.confirmed.get(RCS)?.has("s-1")).toBe(false);
    expect(state.titles.get(RCS)?.has("s-1")).toBe(false);
  });

  test("存储删除失败时内存状态已更新（不会因存储异常复活）", async () => {
    const state = createTitleState();
    const store: TitleStore = { delete: async () => { throw new Error("store unavailable"); } };
    await expect(deleteTitle(state, store, RCS, "s-1")).rejects.toThrow("store unavailable");
    expect(state.deleted.get(RCS)?.has("s-1")).toBe(true);
    expect(state.revisions.get(RCS)).toBe(1);
  });
});

describe("SessionTitleState.project 迟到的 session_list", () => {
  test("已确认删除的会话被过滤，迟到的列表无法复活", async () => {
    const state = createTitleState();
    await deleteTitle(state, undefined, RCS, "s-deleted");

    const { sessions, confirmed } = projectSessionList(state, RCS, [
      { sessionId: "s-deleted", title: "服务端旧标题" },
      { sessionId: "s-alive" },
    ]);

    expect(sessions).toEqual([{ sessionId: "s-alive" }]);
    expect(confirmed.has("s-deleted")).toBe(false);
    expect(confirmed.has("s-alive")).toBe(true);
  });

  test("全部会话都已删除时投影为空", async () => {
    const state = createTitleState();
    await deleteTitle(state, undefined, RCS, "s-1");
    await deleteTitle(state, undefined, RCS, "s-2");

    const { sessions, confirmed } = projectSessionList(state, RCS, [
      { sessionId: "s-1" },
      { sessionId: "s-2" },
    ]);

    expect(sessions).toEqual([]);
    expect(confirmed.size).toBe(0);
  });

  test("未删除会话保留 Fenix 标题覆盖服务端值", () => {
    const state = createTitleState();
    state.titles.set(RCS, new Map([["s-1", "Fenix 标题"]]));

    const { sessions } = projectSessionList(state, RCS, [
      { sessionId: "s-1", title: "服务端标题" },
      { sessionId: "s-2", title: "服务端标题 2" },
    ]);

    expect(sessions).toEqual([
      { sessionId: "s-1", title: "Fenix 标题" },
      { sessionId: "s-2", title: "服务端标题 2" },
    ]);
  });

  test("缺少 sessionId 的条目原样保留且不计入 confirmed", () => {
    const state = createTitleState();
    const { sessions, confirmed } = projectSessionList(state, RCS, [
      { title: "无 ID" },
      null,
      "not-an-object",
      { sessionId: 42 },
    ]);
    expect(sessions).toEqual([{ title: "无 ID" }, null, "not-an-object", { sessionId: 42 }]);
    expect(confirmed.size).toBe(0);
  });

  test("删除只影响对应 rcsSessionId 的会话", async () => {
    const state = createTitleState();
    await deleteTitle(state, undefined, RCS, "s-1");
    const { sessions } = projectSessionList(state, "rcs_session-2", [{ sessionId: "s-1" }]);
    expect(sessions).toEqual([{ sessionId: "s-1" }]);
  });
});

describe("removeSessionSummary 投影清理", () => {
  test("命中时删除并返回 true", () => {
    const sessions = new Map<string, unknown>([
      ["s-1", { id: "s-1" }],
      ["s-2", { id: "s-2" }],
    ]);
    expect(removeSessionSummary(sessions, "s-1")).toBe(true);
    expect(sessions.has("s-1")).toBe(false);
    expect(sessions.get("s-2")).toEqual({ id: "s-2" });
    expect(sessions.size).toBe(1);
  });

  test("不存在时返回 false 且不改变投影", () => {
    const sessions = new Map<string, unknown>([["s-1", { id: "s-1" }]]);
    expect(removeSessionSummary(sessions, "missing")).toBe(false);
    expect(sessions.size).toBe(1);
  });

  test("文档未打开时安全返回 false", () => {
    expect(removeSessionSummary(undefined, "s-1")).toBe(false);
  });

  test("不存在的 sessionId 不误删其他条目", () => {
    const sessions = new Map<string, unknown>([["", { id: "" }], ["s-1", { id: "s-1" }]]);
    expect(removeSessionSummary(sessions, "s-9")).toBe(false);
    expect(sessions.has("")).toBe(true);
  });
});
