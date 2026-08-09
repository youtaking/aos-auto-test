import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listProjects, listSuites, discoverCases } from "../api/projects";
import { get } from "../api/client";
import { triggerRun } from "../api/runs";
import { getCollection, updateCollection, listCollections, createCollection } from "../api/collections";
import { ChevronDown, RefreshCw, FolderOpen } from "lucide-react";
import CollectionManager from "../components/CollectionManager";
import type { TestSuite, TestCase, Collection } from "../api/types";

export default function Cases() {
  const navigate = useNavigate();
  const [suites, setSuites] = useState<TestSuite[]>([]);
  const [cases, setCases] = useState<TestCase[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [running, setRunning] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [headed, setHeaded] = useState(true);
  const [showCollections, setShowCollections] = useState(false);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [runCollectionIds, setRunCollectionIds] = useState<number[]>([]);
  const [showCollectionPicker, setShowCollectionPicker] = useState(false);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [priorityFilters, setPriorityFilters] = useState<Record<string, string>>({});
  const [quickColName, setQuickColName] = useState("");
  const [savingCol, setSavingCol] = useState(false);

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
    listCollections().then(setCollections).catch(console.error);
  }, []);

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

  const toggleAll = (filteredCases?: TestCase[]) => {
    const targetCases = filteredCases ?? cases;
    const allIds = targetCases.map((c) => c.id);
    const allSelected = allIds.length > 0 && allIds.every((id) => selectedIds.has(id));
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allSelected) {
        allIds.forEach((id) => next.delete(id));
      } else {
        allIds.forEach((id) => next.add(id));
      }
      return next;
    });
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

  const handleRunCollection = async () => {
    if (!projectId || runCollectionIds.length === 0 || running) return;
    setRunning(true);
    try {
      const run = await triggerRun(projectId, "manual", headed, 0, [], runCollectionIds);
      navigate(`/runs/${run.id}`);
    } catch (e) {
      console.error(e);
      setRunning(false);
    }
    setShowCollectionPicker(false);
  };

  const handleAddSelectedToCollection = async (collectionId: number, caseIds: number[]) => {
    const col = await getCollection(collectionId);
    const merged = [...new Set([...col.case_ids, ...caseIds])];
    await updateCollection(collectionId, { case_ids: merged });
  };

  const handleQuickCreateCollection = async () => {
    if (!quickColName.trim() || selectedIds.size === 0 || savingCol) return;
    setSavingCol(true);
    try {
      await createCollection({ name: quickColName.trim(), description: "", case_ids: Array.from(selectedIds) });
      setQuickColName("");
      const updated = await listCollections();
      setCollections(updated);
    } catch (e) {
      console.error(e);
    } finally {
      setSavingCol(false);
    }
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
    const pFilter = priorityFilters[sectionKey] || "all";
    const filteredCases = pFilter === "all"
      ? sectionCases
      : sectionCases.filter((c) => c.priority === pFilter);
    const sectionSelected = filteredCases.filter((c) => selectedIds.has(c.id)).length;
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
            {sectionSuites.length} 套件 / {filteredCases.length} 用例
            {pFilter !== "all" && <span className="text-gray-300"> (共 {sectionCases.length})</span>}
            {sectionSelected > 0 && <span className="text-blue-600 ml-2">已选 {sectionSelected}</span>}
          </span>
          <select
            value={pFilter}
            onChange={(e) => {
              e.stopPropagation();
              setPriorityFilters((prev) => ({ ...prev, [sectionKey]: e.target.value }));
            }}
            onClick={(e) => e.stopPropagation()}
            className="ml-auto text-sm border rounded px-2 py-0.5 text-gray-600 cursor-pointer"
          >
            <option value="all">全部优先级</option>
            <option value="P0">P0</option>
            <option value="P1">P1</option>
            <option value="P2">P2</option>
          </select>
          {filteredCases.length > 0 && (
            <button
              onClick={(e) => { e.stopPropagation(); toggleAll(filteredCases); }}
              className="text-sm text-blue-600 hover:text-blue-800 px-2"
            >
              {filteredCases.every((c) => selectedIds.has(c.id)) ? "取消全选" : "全选可见"}
            </button>
          )}
        </div>

        {/* 套件列表 */}
        {!sectionCollapsed && (
          <div className="space-y-2 pl-1">
            {sectionSuites.map((suite) => {
              const suiteKey = `suite-${suite.id}`;
              const allSuiteCases = cases.filter((c) => c.suite_id === suite.id);
              const suiteCases = pFilter === "all"
                ? allSuiteCases
                : allSuiteCases.filter((c) => c.priority === pFilter);
              if (pFilter !== "all" && suiteCases.length === 0) return null;
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
        <div className="flex gap-2 items-center">
              <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer px-3 py-2 border rounded-lg hover:bg-gray-50">
                <input
                  type="checkbox"
                  checked={headed}
                  onChange={(e) => setHeaded(e.target.checked)}
                  className="w-4 h-4 rounded"
                />
                显示浏览器
              </label>
              {collections.length > 0 && (
                <div className="relative">
                  <button
                    onClick={() => setShowCollectionPicker(!showCollectionPicker)}
                    className="flex items-center gap-2 px-4 py-2 border rounded-lg text-sm font-medium hover:bg-gray-50"
                  >
                    运行用例集
                  </button>
                  {showCollectionPicker && (
                    <div className="absolute right-0 top-full mt-1 w-64 bg-white border rounded-lg shadow-lg z-20 p-2">
                      <div className="space-y-1 max-h-48 overflow-y-auto">
                        {collections.map(c => (
                          <label key={c.id} className="flex items-center gap-2 px-2 py-1 rounded hover:bg-gray-50 text-sm cursor-pointer">
                            <input type="checkbox"
                              checked={runCollectionIds.includes(c.id)}
                              onChange={e => {
                                if (e.target.checked) setRunCollectionIds(prev => [...prev, c.id]);
                                else setRunCollectionIds(prev => prev.filter(id => id !== c.id));
                              }} />
                            {c.name} <span className="text-gray-400">({c.case_ids.length})</span>
                          </label>
                        ))}
                      </div>
                      {runCollectionIds.length > 0 && (
                        <button
                          onClick={handleRunCollection}
                          disabled={running}
                          className="w-full mt-2 px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:bg-gray-300"
                        >
                          运行选中的 {runCollectionIds.length} 个集合
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}
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
            <div className="sticky top-0 z-10 bg-white rounded-xl shadow-md border border-blue-200 p-3 flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-3">
                <button onClick={() => toggleAll()} className="text-sm text-blue-600 hover:text-blue-800">
                  {selectedCount === cases.length ? "取消全选" : "全选"}
                </button>
                <span className="text-sm text-gray-600">
                  已选 <span className="font-bold text-blue-600">{selectedCount}</span> 条用例
                </span>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5">
                  <input
                    value={quickColName}
                    onChange={(e) => setQuickColName(e.target.value)}
                    placeholder="测试集名称"
                    className="px-2 py-1.5 border rounded text-sm w-28"
                    onKeyDown={(e) => { if (e.key === "Enter") handleQuickCreateCollection(); }}
                  />
                  <button
                    onClick={handleQuickCreateCollection}
                    disabled={!quickColName.trim() || savingCol}
                    className="px-3 py-1.5 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-700 disabled:bg-gray-300"
                  >
                    {savingCol ? "保存中..." : "存为测试集"}
                  </button>
                </div>
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
