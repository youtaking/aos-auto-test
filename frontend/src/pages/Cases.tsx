import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listProjects, listSuites } from "../api/projects";
import { get } from "../api/client";
import { triggerRun } from "../api/runs";
import type { TestSuite, TestCase } from "../api/types";

export default function Cases() {
  const navigate = useNavigate();
  const [suites, setSuites] = useState<TestSuite[]>([]);
  const [cases, setCases] = useState<TestCase[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [running, setRunning] = useState(false);
  const [headed, setHeaded] = useState(true);
  const [projectId, setProjectId] = useState<number | null>(null);

  useEffect(() => {
    listProjects().then((projs) => {
      if (projs.length > 0) {
        const active = projs.find((p) => p.is_active) ?? projs[0];
        setProjectId(active.id);
        listSuites(active.id).then(setSuites);
      }
    }).catch(console.error);
  }, []);

  useEffect(() => {
    if (suites.length === 0) return;
    Promise.all(
      suites.map((s) => get<TestCase[]>(`/suites/${s.id}/cases`))
    ).then((results) => setCases(results.flat())).catch(console.error);
  }, [suites]);

  const toggleCase = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSuite = (suiteCases: TestCase[]) => {
    const suiteIds = suiteCases.map((c) => c.id);
    const allSelected = suiteIds.every((id) => selectedIds.has(id));
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allSelected) {
        suiteIds.forEach((id) => next.delete(id));
      } else {
        suiteIds.forEach((id) => next.add(id));
      }
      return next;
    });
  };

  const toggleAll = () => {
    const allIds = cases.map((c) => c.id);
    const allSelected = allIds.every((id) => selectedIds.has(id));
    setSelectedIds(allSelected ? new Set() : new Set(allIds));
  };

  const handleRunSelected = async () => {
    if (!projectId || selectedIds.size === 0 || running) return;
    setRunning(true);
    try {
      const run = await triggerRun(projectId, "manual", headed, 0, Array.from(selectedIds));
      navigate(`/runs/${run.id}`);
    } catch (e) {
      console.error(e);
      setRunning(false);
    }
  };

  const selectedCount = selectedIds.size;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">用例管理</h1>
          <p className="text-gray-500 mt-1">共 {cases.length} 个用例，{suites.length} 个套件</p>
        </div>
      </div>

      {/* 浮动操作栏 */}
      {selectedCount > 0 && (
        <div className="sticky top-0 z-10 bg-white rounded-xl shadow-md border border-blue-200 p-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={toggleAll}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              {selectedCount === cases.length ? "取消全选" : "全选"}
            </button>
            <span className="text-sm text-gray-600">
              已选 <span className="font-bold text-blue-600">{selectedCount}</span> 条用例
            </span>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer">
              <input
                type="checkbox"
                checked={headed}
                onChange={(e) => setHeaded(e.target.checked)}
                className="w-4 h-4 rounded"
              />
              显示浏览器
            </label>
            <button
              onClick={handleRunSelected}
              disabled={running}
              className={`px-4 py-2 text-white rounded-lg text-sm font-medium transition-colors ${
                running ? "bg-gray-400 cursor-not-allowed" : "bg-green-600 hover:bg-green-700"
              }`}
            >
              {running ? "正在触发..." : `运行选中 (${selectedCount})`}
            </button>
          </div>
        </div>
      )}

      {suites.map((suite) => {
        const suiteCases = cases.filter((c) => c.suite_id === suite.id);
        const suiteSelectedCount = suiteCases.filter((c) => selectedIds.has(c.id)).length;
        const allSuiteSelected = suiteCases.length > 0 && suiteSelectedCount === suiteCases.length;

        return (
          <div key={suite.id} className="bg-white rounded-xl shadow-sm p-4">
            <div className="flex items-center gap-3 mb-3">
              <input
                type="checkbox"
                checked={allSuiteSelected}
                onChange={() => toggleSuite(suiteCases)}
                className="w-4 h-4 rounded"
              />
              <h2 className="text-lg font-semibold">{suite.name}</h2>
              <span className="text-sm text-gray-400">
                ({suiteSelectedCount}/{suiteCases.length})
              </span>
              <p className="text-sm text-gray-500 ml-auto">{suite.description}</p>
            </div>
            <div className="space-y-1">
              {suiteCases.map((c) => (
                <div
                  key={c.id}
                  className={`flex items-center gap-3 px-3 py-1.5 rounded cursor-pointer transition-colors ${
                    selectedIds.has(c.id) ? "bg-blue-50" : "bg-gray-50 hover:bg-gray-100"
                  }`}
                  onClick={() => toggleCase(c.id)}
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.has(c.id)}
                    onChange={() => toggleCase(c.id)}
                    className="w-4 h-4 rounded"
                    onClick={(e) => e.stopPropagation()}
                  />
                  <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                    c.priority === "P0" ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"
                  }`}>{c.priority}</span>
                  <span className="text-sm">{c.name}</span>
                  <span className="text-xs text-gray-400 ml-auto">{c.function_name}</span>
                </div>
              ))}
              {suiteCases.length === 0 && (
                <p className="text-sm text-gray-400 px-3">暂无用例</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
