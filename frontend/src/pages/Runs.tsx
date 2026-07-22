import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listRuns } from "../api/runs";
import type { TestRun } from "../api/types";

const statusBadge: Record<string, string> = {
  passed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  running: "bg-blue-100 text-blue-700",
  pending: "bg-gray-100 text-gray-700",
  error: "bg-yellow-100 text-yellow-700",
};

export default function Runs() {
  const [runs, setRuns] = useState<TestRun[]>([]);

  useEffect(() => {
    listRuns().then(setRuns).catch(console.error);
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">运行记录</h1>
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">ID</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">状态</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">触发方式</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">通过率</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">耗时</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">时间</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {runs.map((run) => (
              <tr key={run.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <Link to={`/runs/${run.id}`} className="text-blue-600 hover:underline">#{run.id}</Link>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusBadge[run.status] ?? ""}`}>{run.status}</span>
                </td>
                <td className="px-4 py-3 text-sm">{run.trigger_type}</td>
                <td className="px-4 py-3 text-sm">{run.total > 0 ? `${((run.passed / run.total) * 100).toFixed(1)}%` : "-"}</td>
                <td className="px-4 py-3 text-sm">{(run.duration_ms / 1000).toFixed(1)}s</td>
                <td className="px-4 py-3 text-sm">{new Date(run.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
