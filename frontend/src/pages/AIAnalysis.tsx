import { useEffect, useRef, useState } from "react";
import { listRuns } from "../api/runs";
import { post, get, del } from "../api/client";
import { Brain, Bug, Send, ChevronDown, ChevronUp, Save, FileText, Trash2, ArrowLeft, Download, Upload } from "lucide-react";
import ReactMarkdown from "react-markdown";
import type { TestRun } from "../api/types";

interface BugItem {
  title: string;
  severity: string;
  module: string;
  steps: string[];
  expected: string;
  actual: string;
  error_detail: string;
  selected?: boolean;
  expanded?: boolean;
}

interface SavedReport {
  id: number;
  run_id: number;
  run_status: string;
  run_total: number;
  run_passed: number;
  run_failed: number;
  report_md: string;
  bugs: BugItem[];
  llm_model: string;
  created_at: string;
}

export default function AIAnalysis() {
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [generatingBugs, setGeneratingBugs] = useState(false);
  const [reportMd, setReportMd] = useState("");
  const [bugs, setBugs] = useState<BugItem[]>([]);
  const [error, setError] = useState("");
  const [pushing, setPushing] = useState(false);
  const [pushResult, setPushResult] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const [savedReports, setSavedReports] = useState<SavedReport[]>([]);
  const [viewingReport, setViewingReport] = useState<SavedReport | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const uploadRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    listRuns({ page: 1 }).then((data) => {
      const finished = data.filter((r) => r.status !== "pending" && r.status !== "running");
      setRuns(finished);
    }).catch(console.error);
    loadSavedReports();
  }, []);

  const loadSavedReports = () => {
    get<SavedReport[]>("/ai/reports").then(setSavedReports).catch(console.error);
  };

  // ── 第一步：AI 分析 ───────────────────────────────────────────
  const handleAnalyze = async () => {
    if (!selectedRunId) return;
    setAnalyzing(true);
    setError("");
    setReportMd("");
    setBugs([]);
    setPushResult("");
    setSaveMsg("");
    console.log("[AI分析] 开始分析 run_id:", selectedRunId);
    try {
      const res = await post<{ report: string }>("/ai/analyze", { run_id: selectedRunId });
      console.log("[AI分析] 返回:", res);
      setReportMd(res?.report || "");
    } catch (e: unknown) {
      console.error("[AI分析] 错误:", e);
      setError(e instanceof Error ? e.message : "分析失败");
    } finally {
      setAnalyzing(false);
    }
  };

  // ── 第二步：从报告生成 Bug ────────────────────────────────────
  const handleGenerateBugs = async () => {
    if (!reportMd) return;
    setGeneratingBugs(true);
    setError("");
    setBugs([]);
    setPushResult("");
    try {
      const res = await post<{ bugs: BugItem[] }>("/ai/generate-bugs", { report_md: reportMd });
      const bugList = (res?.bugs || []).map((b) => ({ ...b, selected: true, expanded: false }));
      setBugs(bugList);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "生成 Bug 失败");
    } finally {
      setGeneratingBugs(false);
    }
  };

  // ── 下载报告 JSON ──────────────────────────────────────────────
  const handleDownload = () => {
    if (!reportMd) return;
    const data = {
      report: reportMd,
      bugs: bugs.map(({ title, severity, module, steps, expected, actual, error_detail }) => ({
        title, severity, module, steps, expected, actual, error_detail,
      })),
      run_id: selectedRunId,
      exported_at: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ai-analysis-run${selectedRunId || ""}-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // ── 上传报告 JSON ──────────────────────────────────────────────
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      // 用 axios 直接发 multipart
      const { default: axios } = await import("axios");
      const resp = await axios.post("/api/ai/upload-report", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      if (!resp.data.success) throw new Error(resp.data.error || "上传失败");
      const d = resp.data.data;
      setReportMd(d.report || "");
      setBugs((d.bugs || []).map((b: BugItem) => ({ ...b, selected: true, expanded: false })));
      setSelectedRunId(d.run_id || null);
      setViewingReport(null);
      setSaveMsg("");
      setPushResult("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "上传失败");
    } finally {
      if (uploadRef.current) uploadRef.current.value = "";
    }
  };

  // ── 保存到数据库 ───────────────────────────────────────────────
  const handleSave = async () => {
    if (!selectedRunId || !reportMd) return;
    setSaving(true);
    setSaveMsg("");
    try {
      const res = await post<{ message: string }>("/ai/save-report", {
        run_id: selectedRunId,
        report_md: reportMd,
        bugs: bugs.map(({ title, severity, module, steps, expected, actual, error_detail }) => ({
          title, severity, module, steps, expected, actual, error_detail,
        })),
      });
      setSaveMsg(res?.message || "已保存");
      loadSavedReports();
    } catch (e: unknown) {
      setSaveMsg(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  // ── 历史报告操作 ──────────────────────────────────────────────
  const handleViewReport = (report: SavedReport) => {
    setViewingReport(report);
    setReportMd(report.report_md);
    setBugs(report.bugs.map((b) => ({ ...b, selected: true, expanded: false })));
    setSelectedRunId(report.run_id);
    setShowHistory(false);
    setSaveMsg("");
    setPushResult("");
    setError("");
  };

  const handleDeleteReport = async (id: number) => {
    if (!confirm("确定删除此报告？")) return;
    try {
      await del(`/ai/reports/${id}`);
      loadSavedReports();
      if (viewingReport?.id === id) {
        setViewingReport(null);
        setReportMd("");
        setBugs([]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleBackToNew = () => {
    setViewingReport(null);
    setReportMd("");
    setBugs([]);
    setError("");
    setSaveMsg("");
    setPushResult("");
  };

  // ── Bug 编辑 ──────────────────────────────────────────────────
  const toggleBug = (idx: number) => {
    setBugs((prev) => prev.map((b, i) => i === idx ? { ...b, selected: !b.selected } : b));
  };
  const toggleExpand = (idx: number) => {
    setBugs((prev) => prev.map((b, i) => i === idx ? { ...b, expanded: !b.expanded } : b));
  };
  const updateBug = (idx: number, field: keyof BugItem, value: string | string[]) => {
    setBugs((prev) => prev.map((b, i) => i === idx ? { ...b, [field]: value } : b));
  };
  const selectAll = (val: boolean) => {
    setBugs((prev) => prev.map((b) => ({ ...b, selected: val })));
  };

  // ── 推送到禅道 ────────────────────────────────────────────────
  const handlePushZentao = async () => {
    const selected = bugs.filter((b) => b.selected);
    if (selected.length === 0) return;
    setPushing(true);
    setPushResult("");
    try {
      const res = await post<{ pushed: number; errors: string[] }>("/ai/push-zentao", {
        bugs: selected.map(({ title, severity, module, steps, expected, actual, error_detail }) => ({
          title, severity, module, steps, expected, actual, error_detail,
        })),
      });
      setPushResult(
        `成功推送 ${res.pushed} 条 Bug 到禅道` +
        (res.errors?.length ? `，${res.errors.length} 条失败` : "")
      );
    } catch (e: unknown) {
      setPushResult(e instanceof Error ? e.message : "推送失败");
    } finally {
      setPushing(false);
    }
  };

  const selectedCount = bugs.filter((b) => b.selected).length;
  const selectedRun = runs.find((r) => r.id === selectedRunId);
  const hasReport = !!reportMd;
  const hasBugs = bugs.length > 0;

  const severityColor = (s: string) => {
    if (s === "P0") return "bg-red-100 text-red-700";
    if (s === "P1") return "bg-orange-100 text-orange-700";
    return "bg-yellow-100 text-yellow-700";
  };

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">
          {viewingReport ? (
            <span className="flex items-center gap-2">
              <button onClick={handleBackToNew} className="text-gray-400 hover:text-gray-600">
                <ArrowLeft className="w-6 h-6" />
              </button>
              已保存报告 #{viewingReport.id}
            </span>
          ) : "AI 分析"}
        </h1>
        <div className="flex items-center gap-2">
          {/* 上传 */}
          <input ref={uploadRef} type="file" accept=".json" onChange={handleUpload} className="hidden" />
          <button
            onClick={() => uploadRef.current?.click()}
            className="flex items-center gap-1 px-3 py-2 text-sm text-gray-600 hover:text-gray-800 bg-white border rounded-lg"
          >
            <Upload className="w-4 h-4" /> 上传报告
          </button>
          {/* 历史 */}
          {!viewingReport && (
            <button
              onClick={() => { setShowHistory(!showHistory); loadSavedReports(); }}
              className="flex items-center gap-1 px-3 py-2 text-sm text-gray-600 hover:text-gray-800 bg-white border rounded-lg"
            >
              <FileText className="w-4 h-4" /> 历史报告 ({savedReports.length})
            </button>
          )}
        </div>
      </div>

      {/* 历史报告列表 */}
      {showHistory && !viewingReport && (
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div className="px-6 py-3 border-b bg-gray-50 font-medium text-sm">已保存的分析报告</div>
          {savedReports.length === 0 ? (
            <div className="px-6 py-8 text-center text-gray-400">暂无保存的报告</div>
          ) : (
            <div className="divide-y">
              {savedReports.map((r) => (
                <div key={r.id} className="flex items-center justify-between px-6 py-3 hover:bg-gray-50">
                  <div className="flex-1 cursor-pointer" onClick={() => handleViewReport(r)}>
                    <div className="font-medium text-sm">
                      运行 #{r.run_id} · {r.run_status} · {r.run_passed}✅ {r.run_failed}❌
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      {r.llm_model} · {new Date(r.created_at).toLocaleString()} · {r.bugs.length} 条 Bug
                    </div>
                  </div>
                  <button onClick={() => handleDeleteReport(r.id)} className="p-2 text-gray-400 hover:text-red-500">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 选择运行（新建分析时） */}
      {!viewingReport && (
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div className="flex items-end gap-4">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">选择测试运行</label>
              <select
                value={selectedRunId ?? ""}
                onChange={(e) => setSelectedRunId(Number(e.target.value) || null)}
                className="w-full px-3 py-2 border rounded-lg"
              >
                <option value="">-- 请选择 --</option>
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>
                    运行 #{r.id} · {r.status} · {r.passed}✅{r.failed}❌ · {new Date(r.started_at || r.created_at).toLocaleString()}
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={handleAnalyze}
              disabled={!selectedRunId || analyzing}
              className={`flex items-center gap-2 px-6 py-2 text-white rounded-lg font-medium transition-colors ${
                !selectedRunId || analyzing ? "bg-gray-400 cursor-not-allowed" : "bg-purple-600 hover:bg-purple-700"
              }`}
            >
              <Brain className={`w-5 h-5 ${analyzing ? "animate-pulse" : ""}`} />
              {analyzing ? "分析中..." : "AI 分析"}
            </button>
          </div>
          {selectedRun && (
            <div className="mt-3 text-sm text-gray-500">
              运行 #{selectedRun.id}：{selectedRun.total} 条用例，{selectedRun.failed} 条失败，
              通过率 {selectedRun.total ? ((selectedRun.passed / selectedRun.total) * 100).toFixed(1) : 0}%
            </div>
          )}
        </div>
      )}

      {/* 错误提示 */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700">{error}</div>
      )}

      {/* 分析报告 */}
      {hasReport && (
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          {/* 报告头部 */}
          <div className="flex items-center justify-between px-6 py-3 border-b bg-gray-50">
            <div className="flex items-center gap-3">
              <FileText className="w-5 h-5 text-purple-600" />
              <span className="font-medium">分析报告</span>
              {viewingReport && (
                <span className="text-xs text-gray-400">
                  {viewingReport.llm_model} · {new Date(viewingReport.created_at).toLocaleString()}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {saveMsg && <span className="text-xs text-green-600">{saveMsg}</span>}
              <button
                onClick={handleDownload}
                className="flex items-center gap-1 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800 border rounded-lg"
              >
                <Download className="w-4 h-4" /> 下载
              </button>
              {!viewingReport && (
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className={`flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${
                    saving ? "bg-gray-300 text-gray-500" : "bg-blue-600 hover:bg-blue-700 text-white"
                  }`}
                >
                  <Save className="w-4 h-4" />
                  {saving ? "保存中..." : "保存"}
                </button>
              )}
            </div>
          </div>

          {/* Markdown 内容 */}
          <div className="px-6 py-4 md-report">
            <ReactMarkdown>{reportMd}</ReactMarkdown>
          </div>

          {/* 生成 Bug 按钮 */}
          {!hasBugs && (
            <div className="px-6 py-4 border-t bg-gray-50 flex justify-center">
              <button
                onClick={handleGenerateBugs}
                disabled={generatingBugs}
                className={`flex items-center gap-2 px-6 py-2.5 text-white rounded-lg font-medium transition-colors ${
                  generatingBugs ? "bg-gray-400 cursor-not-allowed" : "bg-orange-500 hover:bg-orange-600"
                }`}
              >
                <Bug className={`w-5 h-5 ${generatingBugs ? "animate-pulse" : ""}`} />
                {generatingBugs ? "生成中..." : "根据报告生成 Bug"}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Bug 列表 */}
      {hasBugs && (
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          {/* Bug 工具栏 */}
          <div className="flex items-center justify-between px-6 py-3 border-b bg-gray-50">
            <div className="flex items-center gap-3">
              <Bug className="w-5 h-5 text-purple-600" />
              <span className="font-medium">AI 识别 Bug（{bugs.length} 条）</span>
              <button onClick={() => selectAll(true)} className="text-xs text-blue-600 hover:text-blue-800">全选</button>
              <button onClick={() => selectAll(false)} className="text-xs text-blue-600 hover:text-blue-800">取消全选</button>
            </div>
            <button
              onClick={handlePushZentao}
              disabled={selectedCount === 0 || pushing}
              className={`flex items-center gap-2 px-4 py-2 text-white rounded-lg text-sm font-medium transition-colors ${
                selectedCount === 0 || pushing ? "bg-gray-400 cursor-not-allowed" : "bg-green-600 hover:bg-green-700"
              }`}
            >
              <Send className="w-4 h-4" />
              {pushing ? "推送中..." : `推送到禅道 (${selectedCount})`}
            </button>
          </div>

          {pushResult && (
            <div className={`px-6 py-2 text-sm ${pushResult.includes("成功") ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
              {pushResult}
            </div>
          )}

          {/* Bug 卡片 */}
          <div className="divide-y">
            {bugs.map((bug, idx) => (
              <div key={idx} className={`px-6 py-4 transition-colors ${bug.selected ? "" : "bg-gray-50 opacity-60"}`}>
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={bug.selected}
                    onChange={() => toggleBug(idx)}
                    className="w-4 h-4 rounded"
                  />
                  <span className={`text-xs font-mono px-2 py-0.5 rounded ${severityColor(bug.severity)}`}>
                    {bug.severity}
                  </span>
                  <input
                    value={bug.title}
                    onChange={(e) => updateBug(idx, "title", e.target.value)}
                    className="flex-1 font-medium text-sm border-none bg-transparent focus:ring-1 focus:ring-blue-300 rounded px-1"
                  />
                  <button onClick={() => toggleExpand(idx)} className="p-1 text-gray-400 hover:text-gray-600">
                    {bug.expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </button>
                </div>

                {bug.expanded && (
                  <div className="mt-3 ml-7 space-y-2 text-sm">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-gray-500 text-xs">模块</label>
                        <input
                          value={bug.module}
                          onChange={(e) => updateBug(idx, "module", e.target.value)}
                          className="w-full px-2 py-1 border rounded text-sm"
                        />
                      </div>
                      <div>
                        <label className="text-gray-500 text-xs">严重程度</label>
                        <select
                          value={bug.severity}
                          onChange={(e) => updateBug(idx, "severity", e.target.value)}
                          className="w-full px-2 py-1 border rounded text-sm"
                        >
                          <option value="P0">P0 - 致命</option>
                          <option value="P1">P1 - 严重</option>
                          <option value="P2">P2 - 一般</option>
                        </select>
                      </div>
                    </div>
                    <div>
                      <label className="text-gray-500 text-xs">复现步骤</label>
                      <textarea
                        value={bug.steps.join("\n")}
                        onChange={(e) => updateBug(idx, "steps", e.target.value.split("\n"))}
                        rows={3}
                        className="w-full px-2 py-1 border rounded text-sm font-mono"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-gray-500 text-xs">期望结果</label>
                        <input
                          value={bug.expected}
                          onChange={(e) => updateBug(idx, "expected", e.target.value)}
                          className="w-full px-2 py-1 border rounded text-sm"
                        />
                      </div>
                      <div>
                        <label className="text-gray-500 text-xs">实际结果</label>
                        <input
                          value={bug.actual}
                          onChange={(e) => updateBug(idx, "actual", e.target.value)}
                          className="w-full px-2 py-1 border rounded text-sm"
                        />
                      </div>
                    </div>
                    {bug.error_detail && (
                      <div>
                        <label className="text-gray-500 text-xs">错误详情</label>
                        <pre className="bg-gray-900 text-gray-300 p-2 rounded text-xs overflow-x-auto max-h-32">
                          {bug.error_detail}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
