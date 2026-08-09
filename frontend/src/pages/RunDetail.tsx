import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { getRun, getRunResults, getRunLogs, cancelRun } from "../api/runs";
import type { TestRun, TestResult } from "../api/types";

const statusIcon: Record<string, string> = {
  passed: "✅", failed: "❌", skipped: "⏭️", error: "⚠️", running: "🔄", pending: "⏳", cancelled: "🚫",
};

interface WsMessage {
  event: string;
  data: Record<string, unknown>;
}

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<TestRun | null>(null);
  const [results, setResults] = useState<TestResult[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [showLogs, setShowLogs] = useState(false);
  const [showUnit, setShowUnit] = useState(true);
  const [showIntegration, setShowIntegration] = useState(true);
  const [unitResults, setUnitResults] = useState<{ total: number; passed: number; failed: number; skipped: number; duration_ms: number; status: string; results: { id: number; name: string; classname: string; status: string; duration_ms: number; failure_message: string | null }[] } | null>(null);
  const logsLoadedRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const logEndRef = useRef<HTMLDivElement>(null);
  const autoScrollRef = useRef(true);

  const scrollToEnd = useCallback(() => {
    if (autoScrollRef.current && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    if (logs.length > 0) scrollToEnd();
  }, [logs, scrollToEnd]);

  const handleLogScroll = useCallback(() => {
    const el = logContainerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    autoScrollRef.current = atBottom;
  }, []);

  // 加载历史日志
  const loadLogs = useCallback(() => {
    if (!id || logsLoadedRef.current) return;
    logsLoadedRef.current = true;
    // 只在日志为空时从文件加载（运行中的日志由 WS 实时推送）
    setLogs((prev) => {
      if (prev.length > 0) return prev;
      getRunLogs(Number(id)).then((lines) => {
        if (lines.length > 0) setLogs(lines);
      }).catch(console.error);
      return prev;
    });
  }, [id]);

  // 点击"显示日志"时加载
  const handleToggleLogs = useCallback(() => {
    if (!showLogs) loadLogs();
    setShowLogs(!showLogs);
  }, [showLogs, loadLogs]);

  const handleCancel = async () => {
    if (!run || !confirm(`确定停止运行 #${run.id}？`)) return;
    try {
      await cancelRun(run.id);
      getRun(Number(id)).then(setRun).catch(console.error);
    } catch (e) {
      console.error(e);
    }
  };

  // 数据获取（轮询 fallback）
  useEffect(() => {
    if (!id) return;
    const runId = Number(id);

    const fetch = () => {
      getRun(runId).then((r) => {
        setRun(r);
        if (r.status !== "pending" && r.status !== "running") {
          if (timerRef.current) clearInterval(timerRef.current);
        }
        // 获取单元测试结果
        if (r.pipeline_id) {
          window.fetch(`/api/pipelines/${r.pipeline_id}/unit-results`)
            .then((res) => res.json())
            .then((resp) => {
              if (resp.success) setUnitResults(resp.data);
            })
            .catch(console.error);
        }
      }).catch(console.error);
      getRunResults(runId).then(setResults).catch(console.error);
    };

    fetch();
    timerRef.current = setInterval(fetch, 2000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [id]);

  // WebSocket 连接实时日志
  useEffect(() => {
    if (!id) return;
    const runId = Number(id);

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/runs/${runId}`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const msg: WsMessage = JSON.parse(e.data);
        if (msg.event === "log") {
          const line = (msg.data.line as string) || "";
          setLogs((prev) => [...prev, line]);
        } else if (msg.event === "run_complete") {
          // 运行完成，刷新最终状态
          getRun(runId).then(setRun).catch(console.error);
          getRunResults(runId).then(setResults).catch(console.error);
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onerror = () => {
      // WS 断连时静默降级到轮询
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [id]);

  if (!run) return <div className="p-8 text-gray-500">加载中...</div>;

  const isFinished = run.status !== "pending" && run.status !== "running";
  const allureUrl = `/api/runs/${run.id}/allure`;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">
          运行 #{run.id}
          {run.status === "running" && (
            <span className="ml-3 text-sm font-normal text-blue-500 animate-pulse">运行中...</span>
          )}
        </h1>
        <div className="flex items-center gap-3">
          {!isFinished && (
            <button
              onClick={handleCancel}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors text-sm"
            >
              停止运行
            </button>
          )}
          <button
            onClick={handleToggleLogs}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
              showLogs ? "bg-gray-700 text-white" : "bg-gray-200 text-gray-700 hover:bg-gray-300"
            }`}
          >
            {showLogs ? "隐藏日志" : "显示日志"}
          </button>
          {isFinished && (
            <a
              href={allureUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors text-sm"
            >
              Allure 报告
            </a>
          )}
        </div>
      </div>

      {/* 来源信息 */}
      <div className="bg-white rounded-xl shadow-sm p-4 flex items-center gap-4 text-sm">
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
          run.trigger_type === "ci" ? "bg-purple-100 text-purple-700" : "bg-blue-100 text-blue-700"
        }`}>
          {run.trigger_type === "ci" ? "Pipeline" : "手动触发"}
        </span>
        {run.trigger_type === "ci" ? (
          <>
            {run.pipeline_id && (
              <Link to="/ci" className="text-blue-600 hover:underline">Pipeline #{run.pipeline_id}</Link>
            )}
            {run.git_branch && (
              <span className="text-gray-500">分支: <code className="text-xs bg-gray-100 px-1 rounded">{run.git_branch}</code></span>
            )}
            {run.git_commit && (
              <span className="text-gray-500">Commit: <code className="text-xs bg-gray-100 px-1 rounded">{run.git_commit.slice(0, 8)}</code></span>
            )}
          </>
        ) : (
          <>
            <span className="text-gray-500">{run.trigger_user || "用户"}</span>
            {run.collection_ids && run.collection_ids.length > 0 && (
              <span className="text-gray-500">使用 {run.collection_ids.length} 个用例集</span>
            )}
          </>
        )}
        <span className="text-gray-400 ml-auto">{new Date(run.created_at).toLocaleString()}</span>
      </div>
        {(() => {
          const uT = unitResults?.total ?? 0, uP = unitResults?.passed ?? 0,
                uF = unitResults?.failed ?? 0, uS = unitResults?.skipped ?? 0,
                uD = unitResults?.duration_ms ?? 0;
          const total = run.total + uT;
          const passed = run.passed + uP;
          const failed = run.failed + uF;
          const skipped = run.skipped + uS;
          const duration = Math.max(run.duration_ms, uD);
          return [
            { label: "总计", value: total, color: "" },
            { label: "通过", value: passed, color: "text-green-600" },
            { label: "失败", value: failed, color: "text-red-600" },
            { label: "跳过", value: skipped, color: "text-gray-500" },
            { label: "耗时", value: `${(duration / 1000).toFixed(1)}s`, color: "" },
          ].map((item) => (
            <div key={item.label} className="bg-white rounded-xl p-4 shadow-sm text-center">
              <div className="text-sm text-gray-500">{item.label}</div>
              <div className={`text-xl font-bold ${item.color}`}>{item.value}</div>
            </div>
          ));
        })()}
      </div>

      {/* 实时日志面板 */}
      {showLogs && (
        <div className="bg-gray-900 rounded-xl shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 bg-gray-800">
            <span className="text-sm text-gray-300 font-medium">
              实时日志 {logs.length > 0 && <span className="text-gray-500">({logs.length} 行)</span>}
            </span>
            <div className="flex items-center gap-3">
              {run.status === "running" && (
                <span className="flex items-center gap-1.5 text-xs text-green-400">
                  <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                  接收中
                </span>
              )}
              <button
                onClick={() => setShowLogs(false)}
                className="text-xs text-gray-500 hover:text-gray-300"
              >
                ✕ 关闭
              </button>
            </div>
          </div>
          <div
            ref={logContainerRef}
            onScroll={handleLogScroll}
            className="h-80 overflow-y-auto p-4 font-mono text-xs text-gray-300 leading-relaxed"
          >
            {logs.length === 0 ? (
              <p className="text-gray-600">
                {run.status === "pending" ? "等待运行开始..." : run.status === "running" ? "等待日志输出..." : "无日志"}
              </p>
            ) : (
              logs.map((line, i) => (
                <div key={i} className="whitespace-pre-wrap break-all">
                  {line}
                </div>
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </div>
      )}

      {/* 单元测试结果 */}
      {unitResults && unitResults.status !== "not_run" && unitResults.total > 0 && (
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div
            className="px-4 py-3 bg-blue-50 border-b flex items-center justify-between cursor-pointer select-none hover:bg-blue-100 transition-colors"
            onClick={() => setShowUnit(!showUnit)}
          >
            <h2 className="text-sm font-medium text-blue-700 flex items-center gap-2">
              <span className="text-xs text-gray-400">{showUnit ? "▼" : "▶"}</span>
              单元测试 ({unitResults.total})
            </h2>
            <span className="text-xs text-gray-500">
              {unitResults.passed}✅ {unitResults.failed}❌ {unitResults.skipped}⏭️ · {unitResults.duration_ms}ms
            </span>
          </div>
          {showUnit && unitResults.results.length > 0 && (
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">状态</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Describe</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">用例</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">耗时</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">错误</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {unitResults.results.map((r) => (
                <tr key={r.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2">{statusIcon[r.status] ?? "❓"}</td>
                  <td className="px-4 py-2 text-xs text-gray-500">{r.classname}</td>
                  <td className="px-4 py-2 text-sm font-mono">{r.name}</td>
                  <td className="px-4 py-2 text-sm">{r.duration_ms}ms</td>
                  <td className="px-4 py-2 text-sm">
                    {r.failure_message ? (
                      <div className="max-w-sm max-h-24 overflow-y-auto bg-red-50 rounded p-2 text-red-600 text-xs font-mono whitespace-pre-wrap break-all">
                        {r.failure_message}
                      </div>
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          )}
          {showUnit && unitResults.results.length === 0 && (
            <div className="px-4 py-6 text-center text-sm text-gray-400">
              测试已运行 ({unitResults.total} 条)，但逐条结果未存储。下次 Pipeline 运行后将自动修复。
            </div>
          )}
        </div>
      )}

      {/* 集成测试结果 */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div
          className="px-4 py-3 bg-green-50 border-b cursor-pointer select-none hover:bg-green-100 transition-colors"
          onClick={() => setShowIntegration(!showIntegration)}
        >
          <h2 className="text-sm font-medium text-green-700 flex items-center gap-2">
            <span className="text-xs text-gray-400">{showIntegration ? "▼" : "▶"}</span>
            集成测试 ({results.length})
          </h2>
        </div>
        {showIntegration && (
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">状态</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">用例名</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">套件</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">耗时</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">错误</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {results.map((r) => (
              <tr key={r.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">{statusIcon[r.status] ?? "❓"}</td>
                <td className="px-4 py-3 text-sm font-mono">{r.case_name}</td>
                <td className="px-4 py-3 text-sm">{r.suite_name}</td>
                <td className="px-4 py-3 text-sm">{r.duration_ms}ms</td>
                <td className="px-4 py-3 text-sm">
                  {r.error_message ? (
                    <div className="max-w-sm max-h-24 overflow-y-auto bg-red-50 rounded p-2 text-red-600 text-xs font-mono whitespace-pre-wrap break-all">
                      {r.error_message}
                    </div>
                  ) : (
                    <span className="text-gray-400">-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        )}
      </div>

    </div>
  );
}
