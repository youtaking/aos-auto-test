import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listProjects, listSuites, discoverCases } from "../api/projects";
import { get } from "../api/client";
import { triggerRun } from "../api/runs";
import { getCollection, updateCollection } from "../api/collections";
import { ChevronDown, RefreshCw, FolderOpen } from "lucide-react";
import CollectionManager from "../components/CollectionManager";
import type { TestSuite, TestCase } from "../api/types";

export default function Cases() {
  const navigate = useNavigate();
  const [suites, setSuites] = useState<TestSuite[]>([]);
  const [cases, setCases] = useState<TestCase[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [running, setRunning] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [headed, setHeaded] = useState(true);
  const [showCollections, setShowCollections] = useState(false);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const loadCases = () => {
    listProjects().then((projs) => {
      if (projs.length > 0) {
        const active = projs.find((p) => p.is_active) ?? projs[0];
        setProjectId(active.id);
        listSuites(active.id).then(setSuites);
      }
    }).catch(console.error);
  };

  useEffect(() => { loadCases(); }, []);

  useEffect(() => {
    if (suites.length === 0) return;
    Promise.all(
      suites.map((s) => get<TestCase[]>(`/suites/${s.id}/cases`))
    ).then((results) => setCases(results.flat())).catch(console.error);
  }, [suites]);

  const handleSync = async () => {
    if (syncing) return;
    setSyncing(true);
    try {
      await discoverCases();
      loadCases();
    } catch (e) {
      console.error(e);
    } finally {
      setSyncing(false);
    }
  };

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

  const handleAddSelectedToCollection = async (collectionId: number, caseIds: number[]) => {
    const col = await getCollection(collectionId);
    const merged = [...new Set([...col.case_ids, ...caseIds])];
    await updateCollection(collectionId, { case_ids: merged });
  };

  const toggleCollapse = (key: string) => {
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const selectedCount = selectedIds.size;

  // 按 test_type 分组
  const uiSuites = suites.filter((s) => s.test_type !== "api");
  const apiSuites = suites.filter((s) => s.test_type === "api");
  const uiCases = cases.filter((c) => uiSuites.some((s) => s.id === c.suite_id));
  const apiCases = cases.filter((c) => apiSuites.some((s) => s.id === c.suite_id));

  const renderSuiteSection = (sectionKey: string, title: string, sectionSuites: TestSuite[], sectionCases: TestCase[], accent: string) => {
    const sectionSelected = sectionCases.filter((c) => selectedIds.has(c.id)).length;
    const sectionCollapsed = !!collapsed[sectionKey];

    return (
      <div className="space-y-2">
        {/* 区域标题（可折叠） */}
        <div
          className="flex items-center gap-2 px-1 cursor-pointer select-none"
          onClick={() => toggleCollapse(sectionKey)}
        >
          <ChevronDown className={`w-5 h-5 text-gray-400 transition-transform duration-200 ${sectionCollapsed ? "-rotate-90" : ""}`} />
          <div className={`w-1 h-5 rounded ${accent}`} />
          <h2 className="text-lg font-semibold">{title}</h2>
          <span className="text-sm text-gray-400">
            {sectionSuites.length} 套件 / {sectionCases.length} 用例
            {sectionSelected > 0 && <span className="text-blue-600 ml-2">已选 {sectionSelected}</span>}
          </span>
        </div>

        {/* 套件列表 */}
        {!sectionCollapsed && (
          <div className="space-y-2 pl-1">
            {sectionSuites.map((suite) => {
              const suiteKey = `suite-${suite.id}`;
              const suiteCases = cases.filter((c) => c.suite_id === suite.id);
              const suiteSelectedCount = suiteCases.filter((c) => selectedIds.has(c.id)).length;
              const allSuiteSelected = suiteCases.length > 0 && suiteSelectedCount === suiteCases.length;
              const suiteCollapsed = !!collapsed[suiteKey];

              return (
                <div key={suite.id} className="bg-white rounded-xl shadow-sm overflow-hidden">
                  {/* 套件标题（可折叠） */}
                  <div
                    className="flex items-center gap-3 p-4 cursor-pointer select-none hover:bg-gray-50"
                    onClick={() => toggleCollapse(suiteKey)}
                  >
                    <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform duration-200 ${suiteCollapsed ? "-rotate-90" : ""}`} />
                    <input
                      type="checkbox"
                      checked={allSuiteSelected}
                      onChange={() => toggleSuite(suiteCases)}
                      className="w-4 h-4 rounded"
                      onClick={(e) => e.stopPropagation()}
                    />
                    <h3 className="text-base font-semibold">{suite.name}</h3>
                    <span className="text-sm text-gray-400">
                      ({suiteSelectedCount}/{suiteCases.length})
                    </span>
                    <p className="text-sm text-gray-500 ml-auto">{suite.description}</p>
                  </div>

                  {/* 用例列表 */}
                  {!suiteCollapsed && (
                    <div className="px-4 pb-3 space-y-1">
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
                  )}
                </div>
              );
            })}
            {sectionSuites.length === 0 && (
              <div className="bg-white rounded-xl shadow-sm p-6 text-center text-gray-400">暂无套件</div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">用例管理</h1>
          <p className="text-gray-500 mt-1">
            共 {cases.length} 个用例，{suites.length} 个套件
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowCollections(true)}
            className="flex items-center gap-2 px-4 py-2 border rounded-lg text-sm font-medium hover:bg-gray-50"
          >
            <FolderOpen className="w-4 h-4" /> 用例集
          </button>
          <button
            onClick={handleSync}
            disabled={syncing}
            className={`flex items-center gap-2 px-4 py-2 text-white rounded-lg text-sm font-medium transition-colors ${
              syncing ? "bg-gray-400 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-700"
            }`}
          >
            <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />
            {syncing ? "同步中..." : "重新扫描"}
          </button>
        </div>
      </div>

      {/* 浮动操作栏 */}
      {selectedCount > 0 && (
        <div className="sticky top-0 z-10 bg-white rounded-xl shadow-md border border-blue-200 p-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={toggleAll} className="text-sm text-blue-600 hover:text-blue-800">
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

      {/* UI 测试 */}
      {renderSuiteSection("section-ui", "UI 测试", uiSuites, uiCases, "bg-blue-500")}

      {/* Web API 测试 */}
      {renderSuiteSection("section-api", "Web API 测试", apiSuites, apiCases, "bg-orange-500")}

      {showCollections && (
        <CollectionManager
          selectedCaseIds={Array.from(selectedIds)}
          onAddSelectedToCollection={handleAddSelectedToCollection}
          onClose={() => setShowCollections(false)}
        />
      )}
    </div>
  );
}
