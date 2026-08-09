import { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import { listRuns } from "../api/runs";
import type { TestRun } from "../api/types";

const statusBadge: Record<string, string> = {
  passed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  running: "bg-blue-100 text-blue-700",
  pending: "bg-gray-100 text-gray-700",
  error: "bg-yellow-100 text-yellow-700",
  cancelled: "bg-orange-100 text-orange-700",
};

const triggerLabels: Record<string, { label: string; color: string }> = {
  manual: { label: "手动触发", color: "bg-blue-100 text-blue-700" },
  ci: { label: "Pipeline", color: "bg-purple-100 text-purple-700" },
  api: { label: "API 触发", color: "bg-gray-100 text-gray-700" },
};

export default function Runs() {
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [triggerFilter, setTriggerFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const fetch = () => {
      const params: Record<string, string> = {};
      if (triggerFilter) params.trigger_type = triggerFilter;
      if (statusFilter) params.status = statusFilter;
      listRuns(params).then((data) => {
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
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [triggerFilter, statusFilter]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">运行记录</h1>
        <div className="flex gap-2">
          <select
            value={triggerFilter}
            onChange={(e) => setTriggerFilter(e.target.value)}
            className="text-sm border rounded-lg px-3 py-1.5"
          >
            <option value="">全部来源</option>
            <option value="manual">手动触发</option>
            <option value="ci">Pipeline</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-sm border rounded-lg px-3 py-1.5"
          >
            <option value="">全部状态</option>
            <option value="passed">通过</option>
            <option value="failed">失败</option>
            <option value="running">运行中</option>
            <option value="error">错误</option>
            <option value="cancelled">已取消</option>
          </select>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">ID</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">状态</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">来源</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">信息</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">通过率</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">耗时</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">时间</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {runs.map((run) => {
              const trig = triggerLabels[run.trigger_type] ?? { label: run.trigger_type, color: "bg-gray-100 text-gray-700" };
              return (
                <tr key={run.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link to={`/runs/${run.id}`} className="text-blue-600 hover:underline font-medium">#{run.id}</Link>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusBadge[run.status] ?? ""}`}>{run.status}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${trig.color}`}>{trig.label}</span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {run.trigger_type === "ci" && run.pipeline_id ? (
                      <span>
                        Pipeline #{run.pipeline_id}
                        {run.git_branch && <span className="text-gray-400 ml-1">({run.git_branch})</span>}
                      </span>
                    ) : (
                      <span>
                        {run.trigger_user || "用户"}
                        {run.collection_ids && run.collection_ids.length > 0 && (
                          <span className="text-gray-400 ml-1">({run.collection_ids.length} 个用例集)</span>
                        )}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {run.total > 0 ? (
                      <span className={run.failed > 0 ? "text-red-600" : "text-green-600"}>
                        {((run.passed / run.total) * 100).toFixed(1)}%
                      </span>
                    ) : "-"}
                  </td>
                  <td className="px-4 py-3 text-sm">{(run.duration_ms / 1000).toFixed(1)}s</td>
                  <td className="px-4 py-3 text-sm text-gray-500">{new Date(run.created_at).toLocaleString()}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {runs.length === 0 && (
          <div className="p-8 text-center text-gray-400">暂无运行记录</div>
        )}
      </div>
    </div>
  );
}
