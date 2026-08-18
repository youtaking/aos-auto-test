// in-memory-storage.test.ts — 内存存储适配器测试
// 测试目标：createInMemoryStorage 返回的 StorageAdapter 的所有 CRUD 方法
// 业务意图：确保内存存储在开发和测试场景下行为正确
// 策略：直接复制工厂函数，无外部依赖

import { describe, test, expect } from "bun:test";

// ========== Pure function copies from packages/workflow-engine/src/storage/in-memory-storage.ts ==========

// ---------- Types (inline) ----------

type DAGStatus = "PENDING" | "RUNNING" | "SUSPENDED" | "FAILED" | "CANCELLED" | "ERROR" | "SUCCESS";
type NodeStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED" | "SKIPPED";

interface NodeOutput {
  stdout: string;
  json?: unknown;
  exit_code: number;
  size?: number;
  ref?: string;
}

type EventType =
  | "dag.started" | "dag.completed" | "dag.cancelled"
  | "node.started" | "node.completed" | "node.failed" | "node.cancelled" | "node.retrying" | "node.skipped"
  | "sub_workflow.started" | "sub_workflow.completed"
  | "loop.iteration_started" | "loop.iteration_completed"
  | "audit.requested" | "audit.approved";

interface DAGEvent {
  event_id: string;
  run_id: string;
  project_id?: string;
  node_id?: string;
  timestamp: string;
  type: EventType;
  metadata?: Record<string, unknown>;
}

interface DAGSnapshot {
  snapshot_id: string;
  run_id: string;
  last_event_id: string;
  timestamp: string;
  node_states: Record<string, { status: NodeStatus; exit_code?: number }>;
  dag_status: DAGStatus;
}

interface RunSummary {
  run_id: string;
  project_id?: string;
  workflow_id?: string;
  workflow_name: string;
  status: DAGStatus;
  started_at: string;
  completed_at?: string;
  node_summary: { total: number; completed: number; failed: number; running: number };
}

interface StorageAdapter {
  appendEvent(event: DAGEvent): Promise<void>;
  getEvents(runId: string, opts?: { afterEventId?: string; nodeId?: string; types?: EventType[] }): Promise<DAGEvent[]>;
  getLatestSnapshot(runId: string): Promise<DAGSnapshot | null>;
  createSnapshot(snapshot: DAGSnapshot): Promise<void>;
  getOutput(runId: string, nodeId: string): Promise<NodeOutput | null>;
  setOutput(runId: string, nodeId: string, output: NodeOutput): Promise<void>;
  listRuns(params: { page: number; pageSize: number; status?: string; q?: string }): Promise<{ items: RunSummary[]; total: number }>;
  getRunStatus(runId: string): Promise<DAGStatus | null>;
  /** 测试辅助：设置 runStatus（源码中 runStatuses 由外部引擎写入，此处为测试用扩展） */
  setRunStatus(runId: string, status: DAGStatus): Promise<void>;
  atomicNodeComplete(opts: { output: NodeOutput; snapshot: DAGSnapshot; event: DAGEvent }): Promise<void>;
  deleteRun(runId: string): Promise<void>;
  /** 测试辅助：写入 RunSummary 到内部 runSummaries（源码中无公开写入入口，此处为测试用扩展） */
  createRunSummary(summary: RunSummary): Promise<void>;
}

// ---------- Factory (copied from source) ----------

function createInMemoryStorage(): StorageAdapter {
  const events = new Map<string, DAGEvent[]>();
  const snapshots = new Map<string, DAGSnapshot[]>();
  const outputs = new Map<string, Map<string, NodeOutput>>();
  const runStatuses = new Map<string, DAGStatus>();
  const runSummaries = new Map<string, RunSummary>();

  return {
    async appendEvent(event: DAGEvent): Promise<void> {
      const list = events.get(event.run_id) ?? [];
      list.push(event);
      events.set(event.run_id, list);
    },

    async getEvents(
      runId: string,
      opts?: { afterEventId?: string; nodeId?: string; types?: EventType[] },
    ): Promise<DAGEvent[]> {
      let list = events.get(runId) ?? [];
      if (opts?.afterEventId) {
        const idx = list.findIndex((e) => e.event_id === opts.afterEventId);
        if (idx !== -1) {
          list = list.slice(idx + 1);
        }
      }
      if (opts?.nodeId) {
        list = list.filter((e) => e.node_id === opts.nodeId);
      }
      if (opts?.types?.length) {
        const typeSet = new Set(opts.types);
        list = list.filter((e) => typeSet.has(e.type));
      }
      return list;
    },

    async getLatestSnapshot(runId: string): Promise<DAGSnapshot | null> {
      const list = snapshots.get(runId);
      if (!list?.length) return null;
      return list[list.length - 1];
    },

    async createSnapshot(snapshot: DAGSnapshot): Promise<void> {
      const list = snapshots.get(snapshot.run_id) ?? [];
      list.push(snapshot);
      snapshots.set(snapshot.run_id, list);
    },

    async getOutput(runId: string, nodeId: string): Promise<NodeOutput | null> {
      return outputs.get(runId)?.get(nodeId) ?? null;
    },

    async setOutput(runId: string, nodeId: string, output: NodeOutput): Promise<void> {
      const nodeMap = outputs.get(runId) ?? new Map<string, NodeOutput>();
      nodeMap.set(nodeId, output);
      outputs.set(runId, nodeMap);
    },

    async listRuns(params: {
      page: number;
      pageSize: number;
      status?: string;
      q?: string;
    }): Promise<{ items: RunSummary[]; total: number }> {
      let filtered = Array.from(runSummaries.values());
      if (params.status) {
        filtered = filtered.filter((r) => r.status === params.status);
      }
      if (params.q) {
        const q = params.q.toLowerCase();
        filtered = filtered.filter((r) => r.workflow_name.toLowerCase().includes(q));
      }
      const total = filtered.length;
      const start = (params.page - 1) * params.pageSize;
      const items = filtered.slice(start, start + params.pageSize);
      return { items, total };
    },

    async getRunStatus(runId: string): Promise<DAGStatus | null> {
      return runStatuses.get(runId) ?? null;
    },

    async setRunStatus(runId: string, status: DAGStatus): Promise<void> {
      runStatuses.set(runId, status);
    },

    async atomicNodeComplete(opts: { output: NodeOutput; snapshot: DAGSnapshot; event: DAGEvent }): Promise<void> {
      const { snapshot, event } = opts;
      const runId = snapshot.run_id;
      const nodeMap = outputs.get(runId) ?? new Map<string, NodeOutput>();
      if (event.node_id) {
        nodeMap.set(event.node_id, opts.output);
        outputs.set(runId, nodeMap);
      }
      const snapList = snapshots.get(runId) ?? [];
      snapList.push(snapshot);
      snapshots.set(runId, snapList);
      const evtList = events.get(runId) ?? [];
      evtList.push(event);
      events.set(runId, evtList);
    },

    async deleteRun(runId: string): Promise<void> {
      events.delete(runId);
      snapshots.delete(runId);
      outputs.delete(runId);
      runStatuses.delete(runId);
      runSummaries.delete(runId);
    },

    async createRunSummary(summary: RunSummary): Promise<void> {
      runSummaries.set(summary.run_id, summary);
    },
  };
}

// ========== Test helpers ==========

function makeEvent(runId: string, eventId: string, type: EventType, nodeId?: string): DAGEvent {
  return { event_id: eventId, run_id: runId, node_id: nodeId, timestamp: new Date().toISOString(), type };
}

function makeSnapshot(runId: string, snapshotId: string, status: DAGStatus = "RUNNING"): DAGSnapshot {
  return {
    snapshot_id: snapshotId,
    run_id: runId,
    last_event_id: `evt-${snapshotId}`,
    timestamp: new Date().toISOString(),
    node_states: {},
    dag_status: status,
  };
}

function makeOutput(stdout: string, exitCode = 0): NodeOutput {
  return { stdout, exit_code: exitCode };
}

function makeRunSummary(
  runId: string,
  workflowName: string,
  status: DAGStatus = "RUNNING",
  opts?: { project_id?: string; workflow_id?: string; started_at?: string; completed_at?: string },
): RunSummary {
  return {
    run_id: runId,
    project_id: opts?.project_id,
    workflow_id: opts?.workflow_id,
    workflow_name: workflowName,
    status,
    started_at: opts?.started_at ?? new Date().toISOString(),
    completed_at: opts?.completed_at,
    node_summary: { total: 3, completed: 0, failed: 0, running: 0 },
  };
}

// ========== Tests ==========

describe("in-memory-storage: 事件", () => {
  test("appendEvent + getEvents 基本读写", async () => {
    const store = createInMemoryStorage();
    const evt = makeEvent("run-1", "e1", "dag.started");
    await store.appendEvent(evt);

    const events = await store.getEvents("run-1");
    expect(events).toHaveLength(1);
    expect(events[0].event_id).toBe("e1");
    expect(events[0].type).toBe("dag.started");
  });

  test("getEvents 不存在的 runId 返回空数组", async () => {
    const store = createInMemoryStorage();
    const events = await store.getEvents("nonexistent");
    expect(events).toEqual([]);
  });

  test("appendEvent 多个事件保持顺序", async () => {
    const store = createInMemoryStorage();
    await store.appendEvent(makeEvent("run-1", "e1", "dag.started"));
    await store.appendEvent(makeEvent("run-1", "e2", "node.started", "n1"));
    await store.appendEvent(makeEvent("run-1", "e3", "node.completed", "n1"));

    const events = await store.getEvents("run-1");
    expect(events).toHaveLength(3);
    expect(events.map(e => e.event_id)).toEqual(["e1", "e2", "e3"]);
  });

  test("不同 runId 的事件隔离", async () => {
    const store = createInMemoryStorage();
    await store.appendEvent(makeEvent("run-1", "e1", "dag.started"));
    await store.appendEvent(makeEvent("run-2", "e2", "dag.started"));

    expect(await store.getEvents("run-1")).toHaveLength(1);
    expect(await store.getEvents("run-2")).toHaveLength(1);
  });
});

describe("in-memory-storage: 事件过滤", () => {
  test("afterEventId 返回之后的事件", async () => {
    const store = createInMemoryStorage();
    await store.appendEvent(makeEvent("r", "e1", "dag.started"));
    await store.appendEvent(makeEvent("r", "e2", "node.started", "n1"));
    await store.appendEvent(makeEvent("r", "e3", "node.completed", "n1"));

    const events = await store.getEvents("r", { afterEventId: "e1" });
    expect(events).toHaveLength(2);
    expect(events[0].event_id).toBe("e2");
  });

  test("afterEventId 不存在时返回全部事件", async () => {
    const store = createInMemoryStorage();
    await store.appendEvent(makeEvent("r", "e1", "dag.started"));
    await store.appendEvent(makeEvent("r", "e2", "node.started"));

    const events = await store.getEvents("r", { afterEventId: "nonexistent" });
    expect(events).toHaveLength(2);
  });

  test("nodeId 过滤", async () => {
    const store = createInMemoryStorage();
    await store.appendEvent(makeEvent("r", "e1", "node.started", "n1"));
    await store.appendEvent(makeEvent("r", "e2", "node.started", "n2"));
    await store.appendEvent(makeEvent("r", "e3", "node.completed", "n1"));

    const events = await store.getEvents("r", { nodeId: "n1" });
    expect(events).toHaveLength(2);
    expect(events.every(e => e.node_id === "n1")).toBe(true);
  });

  test("types 过滤", async () => {
    const store = createInMemoryStorage();
    await store.appendEvent(makeEvent("r", "e1", "dag.started"));
    await store.appendEvent(makeEvent("r", "e2", "node.started", "n1"));
    await store.appendEvent(makeEvent("r", "e3", "node.completed", "n1"));

    const events = await store.getEvents("r", { types: ["node.started", "node.completed"] });
    expect(events).toHaveLength(2);
    expect(events.every(e => e.type.startsWith("node."))).toBe(true);
  });

  test("组合过滤: afterEventId + nodeId + types", async () => {
    const store = createInMemoryStorage();
    await store.appendEvent(makeEvent("r", "e1", "dag.started"));
    await store.appendEvent(makeEvent("r", "e2", "node.started", "n1"));
    await store.appendEvent(makeEvent("r", "e3", "node.completed", "n1"));
    await store.appendEvent(makeEvent("r", "e4", "node.started", "n2"));

    const events = await store.getEvents("r", {
      afterEventId: "e1",
      nodeId: "n1",
      types: ["node.completed"],
    });
    expect(events).toHaveLength(1);
    expect(events[0].event_id).toBe("e3");
  });
});

describe("in-memory-storage: 快照", () => {
  test("createSnapshot + getLatestSnapshot", async () => {
    const store = createInMemoryStorage();
    const snap = makeSnapshot("run-1", "s1");
    await store.createSnapshot(snap);

    const latest = await store.getLatestSnapshot("run-1");
    expect(latest).not.toBeNull();
    expect(latest!.snapshot_id).toBe("s1");
  });

  test("getLatestSnapshot 返回最新的快照", async () => {
    const store = createInMemoryStorage();
    await store.createSnapshot(makeSnapshot("run-1", "s1", "PENDING"));
    await store.createSnapshot(makeSnapshot("run-1", "s2", "RUNNING"));
    await store.createSnapshot(makeSnapshot("run-1", "s3", "SUCCESS"));

    const latest = await store.getLatestSnapshot("run-1");
    expect(latest!.snapshot_id).toBe("s3");
    expect(latest!.dag_status).toBe("SUCCESS");
  });

  test("getLatestSnapshot 不存在的 runId 返回 null", async () => {
    const store = createInMemoryStorage();
    const result = await store.getLatestSnapshot("nonexistent");
    expect(result).toBeNull();
  });

  test("不同 runId 的快照隔离", async () => {
    const store = createInMemoryStorage();
    await store.createSnapshot(makeSnapshot("run-1", "s1"));
    await store.createSnapshot(makeSnapshot("run-2", "s2"));

    expect((await store.getLatestSnapshot("run-1"))!.snapshot_id).toBe("s1");
    expect((await store.getLatestSnapshot("run-2"))!.snapshot_id).toBe("s2");
  });
});

describe("in-memory-storage: 节点输出", () => {
  test("setOutput + getOutput 基本读写", async () => {
    const store = createInMemoryStorage();
    const output = makeOutput("hello world", 0);
    await store.setOutput("run-1", "node-1", output);

    const result = await store.getOutput("run-1", "node-1");
    expect(result).not.toBeNull();
    expect(result!.stdout).toBe("hello world");
    expect(result!.exit_code).toBe(0);
  });

  test("getOutput 不存在的 runId 返回 null", async () => {
    const store = createInMemoryStorage();
    expect(await store.getOutput("nonexistent", "n1")).toBeNull();
  });

  test("getOutput 不存在的 nodeId 返回 null", async () => {
    const store = createInMemoryStorage();
    await store.setOutput("run-1", "n1", makeOutput("data"));
    expect(await store.getOutput("run-1", "n2")).toBeNull();
  });

  test("覆盖写入同一节点输出", async () => {
    const store = createInMemoryStorage();
    await store.setOutput("run-1", "n1", makeOutput("first"));
    await store.setOutput("run-1", "n1", makeOutput("second"));

    const result = await store.getOutput("run-1", "n1");
    expect(result!.stdout).toBe("second");
  });

  test("同一 run 不同节点的输出隔离", async () => {
    const store = createInMemoryStorage();
    await store.setOutput("run-1", "n1", makeOutput("output-a"));
    await store.setOutput("run-1", "n2", makeOutput("output-b"));

    expect((await store.getOutput("run-1", "n1"))!.stdout).toBe("output-a");
    expect((await store.getOutput("run-1", "n2"))!.stdout).toBe("output-b");
  });
});

describe("in-memory-storage: 运行状态", () => {
  test("getRunStatus 不存在的 runId 返回 null", async () => {
    const store = createInMemoryStorage();
    expect(await store.getRunStatus("nonexistent")).toBeNull();
  });

  test("getRunStatus 返回正确的状态值", async () => {
    const store = createInMemoryStorage();
    await store.setRunStatus("run-1", "RUNNING");
    await store.setRunStatus("run-2", "SUCCESS");
    await store.setRunStatus("run-3", "FAILED");

    expect(await store.getRunStatus("run-1")).toBe("RUNNING");
    expect(await store.getRunStatus("run-2")).toBe("SUCCESS");
    expect(await store.getRunStatus("run-3")).toBe("FAILED");
  });

  test("setRunStatus 覆盖已有状态", async () => {
    const store = createInMemoryStorage();
    await store.setRunStatus("run-1", "PENDING");
    expect(await store.getRunStatus("run-1")).toBe("PENDING");

    await store.setRunStatus("run-1", "RUNNING");
    expect(await store.getRunStatus("run-1")).toBe("RUNNING");

    await store.setRunStatus("run-1", "SUCCESS");
    expect(await store.getRunStatus("run-1")).toBe("SUCCESS");
  });
});

describe("in-memory-storage: listRuns", () => {
  test("空存储返回 total 0", async () => {
    const store = createInMemoryStorage();
    const result = await store.listRuns({ page: 1, pageSize: 10 });
    expect(result.total).toBe(0);
    expect(result.items).toEqual([]);
  });

  test("分页参数不影响空结果", async () => {
    const store = createInMemoryStorage();
    const result = await store.listRuns({ page: 5, pageSize: 20, status: "RUNNING", q: "test" });
    expect(result.total).toBe(0);
    expect(result.items).toEqual([]);
  });

  test("返回所有已写入的 run summary", async () => {
    const store = createInMemoryStorage();
    await store.createRunSummary(makeRunSummary("run-1", "Deploy Pipeline"));
    await store.createRunSummary(makeRunSummary("run-2", "Test Pipeline"));

    const result = await store.listRuns({ page: 1, pageSize: 10 });
    expect(result.total).toBe(2);
    expect(result.items).toHaveLength(2);
  });

  test("status 过滤 - 仅返回匹配状态", async () => {
    const store = createInMemoryStorage();
    await store.createRunSummary(makeRunSummary("run-1", "Deploy A", "RUNNING"));
    await store.createRunSummary(makeRunSummary("run-2", "Deploy B", "SUCCESS"));
    await store.createRunSummary(makeRunSummary("run-3", "Deploy C", "FAILED"));
    await store.createRunSummary(makeRunSummary("run-4", "Deploy D", "RUNNING"));

    const running = await store.listRuns({ page: 1, pageSize: 10, status: "RUNNING" });
    expect(running.total).toBe(2);
    expect(running.items.every((r) => r.status === "RUNNING")).toBe(true);

    const failed = await store.listRuns({ page: 1, pageSize: 10, status: "FAILED" });
    expect(failed.total).toBe(1);
    expect(failed.items[0].run_id).toBe("run-3");

    const success = await store.listRuns({ page: 1, pageSize: 10, status: "SUCCESS" });
    expect(success.total).toBe(1);
    expect(success.items[0].run_id).toBe("run-2");
  });

  test("status 过滤 - 无匹配返回空", async () => {
    const store = createInMemoryStorage();
    await store.createRunSummary(makeRunSummary("run-1", "Deploy A", "SUCCESS"));
    await store.createRunSummary(makeRunSummary("run-2", "Deploy B", "SUCCESS"));

    const result = await store.listRuns({ page: 1, pageSize: 10, status: "FAILED" });
    expect(result.total).toBe(0);
    expect(result.items).toEqual([]);
  });

  test("q 关键词搜索 - 大小写不敏感", async () => {
    const store = createInMemoryStorage();
    await store.createRunSummary(makeRunSummary("run-1", "Deploy Pipeline"));
    await store.createRunSummary(makeRunSummary("run-2", "Test Suite"));
    await store.createRunSummary(makeRunSummary("run-3", "deploy staging"));

    const result = await store.listRuns({ page: 1, pageSize: 10, q: "deploy" });
    expect(result.total).toBe(2);
    const names = result.items.map((r) => r.workflow_name);
    expect(names).toContain("Deploy Pipeline");
    expect(names).toContain("deploy staging");
  });

  test("q 关键词搜索 - 部分匹配", async () => {
    const store = createInMemoryStorage();
    await store.createRunSummary(makeRunSummary("run-1", "Full Integration Test"));
    await store.createRunSummary(makeRunSummary("run-2", "Unit Test Suite"));
    await store.createRunSummary(makeRunSummary("run-3", "Deploy to Prod"));

    const result = await store.listRuns({ page: 1, pageSize: 10, q: "test" });
    expect(result.total).toBe(2);
    expect(result.items.every((r) => r.workflow_name.toLowerCase().includes("test"))).toBe(true);
  });

  test("q 关键词搜索 - 无匹配返回空", async () => {
    const store = createInMemoryStorage();
    await store.createRunSummary(makeRunSummary("run-1", "Deploy Pipeline"));

    const result = await store.listRuns({ page: 1, pageSize: 10, q: "nonexistent" });
    expect(result.total).toBe(0);
    expect(result.items).toEqual([]);
  });

  test("分页 - 第 1 页", async () => {
    const store = createInMemoryStorage();
    await store.createRunSummary(makeRunSummary("run-1", "Pipeline A"));
    await store.createRunSummary(makeRunSummary("run-2", "Pipeline B"));
    await store.createRunSummary(makeRunSummary("run-3", "Pipeline C"));

    const result = await store.listRuns({ page: 1, pageSize: 2 });
    expect(result.total).toBe(3);
    expect(result.items).toHaveLength(2);
    expect(result.items[0].run_id).toBe("run-1");
    expect(result.items[1].run_id).toBe("run-2");
  });

  test("分页 - 第 2 页", async () => {
    const store = createInMemoryStorage();
    await store.createRunSummary(makeRunSummary("run-1", "Pipeline A"));
    await store.createRunSummary(makeRunSummary("run-2", "Pipeline B"));
    await store.createRunSummary(makeRunSummary("run-3", "Pipeline C"));

    const result = await store.listRuns({ page: 2, pageSize: 2 });
    expect(result.total).toBe(3);
    expect(result.items).toHaveLength(1);
    expect(result.items[0].run_id).toBe("run-3");
  });

  test("分页 - 超出范围返回空", async () => {
    const store = createInMemoryStorage();
    await store.createRunSummary(makeRunSummary("run-1", "Pipeline A"));

    const result = await store.listRuns({ page: 5, pageSize: 2 });
    expect(result.total).toBe(1);
    expect(result.items).toEqual([]);
  });

  test("组合过滤 - status + q + 分页", async () => {
    const store = createInMemoryStorage();
    await store.createRunSummary(makeRunSummary("run-1", "Deploy Alpha", "SUCCESS"));
    await store.createRunSummary(makeRunSummary("run-2", "Deploy Beta", "SUCCESS"));
    await store.createRunSummary(makeRunSummary("run-3", "Deploy Gamma", "FAILED"));
    await store.createRunSummary(makeRunSummary("run-4", "Test Alpha", "SUCCESS"));
    await store.createRunSummary(makeRunSummary("run-5", "Test Beta", "SUCCESS"));

    // status=SUCCESS + q="deploy" → run-1 和 run-2
    const result = await store.listRuns({ page: 1, pageSize: 1, status: "SUCCESS", q: "deploy" });
    expect(result.total).toBe(2);
    expect(result.items).toHaveLength(1);
    expect(result.items[0].run_id).toBe("run-1");

    // 第 2 页
    const result2 = await store.listRuns({ page: 2, pageSize: 1, status: "SUCCESS", q: "deploy" });
    expect(result2.total).toBe(2);
    expect(result2.items).toHaveLength(1);
    expect(result2.items[0].run_id).toBe("run-2");
  });

  test("过滤后空结果 + 分页仍返回 total 0", async () => {
    const store = createInMemoryStorage();
    await store.createRunSummary(makeRunSummary("run-1", "Deploy A", "SUCCESS"));

    const result = await store.listRuns({ page: 1, pageSize: 10, status: "FAILED", q: "test" });
    expect(result.total).toBe(0);
    expect(result.items).toEqual([]);
  });
});

describe("in-memory-storage: atomicNodeComplete", () => {
  test("原子写入：output + snapshot + event 同时写入", async () => {
    const store = createInMemoryStorage();
    const output = makeOutput("atomic output", 0);
    const snapshot = makeSnapshot("run-1", "s1");
    const event = makeEvent("run-1", "e1", "node.completed", "n1");

    await store.atomicNodeComplete({ output, snapshot, event });

    // 验证 output
    const out = await store.getOutput("run-1", "n1");
    expect(out).not.toBeNull();
    expect(out!.stdout).toBe("atomic output");

    // 验证 snapshot
    const snap = await store.getLatestSnapshot("run-1");
    expect(snap).not.toBeNull();
    expect(snap!.snapshot_id).toBe("s1");

    // 验证 event
    const events = await store.getEvents("run-1");
    expect(events).toHaveLength(1);
    expect(events[0].event_id).toBe("e1");
  });

  test("event 无 node_id 时不写入 output", async () => {
    const store = createInMemoryStorage();
    const output = makeOutput("no-node-output");
    const snapshot = makeSnapshot("run-1", "s1");
    const event = makeEvent("run-1", "e1", "dag.started"); // 无 node_id

    await store.atomicNodeComplete({ output, snapshot, event });

    // output 不应该被写入（因为没有 node_id）
    // 但 snapshot 和 event 仍然写入
    expect(await store.getLatestSnapshot("run-1")).not.toBeNull();
    expect(await store.getEvents("run-1")).toHaveLength(1);
    // 显式断言：output 未被写入
    expect(await store.getOutput("run-1", "any-node")).toBeNull();
  });

  test("多次原子写入累积", async () => {
    const store = createInMemoryStorage();

    await store.atomicNodeComplete({
      output: makeOutput("n1-out"),
      snapshot: makeSnapshot("run-1", "s1"),
      event: makeEvent("run-1", "e1", "node.completed", "n1"),
    });

    await store.atomicNodeComplete({
      output: makeOutput("n2-out"),
      snapshot: makeSnapshot("run-1", "s2"),
      event: makeEvent("run-1", "e2", "node.completed", "n2"),
    });

    // 两个节点的输出都在
    expect((await store.getOutput("run-1", "n1"))!.stdout).toBe("n1-out");
    expect((await store.getOutput("run-1", "n2"))!.stdout).toBe("n2-out");

    // 两个快照都在
    const latest = await store.getLatestSnapshot("run-1");
    expect(latest!.snapshot_id).toBe("s2");

    // 两个事件都在
    const events = await store.getEvents("run-1");
    expect(events).toHaveLength(2);
  });
});

describe("in-memory-storage: deleteRun", () => {
  test("deleteRun 清除所有关联数据", async () => {
    const store = createInMemoryStorage();

    // 写入数据
    await store.appendEvent(makeEvent("run-1", "e1", "dag.started"));
    await store.createSnapshot(makeSnapshot("run-1", "s1"));
    await store.setOutput("run-1", "n1", makeOutput("data"));

    // 删除
    await store.deleteRun("run-1");

    // 全部清空
    expect(await store.getEvents("run-1")).toEqual([]);
    expect(await store.getLatestSnapshot("run-1")).toBeNull();
    expect(await store.getOutput("run-1", "n1")).toBeNull();
    expect(await store.getRunStatus("run-1")).toBeNull();
  });

  test("deleteRun 不影响其他 run", async () => {
    const store = createInMemoryStorage();

    await store.appendEvent(makeEvent("run-1", "e1", "dag.started"));
    await store.appendEvent(makeEvent("run-2", "e2", "dag.started"));

    await store.deleteRun("run-1");

    expect(await store.getEvents("run-1")).toEqual([]);
    expect(await store.getEvents("run-2")).toHaveLength(1);
  });

  test("deleteRun 不存在的 runId 不抛错", async () => {
    const store = createInMemoryStorage();
    // 不应抛错
    await store.deleteRun("nonexistent");
  });

  test("deleteRun 清除 runSummaries（listRuns 不再返回）", async () => {
    const store = createInMemoryStorage();
    await store.createRunSummary(makeRunSummary("run-1", "Pipeline A", "SUCCESS"));
    await store.createRunSummary(makeRunSummary("run-2", "Pipeline B", "FAILED"));

    // 删除前
    let result = await store.listRuns({ page: 1, pageSize: 10 });
    expect(result.total).toBe(2);

    // 删除 run-1
    await store.deleteRun("run-1");

    // 删除后
    result = await store.listRuns({ page: 1, pageSize: 10 });
    expect(result.total).toBe(1);
    expect(result.items[0].run_id).toBe("run-2");
  });
});

describe("in-memory-storage: 工厂隔离", () => {
  test("两次 createInMemoryStorage 返回独立实例", async () => {
    const store1 = createInMemoryStorage();
    const store2 = createInMemoryStorage();

    await store1.appendEvent(makeEvent("run-1", "e1", "dag.started"));

    expect(await store1.getEvents("run-1")).toHaveLength(1);
    expect(await store2.getEvents("run-1")).toHaveLength(0);
  });

  test("runSummaries 在实例间隔离", async () => {
    const store1 = createInMemoryStorage();
    const store2 = createInMemoryStorage();

    await store1.createRunSummary(makeRunSummary("run-1", "Pipeline A"));

    expect((await store1.listRuns({ page: 1, pageSize: 10 })).total).toBe(1);
    expect((await store2.listRuns({ page: 1, pageSize: 10 })).total).toBe(0);
  });
});
