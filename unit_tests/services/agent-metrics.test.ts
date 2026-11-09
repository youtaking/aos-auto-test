// agent-metrics.test.ts — Agent 启动/运行指标状态机测试
// 测试目标：beginAgentRun / agentRunReady / agentRunDisconnected / finishAgentRun / active 回调
// 业务意图：确保活跃实例状态可观测、同一代次只结算一次、迟到通知不影响后继实例
// 源：packages/agent-runtime/src/server/services/agent-metrics.ts（main a7f477a9e）

import { beforeEach, describe, expect, test } from "bun:test";

// ── 复制实现（OTel 记录器以端口形式注入） ──

type Result = "success" | "failure" | "cancelled";
type Engine = string;

interface SpanStub {
  attributes: Record<string, unknown>;
  ended: boolean;
  status?: { code: number };
  setAttribute(key: string, value: unknown): void;
  setStatus(status: { code: number }): void;
  end(): void;
}

interface Recorder {
  spans: SpanStub[];
  startSpan(name: string, options: { attributes: Record<string, unknown> }): SpanStub;
  recordStartup(seconds: number, attrs: { engine: Engine; result: Result }): void;
  recordDuration(seconds: number, attrs: { engine: Engine; result: Result }): void;
  countRun(attrs: { engine: Engine; result: Result }): void;
  observe(attrs: { engine: Engine; state: string }): void;
}

const KNOWN_ENGINES = ["peri", "claude-code", "opencode", "ccb"];
const SpanStatusCode = { UNSET: 0, ERROR: 2 } as const;

const running = new Map<
  string,
  { generation: number; engine: Engine; state: "starting" | "running" | "unknown"; started: number; span: SpanStub | null }
>();

function createRecorder(): Recorder {
  const recorder: Recorder = {
    spans: [],
    startSpan(name, options) {
      const span: SpanStub = {
        attributes: { ...options.attributes },
        ended: false,
        setAttribute(key, value) {
          this.attributes[key] = value;
        },
        setStatus(status) {
          this.status = status;
        },
        end() {
          this.ended = true;
        },
      };
      recorder.spans.push(span);
      return span;
    },
    recordStartup: () => {},
    recordDuration: () => {},
    countRun: () => {},
    observe: () => {},
  };
  return recorder;
}

let recorder = createRecorder();
const clock = { now: 1_000 };

function beginAgentRun(id: string, generation: number): void {
  finishAgentRun(id, "cancelled");
  running.set(id, {
    generation,
    engine: "unknown",
    state: "starting",
    started: clock.now,
    span: recorder.startSpan("agent.start", { attributes: { "fenix.agent.instance.id": id } }),
  });
}

function agentRunReady(id: string, engine: string | undefined): void {
  const run = running.get(id);
  if (!run) return;
  run.engine = KNOWN_ENGINES.includes(engine ?? "") ? engine! : "other";
  run.state = "running";
  recorder.recordStartup((clock.now - run.started) / 1000, { engine: run.engine, result: "success" });
  run.span?.setAttribute("engine", run.engine);
  run.span?.end();
  run.span = null;
}

function agentRunDisconnected(id: string): void {
  const run = running.get(id);
  if (run) run.state = "unknown";
}

function finishAgentRun(id: string, result: Result, generation?: number): void {
  const run = running.get(id);
  if (!run || (generation !== undefined && generation !== run.generation)) return;
  running.delete(id);
  const seconds = (clock.now - run.started) / 1000;
  if (run.span) {
    recorder.recordStartup(seconds, { engine: run.engine, result });
    run.span.setStatus({ code: result === "failure" ? SpanStatusCode.ERROR : SpanStatusCode.UNSET });
    run.span.end();
  }
  recorder.countRun({ engine: run.engine, result });
  recorder.recordDuration(seconds, { engine: run.engine, result });
}

function activeTotals(): Map<string, number> {
  const totals = new Map<string, number>();
  for (const run of running.values()) {
    const key = `${run.engine}:${run.state}`;
    totals.set(key, (totals.get(key) ?? 0) + 1);
  }
  for (const engine of [...KNOWN_ENGINES, "other", "unknown"]) {
    for (const state of ["starting", "running", "unknown"])
      recorder.observe({ engine, state });
  }
  return totals;
}

// ── tests ──

describe("agent-metrics 运行指标状态机", () => {
  beforeEach(() => {
    running.clear();
    recorder = createRecorder();
    clock.now = 1_000;
  });

  test("begin 后实例处于 starting / unknown 引擎", () => {
    beginAgentRun("inst-1", 1);
    expect(activeTotals().get("unknown:starting")).toBe(1);
  });

  test("begin 创建带实例属性的启动 span", () => {
    beginAgentRun("inst-1", 1);
    expect(recorder.spans).toHaveLength(1);
    expect(recorder.spans[0]!.attributes["fenix.agent.instance.id"]).toBe("inst-1");
  });

  test("就绪后记录启动耗时并结束 span", () => {
    const startup: Array<{ seconds: number; attrs: { engine: string; result: string } }> = [];
    recorder.recordStartup = (seconds, attrs) => startup.push({ seconds, attrs });
    beginAgentRun("inst-1", 1);
    clock.now += 1_500;
    agentRunReady("inst-1", "peri");
    expect(startup).toEqual([{ seconds: 1.5, attrs: { engine: "peri", result: "success" } }]);
    expect(activeTotals().get("peri:running")).toBe(1);
    expect(recorder.spans[0]!.ended).toBe(true);
    expect(recorder.spans[0]!.attributes.engine).toBe("peri");
  });

  test("未知引擎归入 other 分类", () => {
    beginAgentRun("inst-1", 1);
    agentRunReady("inst-1", "custom-engine");
    expect(activeTotals().get("other:running")).toBe(1);
  });

  test("未提供引擎时归入 other", () => {
    beginAgentRun("inst-1", 1);
    agentRunReady("inst-1", undefined);
    expect(activeTotals().get("other:running")).toBe(1);
  });

  test("未开始就绪通知是空操作", () => {
    let called = 0;
    recorder.recordStartup = () => {
      called++;
    };
    agentRunReady("missing", "peri");
    expect(called).toBe(0);
  });

  test("断连只标记 unknown，不结算", () => {
    const counterCalls: unknown[] = [];
    recorder.countRun = (attrs) => counterCalls.push(attrs);
    beginAgentRun("inst-1", 1);
    agentRunReady("inst-1", "peri");
    agentRunDisconnected("inst-1");
    expect(activeTotals().get("peri:unknown")).toBe(1);
    expect(counterCalls).toHaveLength(0);
  });

  test("成功结算记录计数与耗时", () => {
    const runs: unknown[] = [];
    const durations: unknown[] = [];
    recorder.countRun = (attrs) => runs.push(attrs);
    recorder.recordDuration = (seconds, attrs) => durations.push({ seconds, attrs });
    beginAgentRun("inst-1", 1);
    agentRunReady("inst-1", "claude-code");
    clock.now += 2_000;
    finishAgentRun("inst-1", "success");
    expect(runs).toEqual([{ engine: "claude-code", result: "success" }]);
    expect(durations).toEqual([{ seconds: 2, attrs: { engine: "claude-code", result: "success" } }]);
    expect(running.size).toBe(0);
  });

  test("启动中就失败时用启动 span 记录失败并标记 ERROR", () => {
    const startup: Array<{ attrs: { result: string } }> = [];
    recorder.recordStartup = (_seconds, attrs) => startup.push({ attrs });
    beginAgentRun("inst-1", 1);
    finishAgentRun("inst-1", "failure");
    expect(startup[0]!.attrs.result).toBe("failure");
    expect(recorder.spans[0]!.status).toEqual({ code: SpanStatusCode.ERROR });
    expect(recorder.spans[0]!.ended).toBe(true);
  });

  test("代次不匹配的迟到通知被忽略", () => {
    beginAgentRun("inst-1", 2);
    const runs: unknown[] = [];
    recorder.countRun = (attrs) => runs.push(attrs);
    finishAgentRun("inst-1", "failure", 1);
    expect(runs).toHaveLength(0);
    expect(activeTotals().get("unknown:starting")).toBe(1);
  });

  test("代次匹配的死亡通知正常结算", () => {
    beginAgentRun("inst-1", 2);
    const runs: unknown[] = [];
    recorder.countRun = (attrs) => runs.push(attrs);
    finishAgentRun("inst-1", "failure", 2);
    expect(runs).toEqual([{ engine: "unknown", result: "failure" }]);
  });

  test("重复 begin 会先取消旧代次", () => {
    const runs: unknown[] = [];
    recorder.countRun = (attrs) => runs.push(attrs);
    beginAgentRun("inst-1", 1);
    beginAgentRun("inst-1", 2);
    expect(runs).toEqual([{ engine: "unknown", result: "cancelled" }]);
    expect(activeTotals().get("unknown:starting")).toBe(1);
  });

  test("结算后同一实例可重新开始", () => {
    beginAgentRun("inst-1", 1);
    finishAgentRun("inst-1", "success");
    beginAgentRun("inst-1", 2);
    agentRunReady("inst-1", "opencode");
    expect(activeTotals().get("opencode:running")).toBe(1);
  });
});
