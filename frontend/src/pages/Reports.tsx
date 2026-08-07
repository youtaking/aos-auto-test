import { useEffect, useState } from "react";
import { listRuns, getRunMdReport } from "../api/runs";
import { get } from "../api/client";
import ReactMarkdown from "react-markdown";
import { FileText, Download } from "lucide-react";
import type { TestRun } from "../api/types";

interface UnitTestRun {
  id: number;
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  duration_ms: number;
  trigger_type: string;
  started_at: string | null;
}

export default function Reports() {
  const [activeTab, setActiveTab] = useState<"integration" | "unit">("integration");

  // 集成测试
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [markdown, setMarkdown] = useState("");
  const [loading, setLoading] = useState(false);

  // 单元测试
  const [unitRuns, setUnitRuns] = useState<UnitTestRun[]>([]);
  const [unitSelectedId, setUnitSelectedId] = useState<number | null>(null);
  const [unitMarkdown, setUnitMarkdown] = useState("");
  const [unitLoading, setUnitLoading] = useState(false);

  useEffect(() => {
    listRuns({ page: 1 }).then((data) => {
      const finished = data.filter(
        (r) => r.status !== "pending" && r.status !== "running"
      );
      setRuns(finished);
      if (finished.length > 0 && !selectedId) {
        setSelectedId(finished[0].id);
      }
    }).catch(console.error);

    get<UnitTestRun[]>("/unit-tests/runs").then((data) => {
      setUnitRuns(data);
      if (data.length > 0 && !unitSelectedId) {
        setUnitSelectedId(data[0].id);
      }
    }).catch(console.error);
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setLoading(true);
    setMarkdown("");
    getRunMdReport(selectedId)
      .then(setMarkdown)
      .catch((e) => setMarkdown(`报告加载失败: ${e.message}`))
      .finally(() => setLoading(false));
  }, [selectedId]);

  useEffect(() => {
    if (!unitSelectedId) return;
    setUnitLoading(true);
    setUnitMarkdown("");
    get<string>(`/unit-tests/runs/${unitSelectedId}/report`)
      .then(setUnitMarkdown)
      .catch((e) => setUnitMarkdown(`报告加载失败: ${e.message}`))
      .finally(() => setUnitLoading(false));
  }, [unitSelectedId]);

  const handleDownload = () => {
    const md = activeTab === "integration" ? markdown : unitMarkdown;
    const id = activeTab === "integration" ? selectedId : unitSelectedId;
    const prefix = activeTab === "integration" ? "report_run" : "unit_report";
    if (!md || !id) return;
    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${prefix}${id}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const statusBadge = (s: string) => {
    if (s === "passed") return "bg-green-100 text-green-700";
    if (s === "failed") return "bg-red-100 text-red-700";
    return "bg-gray-100 text-gray-600";
  };

  const currentMarkdown = activeTab === "integration" ? markdown : unitMarkdown;
  const currentLoading = activeTab === "integration" ? loading : unitLoading;
  const currentRuns = activeTab === "integration" ? runs : unitRuns;
  const currentSelectedId = activeTab === "integration" ? selectedId : unitSelectedId;
  const setCurrentSelectedId = activeTab === "integration" ? setSelectedId : setUnitSelectedId;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold">测试报告</h1>
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => setActiveTab("integration")}
              className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                activeTab === "integration" ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
              }`}
            >
              集成测试
            </button>
            <button
              onClick={() => setActiveTab("unit")}
              className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                activeTab === "unit" ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
              }`}
            >
              单元测试
            </button>
          </div>
        </div>
        {currentSelectedId && currentMarkdown && (
          <button
            onClick={handleDownload}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors"
          >
            <Download className="w-4 h-4" />
            下载 MD
          </button>
        )}
      </div>

      <div className="flex gap-4 h-[calc(100vh-140px)]">
        {/* 左侧：运行列表 */}
        <div className="w-72 shrink-0 bg-white rounded-xl shadow-sm overflow-y-auto">
          {currentRuns.length === 0 ? (
            <p className="p-4 text-gray-400 text-sm">暂无已完成的运行</p>
          ) : (
            currentRuns.map((r) => {
              const status = "failed" in r && (r as TestRun).failed > 0 ? "failed" : "passed";
              return (
                <div
                  key={r.id}
                  onClick={() => setCurrentSelectedId(r.id)}
                  className={`p-3 cursor-pointer border-b border-gray-100 transition-colors ${
                    currentSelectedId === r.id
                      ? "bg-blue-50 border-l-4 border-l-blue-500"
                      : "hover:bg-gray-50"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">
                      {activeTab === "integration" ? `运行 #${r.id}` : `单元测试 #${r.id}`}
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${statusBadge(status)}`}>
                      {status}
                    </span>
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    {r.passed}✅ {r.failed}❌ {r.skipped}⏭️ · {(r.duration_ms / 1000).toFixed(1)}s
                  </div>
                  <div className="text-xs text-gray-400">
                    {r.started_at ? new Date(r.started_at).toLocaleString() : "-"}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* 右侧：MD 报告 */}
        <div className="flex-1 bg-white rounded-xl shadow-sm overflow-y-auto p-6">
          {currentLoading ? (
            <div className="flex items-center justify-center h-full text-gray-400">
              <FileText className="w-6 h-6 animate-pulse mr-2" />
              加载中...
            </div>
          ) : currentMarkdown ? (
            <div className="md-report">
              <ReactMarkdown>{currentMarkdown}</ReactMarkdown>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-400">
              选择左侧运行记录查看报告
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
