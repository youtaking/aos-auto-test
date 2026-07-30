import { useEffect, useState } from "react";
import { listRuns, getRunMdReport } from "../api/runs";
import ReactMarkdown from "react-markdown";
import { FileText, Download } from "lucide-react";
import type { TestRun } from "../api/types";

export default function Reports() {
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [markdown, setMarkdown] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listRuns({ page: 1 }).then((data) => {
      // 只显示已完成的运行
      const finished = data.filter(
        (r) => r.status !== "pending" && r.status !== "running"
      );
      setRuns(finished);
      if (finished.length > 0 && !selectedId) {
        setSelectedId(finished[0].id);
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

  const handleDownload = () => {
    if (!markdown || !selectedId) return;
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `report_run${selectedId}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const statusBadge = (s: string) => {
    if (s === "passed") return "bg-green-100 text-green-700";
    if (s === "failed") return "bg-red-100 text-red-700";
    return "bg-gray-100 text-gray-600";
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">测试报告</h1>
        {selectedId && markdown && (
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
          {runs.length === 0 ? (
            <p className="p-4 text-gray-400 text-sm">暂无已完成的运行</p>
          ) : (
            runs.map((r) => (
              <div
                key={r.id}
                onClick={() => setSelectedId(r.id)}
                className={`p-3 cursor-pointer border-b border-gray-100 transition-colors ${
                  selectedId === r.id
                    ? "bg-blue-50 border-l-4 border-l-blue-500"
                    : "hover:bg-gray-50"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">运行 #{r.id}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${statusBadge(r.status)}`}>
                    {r.status}
                  </span>
                </div>
                <div className="text-xs text-gray-400 mt-1">
                  {r.passed}✅ {r.failed}❌ {r.skipped}⏭️ · {(r.duration_ms / 1000).toFixed(1)}s
                </div>
                <div className="text-xs text-gray-400">
                  {r.started_at ? new Date(r.started_at).toLocaleString() : "-"}
                </div>
              </div>
            ))
          )}
        </div>

        {/* 右侧：MD 报告 */}
        <div className="flex-1 bg-white rounded-xl shadow-sm overflow-y-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center h-full text-gray-400">
              <FileText className="w-6 h-6 animate-pulse mr-2" />
              加载中...
            </div>
          ) : markdown ? (
            <div className="md-report">
              <ReactMarkdown>{markdown}</ReactMarkdown>
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
