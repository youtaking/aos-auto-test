import { useEffect, useState, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { listPipelines, deletePipeline, batchDeletePipelines } from "../api/pipelines";
import type { Pipeline } from "../api/types";
import PipelineDetail from "../components/PipelineDetail";
import CIConfigModal from "../components/CIConfigModal";
import { Settings, RefreshCw, ChevronLeft, ChevronRight, Trash2, ExternalLink } from "lucide-react";

const statusIcons: Record<string, string> = {
  building: "🔨", deploying: "🚀", running: "🔄",
  passed: "✅", failed: "❌", error: "⚠️", destroyed: "🗑️",
};

const statusLabels: Record<string, string> = {
  building: "构建中", deploying: "部署中", running: "测试中",
  passed: "通过", failed: "失败", error: "异常", destroyed: "已销毁",
};

const PAGE_SIZE = 20;

const activeStatuses = new Set(["building", "deploying", "running"]);

const getJenkinsInfo = (p: Pipeline) => {
  const bi = p.build_info as Record<string, unknown> | null;
  const url = (bi?.jenkins_url as string) || "";
  const num = (bi?.build_number as number) || 0;
  return { url, num };
};

const statusFilters = [
  { key: "", label: "全部" },
  { key: "running", label: "运行中", group: ["building", "deploying", "running"] },
  { key: "passed", label: "通过" },
  { key: "failed", label: "失败" },
  { key: "destroyed", label: "已销毁" },
];

const typeFilters = [
  { key: "", label: "全部类型" },
  { key: "pr", label: "PR" },
  { key: "staging", label: "Staging" },
];

export default function PRPipeline() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [selected, setSelected] = useState<Pipeline | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<{ ids: number[]; label: string } | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const highlightedRef = useRef<number | null>(null);

  const load = async (p?: number, sf?: string) => {
    const curPage = p ?? page;
    const curStatus = sf ?? statusFilter;
    const statusParam = curStatus === "running"
      ? "building,deploying,running"
      : curStatus || undefined;
    const start = Date.now();
    setLoading(true);
    try {
      const res = await listPipelines({
        page: curPage,
        page_size: PAGE_SIZE,
        status: statusParam,
      });
      setPipelines(res.items);
      setTotal(res.total);
    } catch (e) {
      console.error(e);
    } finally {
      const elapsed = Date.now() - start;
      if (elapsed < 400) await new Promise(r => setTimeout(r, 400 - elapsed));
      setLoading(false);
    }
  };

  useEffect(() => { load(1, ""); }, []);

  // 从 URL ?highlight=ID 自动选中对应 Pipeline
  useEffect(() => {
    const highlightId = searchParams.get("highlight");
    if (!highlightId || !pipelines.length) return;
    const id = Number(highlightId);
    const target = pipelines.find(p => p.id === id);
    if (target) {
      setSelected(target);
      highlightedRef.current = id;
      // 清除 URL 参数，避免刷新重复选中
      const next = new URLSearchParams(searchParams);
      next.delete("highlight");
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, pipelines]);

  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${window.location.host}/ws/global`);
    wsRef.current = ws;
    ws.onmessage = () => { load(); };
    return () => { ws.close(); wsRef.current = null; };
  }, [page, statusFilter]);

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    load(newPage);
  };

  const handleStatusFilter = (sf: string) => {
    setStatusFilter(sf);
    setPage(1);
    setSelected(null);
    setCheckedIds(new Set());
    load(1, sf);
  };

  const calcDuration = (p: Pipeline) => {
    if (!p.run_id) return "-";
    const start = new Date(p.created_at).getTime();
    const end = p.status === "destroyed" || p.status === "passed" || p.status === "failed"
      ? new Date(p.updated_at).getTime()
      : Date.now();
    const mins = Math.floor((end - start) / 60000);
    const secs = Math.floor(((end - start) % 60000) / 1000);
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };

  const toggleCheck = (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    setCheckedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleCheckAll = () => {
    const allIds = filteredPipelines.map((p) => p.id);
    if (checkedIds.size === allIds.length && allIds.length > 0) {
      setCheckedIds(new Set());
    } else {
      setCheckedIds(new Set(allIds));
    }
  };

  const requestDelete = (e: React.MouseEvent, ids: number[], label: string) => {
    e.stopPropagation();
    setConfirmDelete({ ids, label });
  };

  const handleDelete = async (ids: number[]) => {
    setDeleting(true);
    try {
      if (ids.length === 1) {
        await deletePipeline(ids[0]);
      } else {
        await batchDeletePipelines(ids);
      }
      setCheckedIds(new Set());
      load();
    } catch (e) {
      console.error("删除失败:", e);
      alert(`删除失败: ${e instanceof Error ? e.message : "未知错误"}`);
    } finally {
      setDeleting(false);
      setConfirmDelete(null);
    }
  };

  const filteredPipelines = typeFilter
    ? pipelines.filter(p => typeFilter === "staging" ? p.branch === "staging" : p.branch !== "staging")
    : pipelines;

  const allInPage = filteredPipelines.map((p) => p.id);
  const allDeletableChecked = allInPage.length > 0 && checkedIds.size === allInPage.length;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">PR Pipeline</h1>
        <div className="flex gap-2">
          {checkedIds.size > 0 && (
            <button
              onClick={(e) => requestDelete(e, Array.from(checkedIds), `选中的 ${checkedIds.size} 条记录`)}
              disabled={deleting}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
            >
              <Trash2 className="w-4 h-4" /> 删除选中 ({checkedIds.size})
            </button>
          )}
          <button onClick={() => setShowConfig(true)} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50">
            <Settings className="w-4 h-4" /> CI 配置
          </button>
          <button onClick={() => load()} disabled={loading} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-50">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> {loading ? "加载中..." : "刷新"}
          </button>
        </div>
      </div>

      {selected && (
        <PipelineDetail
          pipeline={selected}
          onClose={() => setSelected(null)}
        />
      )}

      <div className="flex items-center gap-1 flex-wrap">
        {statusFilters.map((f) => (
          <button
            key={f.key}
            onClick={() => handleStatusFilter(f.key)}
            className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
              statusFilter === f.key
                ? "bg-blue-600 text-white"
                : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            {f.label}
          </button>
        ))}
        <div className="flex items-center gap-1 ml-4 pl-4 border-l">
          {typeFilters.map((f) => (
            <button
              key={f.key}
              onClick={() => setTypeFilter(f.key)}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                typeFilter === f.key
                  ? "bg-purple-600 text-white"
                  : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <span className="ml-auto text-sm text-gray-400">共 {total} 条</span>
      </div>

      {(() => {
        return (
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b text-left">
                <th className="px-4 py-3 w-10">
                  <input
                    type="checkbox"
                    checked={allDeletableChecked}
                    onChange={toggleCheckAll}
                    className="rounded border-gray-300"
                  />
                </th>
                <th className="px-4 py-3 w-16">ID</th>
                <th className="px-4 py-3">PR</th>
                <th className="px-4 py-3">Commit</th>
                <th className="px-4 py-3">分支</th>
                <th className="px-4 py-3">状态</th>
                <th className="px-4 py-3">测试</th>
                <th className="px-4 py-3">耗时</th>
                <th className="px-4 py-3">Jenkins</th>
                <th className="px-4 py-3 w-16 text-center">操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredPipelines.map((p) => {
                return (
                <tr
                  key={p.id}
                  onClick={() => setSelected(selected?.id === p.id ? null : p)}
                  className={`border-b cursor-pointer hover:bg-blue-50 transition-colors ${
                    selected?.id === p.id ? "bg-blue-50" : ""
                  } ${checkedIds.has(p.id) ? "bg-red-50" : ""}`}
                >
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={checkedIds.has(p.id)}
                      onChange={() => {}}
                      onClick={(e) => toggleCheck(e, p.id)}
                      className="rounded border-gray-300"
                    />
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs text-gray-500 font-mono">#{p.id}</span>
                  </td>
                  <td className="px-4 py-3">
                    {p.branch === "staging" ? (
                      <div>
                        <div className="font-medium text-purple-600">Staging</div>
                        <div className="text-xs text-gray-500 truncate max-w-[200px]">{p.pr_title}</div>
                      </div>
                    ) : (
                      <div>
                        <div className="font-medium">#{p.pr_id}</div>
                        <div className="text-xs text-gray-500 truncate max-w-[200px]">{p.pr_title}</div>
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">{p.commit_sha.slice(0, 8)}</code>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                      p.branch === "staging" ? "bg-purple-100 text-purple-700" : "text-gray-600"
                    }`}>
                      {p.branch}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1">
                      {statusIcons[p.status]} {statusLabels[p.status]}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {p.test_total > 0 ? (
                      <span className="text-xs">
                        {p.test_passed}✅ {p.test_failed}❌ {p.test_skipped}⏭️
                      </span>
                    ) : "-"}
                  </td>
                  <td className="px-4 py-3 text-gray-500">{calcDuration(p)}</td>
                  <td className="px-4 py-3">
                    {(() => {
                      const { url, num } = getJenkinsInfo(p);
                      if (!url || !num) return <span className="text-gray-300">-</span>;
                      return (
                        <a
                          href={url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 hover:underline"
                        >
                          Build #{num} <ExternalLink className="w-3 h-3" />
                        </a>
                      );
                    })()}
                  </td>
                  <td className="px-4 py-3 text-center">
                      <button
                        onClick={(e) => requestDelete(e, [p.id], `Pipeline #${p.id}`)}
                        disabled={deleting}
                        className="text-gray-400 hover:text-red-600 transition-colors disabled:opacity-50"
                        title="删除"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                  </td>
                </tr>
                );
              })}
              {filteredPipelines.length === 0 && (
                <tr>
                  <td colSpan={10} className="px-4 py-8 text-center text-gray-400">
                    暂无 Pipeline 记录
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        );
      })()}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => handlePageChange(page - 1)}
            disabled={page <= 1}
            className="p-1.5 border rounded-lg hover:bg-gray-50 disabled:opacity-30"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
            <button
              key={p}
              onClick={() => handlePageChange(p)}
              className={`w-8 h-8 text-sm rounded-lg transition-colors ${
                p === page ? "bg-blue-600 text-white" : "hover:bg-gray-100"
              }`}
            >
              {p}
            </button>
          ))}
          <button
            onClick={() => handlePageChange(page + 1)}
            disabled={page >= totalPages}
            className="p-1.5 border rounded-lg hover:bg-gray-50 disabled:opacity-30"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {showConfig && <CIConfigModal onClose={() => { setShowConfig(false); load(); }} />}

      {/* 确认删除弹窗 */}
      {confirmDelete && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="text-lg font-semibold text-gray-900">确认删除</h3>
            <p className="mt-2 text-sm text-gray-600">
              确定要删除{confirmDelete.label}吗？删除后数据无法恢复。
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
