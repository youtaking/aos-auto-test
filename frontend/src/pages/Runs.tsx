import { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import { listRuns, deleteRun, batchDeleteRuns } from "../api/runs";
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
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<{ ids: number[]; label: string } | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchRuns = () => {
    const params: Record<string, string> = {};
    if (triggerFilter) params.trigger_type = triggerFilter;
    if (statusFilter) params.status = statusFilter;
    listRuns(params).then((data) => {
      setRuns(data);
      const hasActive = data.some((r) => r.status === "pending" || r.status === "running");
      if (hasActive && !timerRef.current) {
        timerRef.current = setInterval(fetchRuns, 2000);
      } else if (!hasActive && timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }).catch(console.error);
  };

  useEffect(() => {
    fetchRuns();
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [triggerFilter, statusFilter]);

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    const deletableIds = runs.filter((r) => r.status !== "running").map((r) => r.id);
    if (selected.size === deletableIds.length && deletableIds.length > 0) {
      setSelected(new Set());
    } else {
      setSelected(new Set(deletableIds));
    }
  };

  const handleDelete = async (ids: number[]) => {
    setDeleting(true);
    try {
      if (ids.length === 1) {
        await deleteRun(ids[0]);
      } else {
        await batchDeleteRuns(ids);
      }
      setSelected(new Set());
      fetchRuns();
    } catch (e) {
      console.error("删除失败:", e);
      alert(`删除失败: ${e instanceof Error ? e.message : "未知错误"}`);
    } finally {
      setDeleting(false);
      setConfirmDelete(null);
    }
  };

  const requestDelete = (ids: number[], label: string) => {
    setConfirmDelete({ ids, label });
  };

  const deletableRuns = runs.filter((r) => r.status !== "running");
  const allDeletableSelected = deletableRuns.length > 0 && selected.size === deletableRuns.length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">运行记录</h1>
        <div className="flex gap-2">
          {selected.size > 0 && (
            <button
              onClick={() => requestDelete(Array.from(selected), `选中的 ${selected.size} 条记录`)}
              disabled={deleting}
              className="text-sm bg-red-600 text-white px-3 py-1.5 rounded-lg hover:bg-red-700 disabled:opacity-50"
            >
              删除选中 ({selected.size})
            </button>
          )}
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
              <th className="px-4 py-3 text-left w-10">
                <input
                  type="checkbox"
                  checked={allDeletableSelected}
                  onChange={toggleSelectAll}
                  className="rounded border-gray-300"
                />
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">ID</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">状态</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">来源</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">信息</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">通过率</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">耗时</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">时间</th>
              <th className="px-4 py-3 text-center text-sm font-medium text-gray-500 w-16">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {runs.map((run) => {
              const trig = triggerLabels[run.trigger_type] ?? { label: run.trigger_type, color: "bg-gray-100 text-gray-700" };
              const canDelete = run.status !== "running";
              return (
                <tr key={run.id} className={`hover:bg-gray-50 ${selected.has(run.id) ? "bg-blue-50" : ""}`}>
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selected.has(run.id)}
                      disabled={!canDelete}
                      onChange={() => toggleSelect(run.id)}
                      className="rounded border-gray-300"
                    />
                  </td>
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
                  <td className="px-4 py-3 text-center">
                    {canDelete && (
                      <button
                        onClick={() => requestDelete([run.id], `运行记录 #${run.id}`)}
                        disabled={deleting}
                        className="text-gray-400 hover:text-red-600 transition-colors disabled:opacity-50"
                        title="删除"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {runs.length === 0 && (
          <div className="p-8 text-center text-gray-400">暂无运行记录</div>
        )}
      </div>

      {/* 确认删除弹窗 */}
      {confirmDelete && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="text-lg font-semibold text-gray-900">确认删除</h3>
            <p className="mt-2 text-sm text-gray-600">
              确定要删除{confirmDelete.label}吗？删除后数据无法恢复，关联的测试结果也会一并删除。
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setConfirmDelete(null)}
                disabled={deleting}
                className="px-4 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
              >
                取消
              </button>
              <button
                onClick={() => handleDelete(confirmDelete.ids)}
                disabled={deleting}
                className="px-4 py-2 text-sm rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? "删除中..." : "确认删除"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
