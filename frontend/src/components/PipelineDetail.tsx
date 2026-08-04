import { useEffect, useState, useRef } from "react";
import type { Pipeline } from "../api/types";
import { getRunResults, getRunLogs } from "../api/runs";
import type { TestResult } from "../api/types";
import { X, RefreshCw, Trash2, ExternalLink } from "lucide-react";

interface Props {
  pipeline: Pipeline;
  onClose: () => void;
  onRerun: (caseIds?: number[]) => void;
  onDestroy: () => void;
}

const statusIcons: Record<string, string> = {
  queued: "⏳", building: "🔨", deploying: "🚀", running: "🔄",
  passed: "✅", failed: "❌", error: "⚠️", destroyed: "🗑️",
};

export default function PipelineDetail({ pipeline, onClose, onRerun, onDestroy }: Props) {
  const [results, setResults] = useState<TestResult[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<"info" | "results" | "logs">("info");
  const logEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (pipeline.run_id) {
      getRunResults(pipeline.run_id).then(setResults).catch(console.error);
      getRunLogs(pipeline.run_id).then(setLogs).catch(console.error);
    }
  }, [pipeline.run_id]);

  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${window.location.host}/ws/pipelines/${pipeline.id}`);
    wsRef.current = ws;
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.event === "test_log") {
        setLogs((prev) => [...prev, msg.data.line]);
      }
      if (msg.event === "test_progress" && pipeline.run_id) {
        getRunResults(pipeline.run_id).then(setResults).catch(console.error);
      }
    };
    return () => { ws.close(); wsRef.current = null; };
  }, [pipeline.id, pipeline.run_id]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  let envInfo: any = null;
  try {
    envInfo = pipeline.environment_info ? JSON.parse(pipeline.environment_info) : null;
  } catch {
    envInfo = null;
  }
  const passRate = pipeline.test_total > 0
    ? ((pipeline.test_passed / pipeline.test_total) * 100).toFixed(1)
    : "-";

  return (
    <div className="bg-white rounded-xl shadow-lg border p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold">
          {statusIcons[pipeline.status]} PR #{pipeline.pr_id} {pipeline.pr_title}
        </h3>
        <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded">
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="flex gap-2 border-b">
        {(["info", "results", "logs"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab === "info" ? "基本信息" : tab === "results" ? `测试结果 (${pipeline.test_total})` : "实时日志"}
          </button>
        ))}
      </div>

      {activeTab === "info" && (
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="space-y-2">
            <div><span className="text-gray-500">作者:</span> {pipeline.author}</div>
            <div><span className="text-gray-500">Commit:</span> <code>{pipeline.commit_sha.slice(0, 8)}</code></div>
            <div><span className="text-gray-500">分支:</span> {pipeline.branch}</div>
            <div><span className="text-gray-500">触发时间:</span> {new Date(pipeline.created_at).toLocaleString()}</div>
            {pipeline.error_message && (
              <div className="text-red-600"><span className="text-gray-500">错误:</span> {pipeline.error_message}</div>
            )}
          </div>
          <div className="space-y-2">
            <div><span className="text-gray-500">Slot:</span> {pipeline.slot_name || "排队中"}</div>
            {envInfo && (
              <>
                <div><span className="text-gray-500">RCS URL:</span> <code>{envInfo.rcs_url}</code></div>
                <div><span className="text-gray-500">镜像:</span> <code className="text-xs">{pipeline.docker_image}</code></div>
              </>
            )}
            <div><span className="text-gray-500">测试:</span> {pipeline.test_passed}✅ {pipeline.test_failed}❌ {pipeline.test_skipped}⏭️ ({passRate}%)</div>
            {pipeline.timeout_at && (
              <div><span className="text-gray-500">超时销毁:</span> {new Date(pipeline.timeout_at).toLocaleString()}</div>
            )}
          </div>
        </div>
      )}

      {activeTab === "results" && (
        <div className="max-h-96 overflow-y-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left">
                <th className="py-2">状态</th>
                <th className="py-2">套件</th>
                <th className="py-2">用例</th>
                <th className="py-2">耗时</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.id} className="border-b">
                  <td className="py-1.5">
                    {r.status === "passed" ? "✅" : r.status === "failed" ? "❌" : r.status === "skipped" ? "⏭️" : "⚠️"}
                  </td>
                  <td className="py-1.5">{r.suite_name}</td>
                  <td className="py-1.5 font-mono text-xs">{r.case_name}</td>
                  <td className="py-1.5">{r.duration_ms}ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === "logs" && (
        <div className="bg-gray-900 text-green-400 rounded-lg p-4 max-h-96 overflow-y-auto font-mono text-xs">
          {logs.map((line, i) => (
            <div key={i}>{line}</div>
          ))}
          <div ref={logEndRef} />
        </div>
      )}

      <div className="flex gap-2 pt-2 border-t">
        {pipeline.status !== "destroyed" && pipeline.status !== "queued" && (
          <>
            <button
              onClick={() => onRerun()}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <RefreshCw className="w-4 h-4" /> 重跑测试
            </button>
            <button
              onClick={onDestroy}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700"
            >
              <Trash2 className="w-4 h-4" /> 销毁环境
            </button>
          </>
        )}
        {pipeline.status === "destroyed" && (
          <button
            onClick={() => onRerun()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-orange-600 text-white rounded-lg hover:bg-orange-700"
          >
            <RefreshCw className="w-4 h-4" /> 重建并重跑
          </button>
        )}
        {pipeline.status === "queued" && (
          <button
            onClick={() => onRerun()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-gray-600 text-white rounded-lg hover:bg-gray-700"
          >
            <X className="w-4 h-4" /> 取消排队
          </button>
        )}
        {pipeline.run_id && (
          <a
            href={`/runs/${pipeline.run_id}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50"
          >
            <ExternalLink className="w-4 h-4" /> 运行详情
          </a>
        )}
      </div>
    </div>
  );
}
