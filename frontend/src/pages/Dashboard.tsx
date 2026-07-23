import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getSummary, getTrend } from "../api/dashboard";
import { triggerRun } from "../api/runs";
import { listProjects } from "../api/projects";
import type { DashboardSummary, TrendItem, Project } from "../api/types";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

export default function Dashboard() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [trend, setTrend] = useState<TrendItem[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [running, setRunning] = useState(false);
  const [headed, setHeaded] = useState(true);
  const [stepDelay, setStepDelay] = useState(0);

  useEffect(() => {
    getSummary().then(setSummary).catch(console.error);
    getTrend().then(setTrend).catch(console.error);
    listProjects().then(setProjects).catch(console.error);
  }, []);

  const handleRunAll = async () => {
    const activeProject = projects.find((p) => p.is_active) ?? projects[0];
    if (!activeProject || running) return;
    setRunning(true);
    try {
      const run = await triggerRun(activeProject.id, "manual", headed, stepDelay);
      navigate(`/runs/${run.id}`);
    } catch (e) {
      console.error(e);
      setRunning(false);
    }
  };

  const statusColor = summary?.latest_run_status === "passed" ? "bg-green-500" : "bg-red-500";

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">总览</h1>
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="text-sm text-gray-500">项目状态</div>
          <div className="flex items-center gap-2 mt-2">
            <div className={`w-4 h-4 rounded-full ${summary?.latest_run_status ? statusColor : "bg-gray-300"}`} />
            <span className="text-lg font-semibold">
              {summary?.latest_run_status === "passed" ? "正常" : summary?.latest_run_status === "failed" ? "异常" : "未运行"}
            </span>
          </div>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="text-sm text-gray-500">通过率</div>
          <div className="text-2xl font-bold mt-2">{summary?.pass_rate ?? 0}%</div>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="text-sm text-gray-500">用例总数</div>
          <div className="text-2xl font-bold mt-2">{summary?.total_cases ?? 0}</div>
        </div>
        <div className="bg-white rounded-xl p-6 shadow-sm">
          <div className="text-sm text-gray-500">运行次数</div>
          <div className="text-2xl font-bold mt-2">{summary?.total_runs ?? 0}</div>
        </div>
      </div>
      <div className="bg-white rounded-xl p-6 shadow-sm">
        <h2 className="text-lg font-semibold mb-4">运行趋势</h2>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={trend}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="created_at" tickFormatter={(v) => new Date(v).toLocaleDateString()} />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="pass_rate" stroke="#22c55e" name="通过率(%)" strokeWidth={2} />
            <Line type="monotone" dataKey="failed" stroke="#ef4444" name="失败数" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="flex items-center gap-4 flex-wrap">
        <button
          onClick={handleRunAll}
          disabled={running}
          className={`px-4 py-2 text-white rounded-lg transition-colors ${
            running ? "bg-gray-400 cursor-not-allowed" : "bg-green-600 hover:bg-green-700"
          }`}
        >
          {running ? "正在触发..." : "运行全部测试"}
        </button>
        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
          <input
            type="checkbox"
            checked={headed}
            onChange={(e) => setHeaded(e.target.checked)}
            className="w-4 h-4 rounded"
          />
          显示浏览器窗口
        </label>
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <span>操作延迟:</span>
          <input
            type="range"
            min={0}
            max={5}
            step={0.5}
            value={stepDelay}
            onChange={(e) => setStepDelay(Number(e.target.value))}
            className="w-28"
          />
          <span className="w-8 text-center font-mono">{stepDelay}s</span>
        </div>
      </div>
    </div>
  );
}
