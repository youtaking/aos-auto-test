import { useEffect, useState } from "react";
import {
  ChevronDown, FileCode, TestTube, Play, RefreshCw,
  CheckCircle2, XCircle, MinusCircle, Save, FolderOpen, Settings,
  CheckSquare,
} from "lucide-react";
import { listUnitTests, runUnitTests, discoverUnitTests } from "../api/unitTests";
import { listSettings, updateSetting } from "../api/settings";
import type { UnitTestFile, UnitTestRunResult } from "../api/unitTests";

export default function UnitTests() {
  const [files, setFiles] = useState<UnitTestFile[]>([]);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<UnitTestRunResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 源码路径配置
  const [showConfig, setShowConfig] = useState(false);
  const [fenixPath, setFenixPath] = useState("");
  const [savingPath, setSavingPath] = useState(false);

  // 选择运行
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const load = () => {
    setLoading(true);
    discoverUnitTests()
      .then(() => listUnitTests())
      .then(setFiles)
      .catch(console.error)
      .finally(() => setLoading(false));
    listSettings()
      .then((items) => {
        const fp = items.find((s) => s.key === "fenix_source_path");
        if (fp) setFenixPath(fp.value);
      })
      .catch(console.error);
  };

  useEffect(() => { load(); }, []);

  const handleRun = async () => {
    if (running) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const ids = selectedIds.size > 0 ? Array.from(selectedIds) : undefined;
      const r = await runUnitTests(ids);
      setResult(r);
    } catch (e: any) {
      setError(e.message || "运行失败");
    } finally {
      setRunning(false);
    }
  };

  const handleSavePath = async () => {
    setSavingPath(true);
    try {
      await updateSetting("fenix_source_path", fenixPath);
      setShowConfig(false);
    } catch (e) {
      console.error(e);
    } finally {
      setSavingPath(false);
    }
  };

  const toggle = (key: string) => {
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleCase = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSuite = (testIds: number[]) => {
    const allSelected = testIds.every((id) => selectedIds.has(id));
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allSelected) testIds.forEach((id) => next.delete(id));
      else testIds.forEach((id) => next.add(id));
      return next;
    });
  };

  const toggleAll = () => {
    const allIds = files.flatMap((f) => f.describes.flatMap((d) => d.tests.map((t) => t.id)));
    const allSelected = allIds.length > 0 && allIds.every((id) => selectedIds.has(id));
    setSelectedIds(allSelected ? new Set() : new Set(allIds));
  };

  const toggleFile = (file: UnitTestFile) => {
    const fileIds = file.describes.flatMap((d) => d.tests.map((t) => t.id));
    const allSelected = fileIds.every((id) => selectedIds.has(id));
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allSelected) fileIds.forEach((id) => next.delete(id));
      else fileIds.forEach((id) => next.add(id));
      return next;
    });
  };

  const totalTests = files.reduce(
    (sum, f) => sum + f.describes.reduce((s, d) => s + d.tests.length, 0),
    0
  );

  const getTestStatus = (testName: string): "passed" | "failed" | "skipped" | null => {
    if (!result) return null;
    const t = result.tests.find((t) => t.name === testName);
    return t?.status ?? null;
  };

  const StatusIcon = ({ status }: { status: string | null }) => {
    if (status === "passed") return <CheckCircle2 className="w-3.5 h-3.5 text-green-500 shrink-0" />;
    if (status === "failed") return <XCircle className="w-3.5 h-3.5 text-red-500 shrink-0" />;
    if (status === "skipped") return <MinusCircle className="w-3.5 h-3.5 text-yellow-500 shrink-0" />;
    return <TestTube className="w-3 h-3 text-gray-400 shrink-0" />;
  };

  const selectedCount = selectedIds.size;

  return (
    <div className="space-y-6">
      {/* 页头 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">单元测试</h1>
          <p className="text-gray-500 mt-1">
            {loading ? "加载中..." : `${files.length} 个测试文件 / ${totalTests} 个用例`}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowConfig(!showConfig)}
            className="flex items-center gap-2 px-4 py-2 border rounded-lg text-sm font-medium hover:bg-gray-50"
          >
            <Settings className="w-4 h-4" />
            源码路径
          </button>
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 border rounded-lg text-sm font-medium hover:bg-gray-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            刷新
          </button>
          <button
            onClick={toggleAll}
            className="flex items-center gap-2 px-4 py-2 border rounded-lg text-sm font-medium hover:bg-gray-50"
          >
            <CheckSquare className="w-4 h-4" />
            {selectedCount === totalTests && totalTests > 0 ? "取消全选" : "全选"}
          </button>
          <button
            onClick={handleRun}
            disabled={running}
            className={`flex items-center gap-2 px-5 py-2 text-white rounded-lg text-sm font-medium transition-colors ${
              running ? "bg-gray-400 cursor-not-allowed" : "bg-green-600 hover:bg-green-700"
            }`}
          >
            <Play className={`w-4 h-4 ${running ? "animate-pulse" : ""}`} />
            {running ? "运行中..." : selectedCount > 0 ? `运行选中 (${selectedCount})` : "全部运行"}
          </button>
        </div>
      </div>

      {/* 源码路径配置 */}
      {showConfig && (
        <div className="bg-white rounded-xl shadow-sm p-5 border border-blue-200 space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
            <FolderOpen className="w-4 h-4 text-blue-500" />
            FenixAgent 源码路径
          </div>
          <p className="text-xs text-gray-500">
            FenixAgent 源码 src 目录的绝对路径，用于解析 <code className="bg-gray-100 px-1 rounded">@fenix/*</code> 导入。
            Jenkins Pipeline 也会读取此路径。
          </p>
          <div className="flex gap-2">
            <input
              value={fenixPath}
              onChange={(e) => setFenixPath(e.target.value)}
              placeholder="如：D:\chxu\AI中台\Code\FenixAgent\src"
              className="px-3 py-2 border rounded-lg flex-1 font-mono text-sm"
            />
            <button
              onClick={handleSavePath}
              disabled={savingPath}
              className={`flex items-center gap-1.5 px-4 py-2 text-white rounded-lg text-sm font-medium ${
                savingPath ? "bg-gray-400" : "bg-blue-600 hover:bg-blue-700"
              }`}
            >
              <Save className="w-4 h-4" />
              {savingPath ? "保存中..." : "保存"}
            </button>
          </div>
          {fenixPath && (
            <p className="text-xs text-gray-400">
              本地开发命令：<code className="bg-gray-100 px-1 rounded">node setup.js {fenixPath}</code>
            </p>
          )}
        </div>
      )}

      {/* 结果摘要 */}
      {result && (
        <div className={`rounded-xl p-4 border ${result.failed > 0 ? "bg-red-50 border-red-200" : "bg-green-50 border-green-200"}`}>
          <div className="flex items-center gap-6 text-sm">
            <span className="font-semibold text-lg">
              {result.failed === 0 ? "全部通过" : `${result.failed} 个失败`}
            </span>
            <span className="text-gray-600">
              共 {result.total} | <span className="text-green-600">{result.passed} 通过</span> | <span className="text-red-600">{result.failed} 失败</span> | <span className="text-yellow-600">{result.skipped} 跳过</span>
            </span>
            <span className="text-gray-400 ml-auto">{result.duration_ms}ms</span>
          </div>
          {result.failed > 0 && (
            <div className="mt-3 space-y-2">
              {result.tests
                .filter((t) => t.status === "failed")
                .map((t, i) => (
                  <div key={i} className="bg-white rounded-lg p-3 border border-red-100 text-sm">
                    <div className="font-medium text-red-700">{t.classname} › {t.name}</div>
                    {t.failure_message && (
                      <pre className="mt-1 text-xs text-gray-600 whitespace-pre-wrap">{t.failure_message}</pre>
                    )}
                  </div>
                ))}
            </div>
          )}
        </div>
      )}

      {/* 错误 */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* 选择操作栏 */}
      {selectedCount > 0 && (
        <div className="sticky top-0 z-10 bg-white rounded-xl shadow-md border border-blue-200 p-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={toggleAll} className="text-sm text-blue-600 hover:text-blue-800">
              {selectedCount === totalTests ? "取消全选" : "全选"}
            </button>
            <span className="text-sm text-gray-600">
              已选 <span className="font-bold text-blue-600">{selectedCount}</span> 个用例
            </span>
          </div>
          <button
            onClick={() => setSelectedIds(new Set())}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            清除选择
          </button>
        </div>
      )}

      {/* 测试树 */}
      {!loading && files.length === 0 && (
        <div className="bg-white rounded-xl shadow-sm p-8 text-center text-gray-400">
          暂无单元测试用例
        </div>
      )}

      {files.map((file) => {
        const fileKey = `file-${file.file_path}`;
        const fileCollapsed = !!collapsed[fileKey];
        const fileTestCount = file.describes.reduce((s, d) => s + d.tests.length, 0);
        const fileIds = file.describes.flatMap((d) => d.tests.map((t) => t.id));
        const allFileSelected = fileIds.length > 0 && fileIds.every((id) => selectedIds.has(id));

        let filePassed = 0, fileFailed = 0;
        if (result) {
          file.describes.forEach((d) =>
            d.tests.forEach((t) => {
              const s = getTestStatus(t.test_name);
              if (s === "passed") filePassed++;
              if (s === "failed") fileFailed++;
            })
          );
        }

        return (
          <div key={file.file_path} className="bg-white rounded-xl shadow-sm overflow-hidden">
            <div
              className="flex items-center gap-3 p-4 cursor-pointer select-none hover:bg-gray-50"
              onClick={() => toggle(fileKey)}
            >
              <ChevronDown
                className={`w-4 h-4 text-gray-400 transition-transform duration-200 ${fileCollapsed ? "-rotate-90" : ""}`}
              />
              <input
                type="checkbox"
                checked={allFileSelected}
                onChange={() => toggleFile(file)}
                className="w-4 h-4 rounded"
                onClick={(e) => e.stopPropagation()}
              />
              <FileCode className="w-4 h-4 text-blue-500" />
              <span className="text-sm font-medium flex-1">{file.file_path}</span>
              {result && (
                <span className="text-xs">
                  {fileFailed > 0 ? (
                    <span className="text-red-600">{fileFailed} 失败</span>
                  ) : (
                    <span className="text-green-600">{filePassed} 通过</span>
                  )}
                </span>
              )}
              <span className="text-xs text-gray-400">{fileTestCount} tests</span>
            </div>

            {!fileCollapsed && (
              <div className="px-4 pb-3 space-y-2">
                {file.describes.map((describe) => {
                  const dKey = `${fileKey}-${describe.name}`;
                  const dCollapsed = !!collapsed[dKey];
                  const testIds = describe.tests.map((t) => t.id);
                  const allSuiteSelected = testIds.length > 0 && testIds.every((id) => selectedIds.has(id));

                  return (
                    <div key={describe.name} className="pl-4">
                      <div className="flex items-center gap-2 py-1">
                        <ChevronDown
                          className={`w-3 h-3 text-gray-400 transition-transform duration-200 cursor-pointer ${dCollapsed ? "-rotate-90" : ""}`}
                          onClick={() => toggle(dKey)}
                        />
                        <input
                          type="checkbox"
                          checked={allSuiteSelected}
                          onChange={() => toggleSuite(testIds)}
                          className="w-3.5 h-3.5 rounded"
                        />
                        <span
                          className="text-sm font-semibold text-gray-700 cursor-pointer select-none"
                          onClick={() => toggle(dKey)}
                        >
                          {describe.name}
                        </span>
                        <span className="text-xs text-gray-400">({describe.tests.length})</span>
                      </div>

                      {!dCollapsed && (
                        <div className="pl-5 space-y-0.5">
                          {describe.tests.map((t) => {
                            const status = getTestStatus(t.test_name);
                            const failedTest = result?.tests.find(
                              (rt) => rt.name === t.test_name && rt.status === "failed"
                            );

                            return (
                              <div key={t.id}>
                                <div
                                  className={`flex items-center gap-2 py-0.5 text-sm rounded px-1 cursor-pointer transition-colors ${
                                    selectedIds.has(t.id)
                                      ? "bg-blue-50"
                                      : "hover:bg-gray-50"
                                  }`}
                                  onClick={() => toggleCase(t.id)}
                                >
                                  <input
                                    type="checkbox"
                                    checked={selectedIds.has(t.id)}
                                    onChange={() => toggleCase(t.id)}
                                    className="w-3.5 h-3.5 rounded"
                                    onClick={(e) => e.stopPropagation()}
                                  />
                                  <StatusIcon status={status} />
                                  <span className={
                                    status === "failed" ? "text-red-600" :
                                    status === "passed" ? "text-green-600" :
                                    "text-gray-600"
                                  }>
                                    {t.test_name}
                                  </span>
                                </div>
                                {failedTest?.failure_message && (
                                  <pre className="ml-7 text-xs text-red-500 bg-red-50 rounded px-2 py-1 mt-0.5 whitespace-pre-wrap">
                                    {failedTest.failure_message}
                                  </pre>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
