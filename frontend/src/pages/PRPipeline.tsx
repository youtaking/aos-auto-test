import { useEffect, useState, useRef } from "react";
import { listPipelines, rerunPipeline, destroyPipeline, cancelPipeline } from "../api/pipelines";
import { listSlots } from "../api/slots";
import type { Pipeline, EnvironmentSlot } from "../api/types";
import SlotCard from "../components/SlotCard";
import PipelineDetail from "../components/PipelineDetail";
import CIConfigModal from "../components/CIConfigModal";
import { Settings, RefreshCw } from "lucide-react";

const statusIcons: Record<string, string> = {
  queued: "⏳", building: "🔨", deploying: "🚀", running: "🔄",
  passed: "✅", failed: "❌", error: "⚠️", destroyed: "🗑️",
};

const statusLabels: Record<string, string> = {
  queued: "等待中", building: "构建中", deploying: "部署中", running: "测试中",
  passed: "通过", failed: "失败", error: "异常", destroyed: "已销毁",
};

export default function PRPipeline() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [slots, setSlots] = useState<EnvironmentSlot[]>([]);
  const [selected, setSelected] = useState<Pipeline | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const [loading, setLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const load = async () => {
    const start = Date.now();
    setLoading(true);
    try {
      const [p, s] = await Promise.all([
        listPipelines({ page_size: 50 }),
        listSlots(),
      ]);
      setPipelines(p);
      setSlots(s);
    } catch (e) {
      console.error(e);
    } finally {
      const elapsed = Date.now() - start;
      if (elapsed < 600) await new Promise(r => setTimeout(r, 600 - elapsed));
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  // 全局 WebSocket 监听
  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${window.location.host}/ws/global`);
    wsRef.current = ws;
    ws.onmessage = () => { load(); };
    return () => { ws.close(); wsRef.current = null; };
  }, []);

  const handleRerun = async (caseIds?: number[]) => {
    if (!selected) return;
    await rerunPipeline(selected.id, caseIds);
    load();
  };

  const handleDestroy = async () => {
    if (!selected) return;
    if (!confirm("确定销毁此环境？")) return;
    await destroyPipeline(selected.id);
    setSelected(null);
    load();
  };

  const handleCancel = async () => {
    if (!selected) return;
    await cancelPipeline(selected.id);
    load();
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">PR Pipeline</h1>
        <div className="flex gap-2">
          <button onClick={() => setShowConfig(true)} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50">
            <Settings className="w-4 h-4" /> CI 配置
          </button>
          <button onClick={load} disabled={loading} className="flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-50">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> {loading ? "加载中..." : "刷新"}
          </button>
        </div>
      </div>

      {/* Slot 状态栏 */}
      <div className="grid grid-cols-3 gap-4">
        {slots.map((s) => (
          <SlotCard key={s.id} slot={s} />
        ))}
      </div>

      {/* Pipeline 详情（展开） */}
      {selected && (
        <PipelineDetail
          pipeline={selected}
          onClose={() => setSelected(null)}
          onRerun={handleRerun}
          onDestroy={handleDestroy}
        />
      )}

      {/* Pipeline 列表 */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b text-left">
              <th className="px-4 py-3">PR</th>
              <th className="px-4 py-3">Commit</th>
              <th className="px-4 py-3">分支</th>
              <th className="px-4 py-3">Slot</th>
              <th className="px-4 py-3">状态</th>
              <th className="px-4 py-3">测试</th>
              <th className="px-4 py-3">耗时</th>
            </tr>
          </thead>
          <tbody>
            {pipelines.map((p) => (
              <tr
                key={p.id}
                onClick={() => setSelected(p)}
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
                <td className="px-4 py-3">{p.slot_name || (p.queue_position > 0 ? `队列 #${p.queue_position}` : "-")}</td>
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
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  暂无 Pipeline 记录
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {showConfig && <CIConfigModal onClose={() => { setShowConfig(false); load(); }} />}
    </div>
  );
}
