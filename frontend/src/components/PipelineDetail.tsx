import { useEffect, useState, useRef } from "react";
import type { Pipeline } from "../api/types";
import { getRunResults } from "../api/runs";
import { getPipelineLogs } from "../api/pipelines";
import { getPipelineUnitResults } from "../api/unitTests";
import type { TestResult, UnitTestSummary } from "../api/types";
import { X, ExternalLink } from "lucide-react";

interface Props {
  pipeline: Pipeline;
  onClose: () => void;
}

const statusIcons: Record<string, string> = {
  building: "🔨", deploying: "🚀", running: "🔄",
  passed: "✅", failed: "❌", error: "⚠️", destroyed: "🗑️",
};

export default function PipelineDetail({ pipeline, onClose }: Props) {
  const [results, setResults] = useState<TestResult[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [unitResults, setUnitResults] = useState<UnitTestSummary | null>(null);
  const [activeTab, setActiveTab] = useState<"info" | "unit" | "results" | "logs">("info");
  const logEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (pipeline.run_id) {
      getRunResults(pipeline.run_id).then(setResults).catch(console.error);
    }
    // 获取 Pipeline 日志（从 /api/pipelines/{id}/logs）
    getPipelineLogs(pipeline.id)
      .then((res) => {
        const logs = res.logs || "";
        setLogs(logs ? logs.split("\n") : []);
      })
      .catch(console.error);
    getPipelineUnitResults(pipeline.id).then(setUnitResults).catch(console.error);
  }, [pipeline.run_id, pipeline.id]);

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
        {(["info", "unit", "results", "logs"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab === "info" ? "基本信息"
              : tab === "unit" ? `单元测试${unitResults && unitResults.status !== "not_run" ? ` (${unitResults.total})` : ""}`
              : tab === "results" ? `集成测试 (${pipeline.test_total})`
              : "执行日志"}
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
            {pipeline.target_url && (
              <div>
                <span className="text-gray-500">Target URL:</span>{" "}
                <a href={pipeline.target_url} target="_blank" rel="noopener noreferrer"
                   className="text-blue-600 hover:underline">{pipeline.target_url}</a>
              </div>
            )}
            {pipeline.build_info && (pipeline.build_info as any).jenkins_url && (
              <div>
                <span className="text-gray-500">Jenkins:</span>{" "}
                <a href={(pipeline.build_info as any).jenkins_url} target="_blank"
                   rel="noopener noreferrer" className="text-blue-600 hover:underline">
                  Build #{(pipeline.build_info as any).build_number || "?"}
                </a>
              </div>
            )}
            <div><span className="text-gray-500">镜像:</span> <code className="text-xs">{pipeline.docker_image}</code></div>
            {(() => {
              const uP = unitResults?.passed ?? 0, uF = unitResults?.failed ?? 0, uS = unitResults?.skipped ?? 0;
              const iP = pipeline.test_passed, iF = pipeline.test_failed, iS = pipeline.test_skipped;
              const total = uP + uF + uS + iP + iF + iS;
              const rate = total > 0 ? (((uP + iP) / total) * 100).toFixed(1) : "-";
              return (
                <div className="space-y-1">
                  <div><span className="text-gray-500">测试总计:</span> {uP + iP}✅ {uF + iF}❌ {uS + iS}⏭️ ({rate}%)</div>
                  <div className="pl-2 text-xs text-gray-400">单元: {uP}✅ {uF}❌ {uS}⏭️</div>
                  <div className="pl-2 text-xs text-gray-400">集成: {iP}✅ {iF}❌ {iS}⏭️</div>
                </div>
              );
            })()}
          </div>
        </div>
      )}

      {activeTab === "unit" && (
        <div>
          {!unitResults || unitResults.status === "not_run" ? (
            <div className="text-center py-12 text-gray-400">
              <div className="text-3xl mb-2">⏸️</div>
              <div>未运行单元测试</div>
            </div>
          ) : unitResults.status === "running" ? (
            <div className="text-center py-12 text-blue-500">
              <div className="text-3xl mb-2 animate-spin">🔄</div>
              <div>单元测试运行中...</div>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-4 mb-4 text-sm">
                <span className={`font-medium ${unitResults.failed > 0 ? "text-red-600" : "text-green-600"}`}>
                  {unitResults.failed > 0 ? "❌ 失败" : "✅ 通过"}
                </span>
                <span>{unitResults.passed}✅ {unitResults.failed}❌ {unitResults.skipped}⏭️</span>
                <span className="text-gray-400">{unitResults.duration_ms}ms</span>
              </div>
              {unitResults.results.length > 0 ? (
              <div className="max-h-96 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left">
                      <th className="py-2">状态</th>
                      <th className="py-2">Describe</th>
                      <th className="py-2">用例</th>
                      <th className="py-2">耗时</th>
                    </tr>
                  </thead>
                  <tbody>
                    {unitResults.results.map((r) => (
                      <tr key={r.id} className="border-b">
                        <td className="py-1.5">
                          {r.status === "passed" ? "✅" : r.status === "failed" ? "❌" : r.status === "skipped" ? "⏭️" : "⚠️"}
                        </td>
                        <td className="py-1.5 text-gray-500 text-xs">{r.classname}</td>
                        <td className="py-1.5 font-mono text-xs">
                          {r.name}
                          {r.failure_message && (
                            <div className="text-red-500 mt-1 text-xs font-normal whitespace-pre-wrap">{r.failure_message}</div>
                          )}
                        </td>
                        <td className="py-1.5">{r.duration_ms}ms</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              ) : (
                <div className="text-center py-6 text-sm text-gray-400">
                  测试已完成 ({unitResults.total} 条)，但逐条结果未存储。下次 Pipeline 运行后将自动保存。
                </div>
              )}
            </>
          )}
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
