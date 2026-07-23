import { useEffect, useState, useRef } from "react";
import { useParams } from "react-router-dom";
import { getRun, getRunResults } from "../api/runs";
import type { TestRun, TestResult } from "../api/types";

const statusIcon: Record<string, string> = {
  passed: "✅", failed: "❌", skipped: "⏭️", error: "⚠️", running: "🔄", pending: "⏳",
};

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<TestRun | null>(null);
  const [results, setResults] = useState<TestResult[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
    </div>
  );
}
