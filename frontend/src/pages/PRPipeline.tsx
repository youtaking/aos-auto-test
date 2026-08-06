import { useEffect, useState, useRef } from "react";
import { listPipelines } from "../api/pipelines";
import type { Pipeline } from "../api/types";
import PipelineDetail from "../components/PipelineDetail";
import CIConfigModal from "../components/CIConfigModal";
import { Settings, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";

const statusIcons: Record<string, string> = {
  building: "🔨", deploying: "🚀", running: "🔄",
  passed: "✅", failed: "❌", error: "⚠️", destroyed: "🗑️",
};

const statusLabels: Record<string, string> = {
  building: "构建中", deploying: "部署中", running: "测试中",
  passed: "通过", failed: "失败", error: "异常", destroyed: "已销毁",
};

const PAGE_SIZE = 20;

const statusFilters = [
  { key: "", label: "全部" },
  { key: "running", label: "运行中", group: ["building", "deploying", "running"] },
  { key: "passed", label: "通过" },
  { key: "failed", label: "失败" },
  { key: "destroyed", label: "已销毁" },
];

export default function PRPipeline() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [selected, setSelected] = useState<Pipeline | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const wsRef = useRef<WebSocket | null>(null);

  const load = async (p?: number, sf?: string) => {
    const curPage = p ?? page;
    const curStatus = sf ?? statusFilter;
    // "running" 筛选包含多个状态
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

  // 全局 WebSocket 监听
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

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">PR Pipeline</h1>
        <div className="flex gap-2">
          <button onClick={() => setShowConfig(true)} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50">
            <Settings className="w-4 h-4" /> CI 配置
          </button>
          <button onClick={() => load()} disabled={loading} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-50">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> {loading ? "加载中..." : "刷新"}
          </button>
        </div>
      </div>

      {/* Pipeline 详情（展开） */}
      {selected && (
        <PipelineDetail
          pipeline={selected}
          onClose={() => setSelected(null)}
        />
      )}

      {/* 状态筛选 */}
      <div className="flex items-center gap-1">
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
        <span className="ml-auto text-sm text-gray-400">共 {total} 条</span>
      </div>

      {/* Pipeline 列表 */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b text-left">
              <th className="px-4 py-3">PR</th>
              <th className="px-4 py-3">Commit</th>
              <th className="px-4 py-3">分支</th>
              <th className="px-4 py-3">状态</th>
              <th className="px-4 py-3">测试</th>
              <th className="px-4 py-3">耗时</th>
            </tr>
          </thead>
          <tbody>
            {pipelines.map((p) => (
              <tr
                key={p.id}
                onClick={() => setSelected(selected?.id === p.id ? null : p)}
                className={`border-b cursor-pointer hover:bg-blue-50 transition-colors ${
                  selected?.id === p.id ? "bg-blue-50" : ""
                }`}
              >
                <td className="px-4 py-3">
                  <div className="font-medium">#{p.pr_id}</div>
                  <div className="text-xs text-gray-500 truncate max-w-[200px]">{p.pr_title}</div>
                </td>
                <td className="px-4 py-3">
                  <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">{p.commit_sha.slice(0, 8)}</code>
                </td>
                <td className="px-4 py-3 text-gray-600">{p.branch}</td>
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
              </tr>
            ))}
            {pipelines.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                  暂无 Pipeline 记录
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* 分页 */}
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
    </div>
  );
}
