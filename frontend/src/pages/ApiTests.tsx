import { useEffect, useState, useRef, useCallback } from "react";
import { Link } from "react-router-dom";
import { listApiCases, triggerApiRun, listApiRuns, getApiRun } from "../api/apiTests";
import { cancelRun } from "../api/runs";
import { listProjects } from "../api/projects";
import type { ApiTestCase, ApiRunDetail } from "../api/apiTests";
import type { TestRun, TestResult, Project } from "../api/types";

const statusIcon: Record<string, string> = {
  passed: "✅", failed: "❌", skipped: "⏭️", error: "⚠️",
  running: "🔄", pending: "⏳",
};

const statusBadge: Record<string, string> = {
  passed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  running: "bg-blue-100 text-blue-700",
  pending: "bg-gray-100 text-gray-700",
  cancelled: "bg-orange-100 text-orange-700",
};

export default function ApiTests() {
  const [cases, setCases] = useState<ApiTestCase[]>([]);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [running, setRunning] = useState(false);
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [showLogs, setShowLogs] = useState(false);
  const [runResults, setRunResults] = useState<TestResult[]>([]);
  const [activeRun, setActiveRun] = useState<TestRun | null>(null);
  const [showResults, setShowResults] = useState(false);
  const [moduleFilter, setModuleFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const logEndRef = useRef<HTMLDivElement>(null);
  const autoScrollRef = useRef(true);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const scrollToEnd = useCallback(() => {
    if (autoScrollRef.current && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    if (logs.length > 0) scrollToEnd();
  }, [logs, scrollToEnd]);

  // 用户手动滚动时暂停自动滚动，滚回底部时恢复
  const handleLogScroll = useCallback(() => {
    const el = logContainerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    autoScrollRef.current = atBottom;
  }, []);

  // 加载用例和项目
  useEffect(() => {
    const params: Record<string, string> = {};
    if (moduleFilter) params.module = moduleFilter;
    if (priorityFilter) params.priority = priorityFilter;
    listApiCases(params).then(setCases).catch(console.error);
    listProjects().then(setProjects).catch(console.error);
    listApiRuns().then(setRuns).catch(console.error);
  }, [moduleFilter, priorityFilter]);

  // 轮询运行列表
  useEffect(() => {
    const fetch = () => {
      listApiRuns().then((data) => {
        setRuns(data);
        const hasActive = data.some((r) => r.status === "pending" || r.status === "running");
        if (hasActive && !timerRef.current) {
          timerRef.current = setInterval(fetch, 2000);
        } else if (!hasActive && timerRef.current) {
          clearInterval(timerRef.current);
          timerRef.current = null;
        }
      }).catch(console.error);
    };
    fetch();
    // 当有新运行启动时，确保轮询开始
    if (running && !timerRef.current) {
      timerRef.current = setInterval(fetch, 2000);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); timerRef.current = null; };
  }, [running]);

  // WebSocket 实时日志
  useEffect(() => {
    if (!activeRunId) return;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/runs/${activeRunId}`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.event === "log") {
          setLogs((prev) => [...prev, msg.data.line || ""]);
        } else if (msg.event === "run_complete") {
          setRunning(false);
          getApiRun(activeRunId).then((detail: ApiRunDetail) => {
            setActiveRun(detail.run);
            setRunResults(detail.results);
            // 有失败时自动展开结果
            if (detail.run.failed > 0 || detail.run.status === "error") {
              setShowResults(true);
            }
          }).catch(console.error);
          listApiRuns().then(setRuns).catch(console.error);
        }
      } catch { /* ignore */ }
    };

    return () => { ws.close(); wsRef.current = null; };
  }, [activeRunId]);

  const toggleCase = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedIds.size === cases.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(cases.map((c) => c.id)));
    }
  };

  const handleCancel = async (runId: number) => {
    if (!confirm(`确定停止运行 #${runId}？`)) return;
    try {
      await cancelRun(runId);
      listApiRuns().then(setRuns).catch(console.error);
    } catch (e) {
      console.error(e);
    }
  };

  const handleRun = async (caseIds?: number[]) => {
    const activeProject = projects.find((p) => p.is_active) ?? projects[0];
    if (!activeProject || running) return;
    setRunning(true);
    setLogs([]);
    setRunResults([]);
    setActiveRun(null);
    setShowLogs(true);
    autoScrollRef.current = true;
    try {
      const run = await triggerApiRun(activeProject.id, caseIds);
      setActiveRunId(run.id);
      setActiveRun(run);
      // 立即刷新运行历史，让当前运行出现在列表中
      listApiRuns().then(setRuns).catch(console.error);
    } catch (e) {
      console.error(e);
      setRunning(false);
    }
  };

  // 统计
  const totalCases = cases.length;
  const latestRun = runs[0];
  const passRate = latestRun && latestRun.total > 0
    ? ((latestRun.passed / latestRun.total) * 100).toFixed(1)
    : "0";

  // 模块分组统计
  const moduleStats = cases.reduce((acc, c) => {
    const mod = c.tags.split(",")[1]?.trim() || "unknown";
    if (!acc[mod]) acc[mod] = { total: 0, name: mod };
    acc[mod].total++;
    return acc;
  }, {} as Record<string, { total: number; name: string }>);

  const isRunning = running || activeRun?.status === "running" || activeRun?.status === "pending";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">接口测试</h1>
        <div className="flex gap-2">
          <button
            onClick={() => handleRun(Array.from(selectedIds))}
            disabled={running || selectedIds.size === 0}
            className={`px-4 py-2 text-white rounded-lg text-sm transition-colors ${
              running || selectedIds.size === 0
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-700"
            }`}
          >
            {running ? "运行中..." : `运行选中 (${selectedIds.size})`}
          </button>
          <button
            onClick={() => handleRun()}
            disabled={running}
            className={`px-4 py-2 text-white rounded-lg text-sm transition-colors ${
              running ? "bg-gray-400 cursor-not-allowed" : "bg-green-600 hover:bg-green-700"
            }`}
          >
            {running ? "运行中..." : "全部运行"}
          </button>
        </div>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="text-sm text-gray-500">总用例</div>
          <div className="text-2xl font-bold mt-2">{totalCases}</div>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="text-sm text-gray-500">通过率</div>
          <div className="text-2xl font-bold mt-2">{passRate}%</div>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="text-sm text-gray-500">运行次数</div>
          <div className="text-2xl font-bold mt-2">{runs.length}</div>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="text-sm text-gray-500">平均耗时</div>
          <div className="text-2xl font-bold mt-2">
            {latestRun ? `${(latestRun.duration_ms / 1000).toFixed(1)}s` : "-"}
          </div>
        </div>
      </div>

      {/* 实时日志面板 */}
      {showLogs && (
        <div className="bg-gray-900 rounded-xl shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 bg-gray-800">
            <span className="text-sm text-gray-300 font-medium">
              实时日志 {logs.length > 0 && <span className="text-gray-500">({logs.length} 行)</span>}
            </span>
            <div className="flex items-center gap-3">
              {isRunning ? (
                <span className="flex items-center gap-1.5 text-xs text-green-400">
                  <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                  运行中
                </span>
              ) : (
                <span className="flex items-center gap-1.5 text-xs text-gray-400">
                  <span className="w-2 h-2 rounded-full bg-gray-500" />
                  已完成
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
              <p className="text-gray-600">等待日志输出...</p>
            ) : (
              logs.map((line, i) => (
                <div key={i} className="whitespace-pre-wrap break-all">{line}</div>
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </div>
      )}

      {/* 运行结果（可折叠） */}
      {activeRun && !isRunning && runResults.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div
            className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between cursor-pointer select-none"
            onClick={() => setShowResults(!showResults)}
          >
            <div className="flex items-center gap-2">
              <span className="text-gray-400 text-xs">{showResults ? "▼" : "▶"}</span>
              <span className="font-medium">运行 #{activeRun.id} 结果</span>
              <span className={`px-2 py-0.5 rounded-full text-xs ${statusBadge[activeRun.status] ?? ""}`}>
                {activeRun.status}
              </span>
              <span className="text-sm text-gray-500">
                通过 {activeRun.passed} / 失败 {activeRun.failed} / 跳过 {activeRun.skipped}
              </span>
            </div>
            <span className="text-xs text-gray-400">{showResults ? "收起" : "展开"}</span>
          </div>
          {showResults && (
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">状态</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">用例名</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">耗时</th>
                  <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">错误</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {runResults.map((r) => (
                  <tr key={r.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2">{statusIcon[r.status] ?? "❓"}</td>
                    <td className="px-4 py-2 text-sm font-mono">{r.case_name}</td>
                    <td className="px-4 py-2 text-sm">{r.duration_ms}ms</td>
                    <td className="px-4 py-2 text-sm">
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
      )}

      {/* 用例列表 */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
          <span className="font-medium">接口用例</span>
          <div className="flex items-center gap-3">
            <select
              value={moduleFilter}
              onChange={(e) => setModuleFilter(e.target.value)}
              className="text-sm border rounded px-2 py-1"
            >
              <option value="">全部模块</option>
              {Object.values(moduleStats).map((m) => (
                <option key={m.name} value={m.name}>{m.name} ({m.total})</option>
              ))}
            </select>
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="text-sm border rounded px-2 py-1"
            >
              <option value="">全部优先级</option>
              <option value="P0">P0</option>
              <option value="P1">P1</option>
            </select>
            <button
              onClick={toggleAll}
              className="text-sm text-blue-600 hover:underline"
            >
              {selectedIds.size === cases.length ? "取消全选" : "全选"}
            </button>
          </div>
        </div>
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 w-10">
                <input
                  type="checkbox"
                  checked={selectedIds.size === cases.length && cases.length > 0}
                  onChange={toggleAll}
                  className="w-4 h-4 rounded"
                />
              </th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">用例名</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">模块</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">优先级</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">文件</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {cases.map((c) => (
              <tr
                key={c.id}
                className={`hover:bg-gray-50 cursor-pointer ${selectedIds.has(c.id) ? "bg-blue-50" : ""}`}
                onClick={() => toggleCase(c.id)}
              >
                <td className="px-4 py-2">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(c.id)}
                    onChange={() => toggleCase(c.id)}
                    className="w-4 h-4 rounded"
                  />
                </td>
                <td className="px-4 py-2 text-sm font-mono">{c.name}</td>
                <td className="px-4 py-2 text-sm">{c.tags.split(",")[1]?.trim() || "-"}</td>
                <td className="px-4 py-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    c.priority === "P0" ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"
                  }`}>
                    {c.priority}
                  </span>
                </td>
                <td className="px-4 py-2 text-sm text-gray-500">{c.file_path}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 运行历史 */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b bg-gray-50">
          <span className="font-medium">运行历史</span>
        </div>
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">ID</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">状态</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">通过率</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">耗时</th>
              <th className="px-4 py-2 text-left text-sm font-medium text-gray-500">时间</th>
              <th className="px-4 py-2 text-center text-sm font-medium text-gray-500">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {runs.map((run) => (
              <tr key={run.id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-sm">
                  <Link to={`/runs/${run.id}`} className="text-blue-600 hover:underline font-mono">
                    #{run.id}
                  </Link>
                </td>
                <td className="px-4 py-2">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusBadge[run.status] ?? ""}`}>
                    {run.status}
                  </span>
                </td>
                <td className="px-4 py-2 text-sm">
                  {run.total > 0 ? `${((run.passed / run.total) * 100).toFixed(1)}%` : "-"}
                </td>
                <td className="px-4 py-2 text-sm">{(run.duration_ms / 1000).toFixed(1)}s</td>
                <td className="px-4 py-2 text-sm">{new Date(run.created_at).toLocaleString()}</td>
                <td className="px-4 py-2 text-center">
                  {(run.status === "running" || run.status === "pending") && (
                    <button
                      onClick={() => handleCancel(run.id)}
                      className="px-2 py-1 text-xs text-red-600 border border-red-300 rounded hover:bg-red-50 transition-colors"
                    >
                      停止
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
