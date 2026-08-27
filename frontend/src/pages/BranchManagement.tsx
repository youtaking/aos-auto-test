import { useEffect, useState, useCallback } from "react";
import {
  RefreshCw, Plus, Trash2, ArrowUpCircle, Play, RotateCcw,
  Settings, GitBranch, CheckCircle2,
  XCircle, Loader2, ExternalLink, FolderOpen, Clock,
  Archive, FileCode, FileText, X,
} from "lucide-react";
import {
  listBranches, createBranch, deleteBranch, resetBranch, promoteBranch,
  pollNow, canGenerate, launchGenerate, listBranchCases,
  type BranchInfo, type BranchCases,
} from "../api/branches";

/* ---------- 开发状态徽章 ---------- */

const devStatusConfig: Record<string, { label: string; cls: string; icon: typeof CheckCircle2 }> = {
  open: { label: "Open", cls: "bg-green-50 text-green-700 border-green-200", icon: GitBranch },
  merged: { label: "已合入", cls: "bg-purple-50 text-purple-700 border-purple-200", icon: CheckCircle2 },
  closed: { label: "已关闭", cls: "bg-red-50 text-red-600 border-red-200", icon: XCircle },
  manual: { label: "手动", cls: "bg-blue-50 text-blue-700 border-blue-200", icon: FolderOpen },
  up_to_date: { label: "主干", cls: "bg-gray-50 text-gray-500 border-gray-200", icon: GitBranch },
};

function DevStatusBadge({ status }: { status: string }) {
  const cfg = devStatusConfig[status] ?? devStatusConfig.closed;
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${cfg.cls}`}>
      <Icon className="w-3 h-3" />
      {cfg.label}
    </span>
  );
}

/* ---------- 测试集状态徽章 ---------- */

const caseStatusConfig: Record<string, { label: string; cls: string; icon: typeof CheckCircle2 }> = {
  pending: { label: "未创建", cls: "bg-gray-50 text-gray-500 border-gray-200", icon: Clock },
  active: { label: "使用中", cls: "bg-green-50 text-green-700 border-green-200", icon: CheckCircle2 },
  ready_to_sync: { label: "可同步", cls: "bg-blue-50 text-blue-700 border-blue-200", icon: ArrowUpCircle },
  disposable: { label: "可清理", cls: "bg-orange-50 text-orange-700 border-orange-200", icon: Archive },
};

function CaseStatusBadge({ status }: { status: string }) {
  const cfg = caseStatusConfig[status] ?? caseStatusConfig.pending;
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${cfg.cls}`}>
      <Icon className="w-3 h-3" />
      {cfg.label}
    </span>
  );
}

/* ---------- 主页面 ---------- */

export default function BranchManagement() {
  const [branches, setBranches] = useState<BranchInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);

  // 创建弹窗
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  // 删除确认
  const [deleteTarget, setDeleteTarget] = useState<BranchInfo | null>(null);
  const [deleting, setDeleting] = useState(false);

  // 重置确认
  const [resetTarget, setResetTarget] = useState<BranchInfo | null>(null);
  const [resetting, setResetting] = useState(false);

  // 生成用例
  const [generating, setGenerating] = useState<string | null>(null);

  // Promote
  const [promoting, setPromoting] = useState<string | null>(null);
  const [promoteResult, setPromoteResult] = useState<{ branch: string; files: string[] } | null>(null);

  // 用例抽屉
  const [casesDrawer, setCasesDrawer] = useState<string | null>(null);
  const [casesData, setCasesData] = useState<BranchCases | null>(null);
  const [casesLoading, setCasesLoading] = useState(false);
  const [casesTab, setCasesTab] = useState<"api" | "unit">("api");

  // 错误/提示
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    listBranches()
      .then(setBranches)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  /* ---------- 操作 ---------- */

  const handlePoll = async () => {
    if (polling) return;
    setPolling(true);
    try {
      await pollNow();
      await load();
      showToast("轮询完成");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setPolling(false);
    }
  };

  const handleCreate = async () => {
    if (!newName.trim() || creating) return;
    setCreating(true);
    try {
      await createBranch(newName.trim());
      setShowCreate(false);
      setNewName("");
      await load();
      showToast("分支创建成功");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget || deleting) return;
    setDeleting(true);
    try {
      await deleteBranch(deleteTarget.branch_name);
      setDeleteTarget(null);
      await load();
      showToast("分支已删除");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setDeleting(false);
    }
  };

  const handleReset = async () => {
    if (!resetTarget || resetting) return;
    setResetting(true);
    try {
      await resetBranch(resetTarget.branch_name);
      setResetTarget(null);
      await load();
      showToast("重置完成，用例已从主干重新复制");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setResetting(false);
    }
  };

  const handlePromote = async (branchName: string) => {
    if (promoting) return;
    setPromoting(branchName);
    try {
      const report = await promoteBranch(branchName);
      const files = [...report.new_api_files, ...report.new_unit_files];
      if (files.length > 0) {
        setPromoteResult({ branch: branchName, files });
      } else {
        showToast("Promote 完成，无新文件");
      }
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setPromoting(null);
    }
  };

  const handleGenerate = async (branchName: string, testType: "api" | "unit") => {
    if (generating) return;

    // 先检查 can-generate
    try {
      const check = await canGenerate();
      if (!check.can_generate) {
        showToast("当前环境不支持生成用例（需要本地 autotest 目录）");
        return;
      }
    } catch (e: any) {
      setError(e.message);
      return;
    }

    setGenerating(`${branchName}:${testType}`);
    try {
      await launchGenerate(branchName, testType);
      showToast("Claude Code 已启动");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setGenerating(null);
    }
  };

  const handleViewCases = async (branchName: string) => {
    setCasesDrawer(branchName);
    setCasesTab("api");
    setCasesLoading(true);
    try {
      const data = await listBranchCases(branchName);
      setCasesData(data);
    } catch (e: any) {
      setError(e.message);
      setCasesData(null);
    } finally {
      setCasesLoading(false);
    }
  };

  /* ---------- 渲染 ---------- */

  return (
    <div className="space-y-6">
      {/* 页头 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">分支用例</h1>
          <p className="text-gray-500 mt-1">
            {loading ? "加载中..." : `共 ${branches.length} 个分支`}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            创建分支
          </button>
          <button
            onClick={handlePoll}
            disabled={polling}
            className={`flex items-center gap-2 px-4 py-2 border rounded-lg text-sm font-medium transition-colors ${
              polling ? "text-gray-400 cursor-not-allowed" : "hover:bg-gray-50"
            }`}
          >
            <RefreshCw className={`w-4 h-4 ${polling ? "animate-spin" : ""}`} />
            {polling ? "轮询中..." : "手动轮询"}
          </button>
          <a
            href="/settings"
            className="flex items-center gap-2 px-4 py-2 border rounded-lg text-sm font-medium hover:bg-gray-50"
          >
            <Settings className="w-4 h-4" />
            Settings
          </a>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 bg-green-600 text-white px-4 py-2 rounded-lg shadow-lg text-sm animate-pulse">
          {toast}
        </div>
      )}

      {/* 错误 */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600 ml-4">
            <XCircle className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Promote 结果 */}
      {promoteResult && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="font-semibold text-green-700">
              Promote 完成 — {promoteResult.branch}
            </span>
            <button onClick={() => setPromoteResult(null)} className="text-green-400 hover:text-green-600">
              <XCircle className="w-4 h-4" />
            </button>
          </div>
          <p className="text-green-600 mb-1">新增 {promoteResult.files.length} 个文件：</p>
          <ul className="list-disc list-inside text-green-600 space-y-0.5">
            {promoteResult.files.map((f) => (
              <li key={f} className="font-mono text-xs">{f}</li>
            ))}
          </ul>
        </div>
      )}

      {/* 表格 */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        {loading && branches.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2" />
            加载中...
          </div>
        ) : branches.length === 0 ? (
          <div className="p-8 text-center text-gray-400">
            暂无分支数据，点击"手动轮询"同步 GitHub Open PR
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b bg-gray-50">
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">分支名</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">PR</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Commit</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">开发状态</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">测试集状态</th>
                <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">更新时间</th>
                <th className="text-right px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {branches.map((b) => {
                const isGeneratingApi = generating === `${b.branch_name}:api`;
                const isGeneratingUnit = generating === `${b.branch_name}:unit`;
                const isPromoting = promoting === b.branch_name;
                const isMain = b.branch_name === "main";

                return (
                  <tr key={b.branch_name} className="hover:bg-gray-50 transition-colors">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <GitBranch className="w-4 h-4 text-gray-400 shrink-0" />
                        {b.has_dir && !isMain ? (
                          <button
                            onClick={() => handleViewCases(b.branch_name)}
                            className="font-medium text-sm text-blue-600 hover:text-blue-800 hover:underline"
                          >
                            {b.branch_name}
                          </button>
                        ) : (
                          <span className="font-medium text-sm">{b.branch_name}</span>
                        )}
                      </div>
                    </td>
                    <td className="px-5 py-3">
                      {b.pr_number ? (
                        <span className="inline-flex items-center gap-1 text-xs text-gray-600">
                          <ExternalLink className="w-3 h-3" />
                          #{b.pr_number}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400">-</span>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded font-mono">
                        {b.last_commit_sha?.substring(0, 8) || "-"}
                      </code>
                    </td>
                    <td className="px-5 py-3">
                      <DevStatusBadge status={b.dev_status} />
                    </td>
                    <td className="px-5 py-3">
                      <CaseStatusBadge status={b.case_status} />
                    </td>
                    <td className="px-5 py-3 text-sm text-gray-500">
                      {b.updated_at ? new Date(b.updated_at).toLocaleString("zh-CN") : "-"}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center justify-end gap-1.5">
                        {/* 生成按钮：只有测试集状态为 active 或有目录时才显示 */}
                        {!isMain && b.case_status !== "pending" && (
                          <>
                            <button
                              onClick={() => handleGenerate(b.branch_name, "api")}
                              disabled={!!generating}
                              title="生成 API 用例"
                              className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1 ${
                                generating
                                  ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                                  : "bg-blue-50 text-blue-700 hover:bg-blue-100"
                              }`}
                            >
                              <Play className="w-3 h-3" />
                              {isGeneratingApi ? "启动中..." : "API 用例"}
                            </button>
                            <button
                              onClick={() => handleGenerate(b.branch_name, "unit")}
                              disabled={!!generating}
                              title="生成单元测试"
                              className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1 ${
                                generating
                                  ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                                  : "bg-purple-50 text-purple-700 hover:bg-purple-100"
                              }`}
                            >
                              <Play className="w-3 h-3" />
                              {isGeneratingUnit ? "启动中..." : "单元测试"}
                            </button>
                          </>
                        )}

                        {/* Promote 按钮：只有 ready_to_sync 或有目录时显示 */}
                        {(b.case_status === "ready_to_sync" || b.has_dir) && (
                          <button
                            onClick={() => handlePromote(b.branch_name)}
                            disabled={!!promoting}
                            title="Promote 到主干"
                            className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1 ${
                              promoting
                                ? "bg-gray-100 text-gray-400 cursor-not-allowed"
                                : "bg-green-50 text-green-700 hover:bg-green-100"
                            }`}
                          >
                            <ArrowUpCircle className="w-3 h-3" />
                            {isPromoting ? "..." : "Promote"}
                          </button>
                        )}

                        {/* 重置按钮 */}
                        {!isMain && b.has_dir && (
                          <button
                            onClick={() => setResetTarget(b)}
                            title="重置用例（从主干重新复制）"
                            className="p-1.5 rounded-lg transition-colors text-orange-400 hover:bg-orange-50 hover:text-orange-600"
                          >
                            <RotateCcw className="w-4 h-4" />
                          </button>
                        )}

                        {/* 删除按钮 */}
                        <button
                          onClick={() => setDeleteTarget(b)}
                          title="删除分支"
                          className="p-1.5 rounded-lg transition-colors text-red-400 hover:bg-red-50 hover:text-red-600"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* 创建分支弹窗 */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
            <h2 className="text-lg font-semibold">创建分支</h2>
            <p className="text-sm text-gray-500">输入新的分支名称，系统将自动从主干创建用例目录。</p>
            <input
              autoFocus
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="feature/xxx"
              className="w-full px-3 py-2 border rounded-lg text-sm font-mono"
              onKeyDown={(e) => { if (e.key === "Enter") handleCreate(); }}
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => { setShowCreate(false); setNewName(""); }}
                className="px-4 py-2 border rounded-lg text-sm font-medium hover:bg-gray-50"
              >
                取消
              </button>
              <button
                onClick={handleCreate}
                disabled={!newName.trim() || creating}
                className={`px-4 py-2 text-white rounded-lg text-sm font-medium transition-colors ${
                  creating || !newName.trim() ? "bg-gray-400 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-700"
                }`}
              >
                {creating ? "创建中..." : "创建"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 删除确认弹窗 */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
            <h2 className="text-lg font-semibold text-red-600">确认删除</h2>
            <p className="text-sm text-gray-600">
              确定要删除分支 <code className="bg-gray-100 px-1.5 py-0.5 rounded font-mono">{deleteTarget.branch_name}</code> 吗？
            </p>
            {deleteTarget.has_dir && (
              <p className="text-sm text-orange-600 bg-orange-50 rounded-lg p-3">
                该分支存在关联的测试目录，删除时将一并删除。
              </p>
            )}
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setDeleteTarget(null)}
                className="px-4 py-2 border rounded-lg text-sm font-medium hover:bg-gray-50"
              >
                取消
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className={`px-4 py-2 text-white rounded-lg text-sm font-medium transition-colors ${
                  deleting ? "bg-gray-400 cursor-not-allowed" : "bg-red-600 hover:bg-red-700"
                }`}
              >
                {deleting ? "删除中..." : "确认删除"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 重置确认弹窗 */}
      {resetTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
            <h2 className="text-lg font-semibold text-orange-600">确认重置</h2>
            <p className="text-sm text-gray-600">
              确定要重置分支 <code className="bg-gray-100 px-1.5 py-0.5 rounded font-mono">{resetTarget.branch_name}</code> 吗？
            </p>
            <p className="text-sm text-orange-600 bg-orange-50 rounded-lg p-3">
              分支上的所有用例修改将丢失，将从主干重新复制用例。
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setResetTarget(null)}
                className="px-4 py-2 border rounded-lg text-sm font-medium hover:bg-gray-50"
              >
                取消
              </button>
              <button
                onClick={handleReset}
                disabled={resetting}
                className={`px-4 py-2 text-white rounded-lg text-sm font-medium transition-colors ${
                  resetting ? "bg-gray-400 cursor-not-allowed" : "bg-orange-600 hover:bg-orange-700"
                }`}
              >
                {resetting ? "重置中..." : "确认重置"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 用例抽屉 */}
      {casesDrawer && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={() => setCasesDrawer(null)}>
          <div
            className="w-full max-w-md bg-white shadow-xl flex flex-col animate-in slide-in-from-right"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 头部 */}
            <div className="flex items-center justify-between px-5 py-4 border-b">
              <div className="flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-gray-500" />
                <span className="font-semibold text-sm">{casesDrawer}</span>
              </div>
              <button onClick={() => setCasesDrawer(null)} className="p-1 hover:bg-gray-100 rounded">
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Tab */}
            <div className="flex border-b">
              <button
                onClick={() => setCasesTab("api")}
                className={`flex-1 px-4 py-2.5 text-sm font-medium transition-colors ${
                  casesTab === "api"
                    ? "text-blue-600 border-b-2 border-blue-600"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                <FileCode className="w-4 h-4 inline mr-1.5" />
                API 用例 {casesData ? `(${casesData.api_suites.length})` : ""}
              </button>
              <button
                onClick={() => setCasesTab("unit")}
                className={`flex-1 px-4 py-2.5 text-sm font-medium transition-colors ${
                  casesTab === "unit"
                    ? "text-blue-600 border-b-2 border-blue-600"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                <FileText className="w-4 h-4 inline mr-1.5" />
                单元测试 {casesData ? `(${casesData.unit_tests.length})` : ""}
              </button>
            </div>

            {/* 文件列表 */}
            <div className="flex-1 overflow-y-auto">
              {casesLoading ? (
                <div className="p-8 text-center text-gray-400">
                  <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" />
                  加载中...
                </div>
              ) : !casesData ? (
                <div className="p-8 text-center text-gray-400">加载失败</div>
              ) : (
                (() => {
                  const files = casesTab === "api" ? casesData.api_suites : casesData.unit_tests;
                  if (files.length === 0) {
                    return (
                      <div className="p-8 text-center text-gray-400">
                        {casesTab === "api" ? "暂无 API 用例" : "暂无单元测试"}
                      </div>
                    );
                  }
                  return (
                    <ul className="divide-y">
                      {files.map((f) => (
                        <li key={f.path} className="px-5 py-3 hover:bg-gray-50 flex items-center justify-between">
                          <div className="flex items-center gap-2 min-w-0">
                            <FileCode className="w-4 h-4 text-gray-400 shrink-0" />
                            <span className="text-sm font-mono truncate">{f.path}</span>
                          </div>
                          <span className="text-xs text-gray-400 shrink-0 ml-2">
                            {(f.size / 1024).toFixed(1)}KB
                          </span>
                        </li>
                      ))}
                    </ul>
                  );
                })()
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
