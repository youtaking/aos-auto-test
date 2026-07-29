import { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "react-router-dom";
import { getRun, getRunResults } from "../api/runs";
import type { TestRun, TestResult } from "../api/types";

const statusIcon: Record<string, string> = {
  passed: "✅", failed: "❌", skipped: "⏭️", error: "⚠️", running: "🔄", pending: "⏳",
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
  const [showLogs, setShowLogs] = useState(true);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  const scrollToEnd = useCallback(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    if (logs.length > 0) scrollToEnd();
  }, [logs, scrollToEnd]);

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
          <button
            onClick={() => setShowLogs(!showLogs)}
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
      <div className="grid grid-cols-5 gap-4">
        {[
          { label: "总计", value: run.total, color: "" },
          { label: "通过", value: run.passed, color: "text-green-600" },
          { label: "失败", value: run.failed, color: "text-red-600" },
          { label: "跳过", value: run.skipped, color: "text-gray-500" },
          { label: "耗时", value: `${(run.duration_ms / 1000).toFixed(1)}s`, color: "" },
        ].map((item) => (
          <div key={item.label} className="bg-white rounded-xl p-4 shadow-sm text-center">
            <div className="text-sm text-gray-500">{item.label}</div>
            <div className={`text-xl font-bold ${item.color}`}>{item.value}</div>
          </div>
        ))}
      </div>

      {/* 结果表格 */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
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
                <td className="px-4 py-3 text-sm text-red-600 max-w-xs truncate">{r.error_message ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 实时日志面板 */}
      {showLogs && (
        <div className="bg-gray-900 rounded-xl shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 bg-gray-800">
            <span className="text-sm text-gray-300 font-medium">
              实时日志 {logs.length > 0 && <span className="text-gray-500">({logs.length} 行)</span>}
            </span>
            {run.status === "running" && (
              <span className="flex items-center gap-1.5 text-xs text-green-400">
                <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                接收中
              </span>
            )}
          </div>
          <div className="h-80 overflow-y-auto p-4 font-mono text-xs text-gray-300 leading-relaxed">
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
    </div>
  );
}
