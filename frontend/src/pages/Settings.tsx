import { useEffect, useState } from "react";
import { listProjects, createProject, updateProject, deleteProject, activateProject } from "../api/projects";
import { listAuthConfigs, createAuthConfig, updateAuthConfig, deleteAuthConfig, activateAuthConfig } from "../api/authConfigs";
import { listLLMConfigs, createLLMConfig, updateLLMConfig, deleteLLMConfig, activateLLMConfig } from "../api/llmConfigs";
import { listZentaoConfigs, createZentaoConfig, updateZentaoConfig, deleteZentaoConfig, activateZentaoConfig } from "../api/zentaoConfigs";
import { listSettings, updateSetting } from "../api/settings";
import { pollNow } from "../api/branches";
import type { Project, AuthConfig, LLMConfig, ZentaoConfig } from "../api/types";
import { Check, Trash2, Pencil, X, Eye, EyeOff, Plus, RefreshCw } from "lucide-react";

export default function Settings() {
  // ── 项目管理 ──
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editUrl, setEditUrl] = useState("");

  // ── 认证配置 ──
  const [authConfigs, setAuthConfigs] = useState<AuthConfig[]>([]);
  const [authEditingId, setAuthEditingId] = useState<number | null>(null);
  const [authForm, setAuthForm] = useState({
    name: "", ui_test_email: "", ui_test_password: "",
    api_test_email: "", api_test_password: "", open_api_key: "",
  });
  const [showNewAuth, setShowNewAuth] = useState(false);
  const [showPasswords, setShowPasswords] = useState<Record<number, boolean>>({});
  const [showFormPasswords, setShowFormPasswords] = useState({ ui: false, api: false });
  const emptyForm = { name: "", ui_test_email: "", ui_test_password: "", api_test_email: "", api_test_password: "", open_api_key: "" };

  // ── LLM 配置 ──
  const [llmConfigs, setLLMConfigs] = useState<LLMConfig[]>([]);
  const [llmShowNew, setLLMShowNew] = useState(false);
  const [llmEditingId, setLLMEditingId] = useState<number | null>(null);
  const [llmForm, setLLMForm] = useState({ name: "", provider: "openai", base_url: "", api_key: "", model: "" });
  const [llmShowKeys, setLLMShowKeys] = useState<Record<number, boolean>>({});
  const llmEmptyForm = { name: "", provider: "openai", base_url: "", api_key: "", model: "" };

  // ── 禅道配置 ──
  const [ztConfigs, setZtConfigs] = useState<ZentaoConfig[]>([]);
  const [ztShowNew, setZtShowNew] = useState(false);
  const [ztEditingId, setZtEditingId] = useState<number | null>(null);
  const [ztForm, setZtForm] = useState({ name: "", base_url: "", username: "", password: "", product_id: 1 });
  const ztEmptyForm = { name: "", base_url: "", username: "", password: "", product_id: 1 };

  // ── 分支轮询配置 ──
  const [bpEnabled, setBpEnabled] = useState(false);
  const [bpInterval, setBpInterval] = useState(300);
  const [bpRepo, setBpRepo] = useState("");
  const [bpToken, setBpToken] = useState("");
  const [bpShowToken, setBpShowToken] = useState(false);
  const [bpSaving, setBpSaving] = useState(false);
  const [bpTesting, setBpTesting] = useState(false);
  const [bpTestResult, setBpTestResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [bpPolling, setBpPolling] = useState(false);
  const [bpPollMsg, setBpPollMsg] = useState("");

  const load = () => {
    listProjects().then(setProjects).catch(console.error);
    listAuthConfigs().then(setAuthConfigs).catch(console.error);
    listLLMConfigs().then(setLLMConfigs).catch(console.error);
    listZentaoConfigs().then(setZtConfigs).catch(console.error);
  };
  useEffect(() => { load(); }, []);

  // ── 加载分支轮询配置 ──
  useEffect(() => {
    listSettings()
      .then((items) => {
        const m: Record<string, string> = {};
        items.forEach((s) => { m[s.key] = s.value; });
        setBpEnabled(m["branch_poll_enabled"] === "true");
        if (m["branch_poll_interval"]) setBpInterval(Number(m["branch_poll_interval"]));
        if (m["branch_poll_repo"]) setBpRepo(m["branch_poll_repo"]);
        if (m["github_token"]) setBpToken(m["github_token"]);
      })
      .catch(console.error);
  }, []);

  // ── 分支轮询操作 ──
  const bpSave = async () => {
    setBpSaving(true);
    try {
      await updateSetting("branch_poll_enabled", String(bpEnabled));
      await updateSetting("branch_poll_interval", String(bpInterval));
      await updateSetting("branch_poll_repo", bpRepo);
      await updateSetting("github_token", bpToken);
    } catch (e) {
      console.error(e);
    } finally {
      setBpSaving(false);
    }
  };
  const bpTestConnection = async () => {
    setBpTesting(true);
    setBpTestResult(null);
    try {
      await pollNow();
      setBpTestResult({ ok: true, msg: "连接成功，轮询已触发" });
    } catch (e: any) {
      setBpTestResult({ ok: false, msg: e.message || "连接失败" });
    } finally {
      setBpTesting(false);
    }
  };
  const bpTriggerPoll = async () => {
    setBpPolling(true);
    setBpPollMsg("");
    try {
      await pollNow();
      setBpPollMsg("轮询已触发");
    } catch (e: any) {
      setBpPollMsg(e.message || "轮询失败");
    } finally {
      setBpPolling(false);
    }
  };

  // ── 项目操作 ──
  const handleCreateProject = async () => {
    if (!name || !url) return;
    await createProject({ name, url });
    setName(""); setUrl("");
    load();
  };
  const handleDeleteProject = async (id: number) => {
    if (!confirm("确定删除此项目？")) return;
    await deleteProject(id);
    load();
  };
  const handleActivateProject = async (id: number) => {
    await activateProject(id);
    load();
  };
  const startEditProject = (p: Project) => {
    setEditingId(p.id); setEditName(p.name); setEditUrl(p.url);
  };
  const handleSaveProject = async () => {
    if (editingId === null) return;
    await updateProject(editingId, { name: editName, url: editUrl });
    setEditingId(null); load();
  };

  // ── 认证配置操作 ──
  const startNewAuth = () => {
    setAuthForm(emptyForm);
    setShowNewAuth(true);
    setAuthEditingId(null);
    setShowFormPasswords({ ui: false, api: false });
  };
  const startEditAuth = (c: AuthConfig) => {
    setAuthEditingId(c.id);
    setAuthForm({
      name: c.name, ui_test_email: c.ui_test_email, ui_test_password: c.ui_test_password,
      api_test_email: c.api_test_email, api_test_password: c.api_test_password, open_api_key: c.open_api_key,
    });
    setShowNewAuth(false);
    setShowFormPasswords({ ui: false, api: false });
  };
  const handleSaveAuth = async () => {
    if (!authForm.name) return;
    if (authEditingId) {
      await updateAuthConfig(authEditingId, authForm);
      setAuthEditingId(null);
    } else {
      await createAuthConfig(authForm);
      setShowNewAuth(false);
    }
    setAuthForm(emptyForm);
    load();
  };
  const handleCancelAuth = () => {
    setShowNewAuth(false);
    setAuthEditingId(null);
    setAuthForm(emptyForm);
  };
  const handleDeleteAuth = async (id: number) => {
    if (!confirm("确定删除此认证配置？")) return;
    await deleteAuthConfig(id);
    load();
  };
  const handleActivateAuth = async (id: number) => {
    await activateAuthConfig(id);
    load();
  };
  const togglePassword = (id: number) => {
    setShowPasswords((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  // ── LLM 操作 ──
  const llmStartNew = () => { setLLMForm(llmEmptyForm); setLLMShowNew(true); setLLMEditingId(null); };
  const llmStartEdit = (c: LLMConfig) => {
    setLLMEditingId(c.id);
    setLLMForm({ name: c.name, provider: c.provider, base_url: c.base_url, api_key: c.api_key, model: c.model });
    setLLMShowNew(false);
  };
  const llmSave = async () => {
    if (!llmForm.name || !llmForm.base_url || !llmForm.model) return;
    if (llmEditingId) {
      await updateLLMConfig(llmEditingId, llmForm);
      setLLMEditingId(null);
    } else {
      await createLLMConfig(llmForm);
      setLLMShowNew(false);
    }
    setLLMForm(llmEmptyForm);
    load();
  };
  const llmCancel = () => { setLLMShowNew(false); setLLMEditingId(null); setLLMForm(llmEmptyForm); };
  const llmDelete = async (id: number) => { if (!confirm("确定删除此 LLM 配置？")) return; await deleteLLMConfig(id); load(); };
  const llmActivate = async (id: number) => { await activateLLMConfig(id); load(); };

  // ── 禅道操作 ──
  const ztStartNew = () => { setZtForm(ztEmptyForm); setZtShowNew(true); setZtEditingId(null); };
  const ztStartEdit = (c: ZentaoConfig) => {
    setZtEditingId(c.id);
    setZtForm({ name: c.name, base_url: c.base_url, username: c.username, password: c.password, product_id: c.product_id });
    setZtShowNew(false);
  };
  const ztSave = async () => {
    if (!ztForm.name || !ztForm.base_url) return;
    if (ztEditingId) {
      await updateZentaoConfig(ztEditingId, ztForm);
      setZtEditingId(null);
    } else {
      await createZentaoConfig(ztForm);
      setZtShowNew(false);
    }
    setZtForm(ztEmptyForm);
    load();
  };
  const ztCancel = () => { setZtShowNew(false); setZtEditingId(null); setZtForm(ztEmptyForm); };
  const ztDelete = async (id: number) => { if (!confirm("确定删除此禅道配置？")) return; await deleteZentaoConfig(id); load(); };
  const ztActivate = async (id: number) => { await activateZentaoConfig(id); load(); };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">设置</h1>

      {/* ── 项目管理 ── */}
      <div className="bg-white rounded-xl shadow-sm p-6 space-y-4">
        <h2 className="text-lg font-semibold">项目管理</h2>
        <div className="flex gap-2">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="项目名称" className="px-3 py-2 border rounded-lg" />
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="项目 URL" className="px-3 py-2 border rounded-lg flex-1" />
          <button
            onClick={handleCreateProject}
            disabled={!name || !url}
            className={`px-4 py-2 text-white rounded-lg ${!name || !url ? "bg-gray-300 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-700"}`}
          >添加</button>
        </div>
        <div className="space-y-2">
          {projects.map((p) => (
            <div key={p.id} className={`flex items-center gap-3 p-3 rounded-lg border ${p.is_active ? "border-green-400 bg-green-50" : "border-gray-200 bg-gray-50"}`}>
              {editingId === p.id ? (
                <>
                  <input value={editName} onChange={(e) => setEditName(e.target.value)} className="px-2 py-1 border rounded" />
                  <input value={editUrl} onChange={(e) => setEditUrl(e.target.value)} className="px-2 py-1 border rounded flex-1" />
                  <button onClick={handleSaveProject} className="p-1.5 text-green-600 hover:bg-green-100 rounded"><Check className="w-4 h-4" /></button>
                  <button onClick={() => setEditingId(null)} className="p-1.5 text-gray-400 hover:bg-gray-200 rounded"><X className="w-4 h-4" /></button>
                </>
              ) : (
                <>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{p.name}</span>
                      {p.is_active ? <span className="text-xs bg-green-500 text-white px-2 py-0.5 rounded-full">已激活</span> : null}
                    </div>
                    <div className="text-sm text-gray-500">{p.url}</div>
                  </div>
                  {!p.is_active && <button onClick={() => handleActivateProject(p.id)} className="px-3 py-1 text-sm text-green-700 hover:bg-green-100 rounded border border-green-300">激活</button>}
                  <button onClick={() => startEditProject(p)} className="p-1.5 text-gray-500 hover:bg-gray-200 rounded"><Pencil className="w-4 h-4" /></button>
                  <button onClick={() => handleDeleteProject(p.id)} className="p-1.5 text-red-400 hover:bg-red-100 rounded"><Trash2 className="w-4 h-4" /></button>
                </>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── 认证配置 ── */}
      <div className="bg-white rounded-xl shadow-sm p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">认证配置</h2>
          {!showNewAuth && (
            <button onClick={startNewAuth} className="flex items-center gap-1 px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              <Plus className="w-4 h-4" /> 添加
            </button>
          )}
        </div>

        {/* 新增表单（编辑在卡片内联） */}
        {showNewAuth && (
          <div className="border border-blue-300 bg-blue-50 rounded-lg p-4 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-gray-600 mb-1">配置名称</label>
                <input value={authForm.name} onChange={(e) => setAuthForm({ ...authForm, name: e.target.value })} placeholder="如：测试环境A" className="w-full px-3 py-2 border rounded-lg" />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">Open API Key</label>
                <input value={authForm.open_api_key} onChange={(e) => setAuthForm({ ...authForm, open_api_key: e.target.value })} placeholder="rcs_..." className="w-full px-3 py-2 border rounded-lg" />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">UI 测试账号</label>
                <input value={authForm.ui_test_email} onChange={(e) => setAuthForm({ ...authForm, ui_test_email: e.target.value })} className="w-full px-3 py-2 border rounded-lg" />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">UI 测试密码</label>
                <div className="relative">
                  <input type={showFormPasswords.ui ? "text" : "password"} value={authForm.ui_test_password} onChange={(e) => setAuthForm({ ...authForm, ui_test_password: e.target.value })} className="w-full px-3 py-2 pr-10 border rounded-lg" />
                  <button type="button" onClick={() => setShowFormPasswords((p) => ({ ...p, ui: !p.ui }))} className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600">
                    {showFormPasswords.ui ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">API 测试账号</label>
                <input value={authForm.api_test_email} onChange={(e) => setAuthForm({ ...authForm, api_test_email: e.target.value })} className="w-full px-3 py-2 border rounded-lg" />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">API 测试密码</label>
                <div className="relative">
                  <input type={showFormPasswords.api ? "text" : "password"} value={authForm.api_test_password} onChange={(e) => setAuthForm({ ...authForm, api_test_password: e.target.value })} className="w-full px-3 py-2 pr-10 border rounded-lg" />
                  <button type="button" onClick={() => setShowFormPasswords((p) => ({ ...p, api: !p.api }))} className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600">
                    {showFormPasswords.api ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={handleCancelAuth} className="px-4 py-2 text-gray-600 border rounded-lg hover:bg-gray-100">取消</button>
              <button onClick={handleSaveAuth} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">保存</button>
            </div>
          </div>
        )}

        {/* 配置列表 */}
        <div className="space-y-2">
          {authConfigs.map((c) => {
            const visible = showPasswords[c.id];
            return (
              <div key={c.id} className={`p-3 rounded-lg border ${c.is_active ? "border-green-400 bg-green-50" : "border-gray-200 bg-gray-50"}`}>
                {authEditingId === c.id ? (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-sm text-gray-600 mb-1">配置名称</label>
                        <input value={authForm.name} onChange={(e) => setAuthForm({ ...authForm, name: e.target.value })} className="w-full px-3 py-2 border rounded-lg" />
                      </div>
                      <div>
                        <label className="block text-sm text-gray-600 mb-1">Open API Key</label>
                        <input value={authForm.open_api_key} onChange={(e) => setAuthForm({ ...authForm, open_api_key: e.target.value })} className="w-full px-3 py-2 border rounded-lg" />
                      </div>
                      <div>
                        <label className="block text-sm text-gray-600 mb-1">UI 测试账号</label>
                        <input value={authForm.ui_test_email} onChange={(e) => setAuthForm({ ...authForm, ui_test_email: e.target.value })} className="w-full px-3 py-2 border rounded-lg" />
                      </div>
                      <div>
                        <label className="block text-sm text-gray-600 mb-1">UI 测试密码</label>
                        <div className="relative">
                          <input type={showFormPasswords.ui ? "text" : "password"} value={authForm.ui_test_password} onChange={(e) => setAuthForm({ ...authForm, ui_test_password: e.target.value })} className="w-full px-3 py-2 pr-10 border rounded-lg" />
                          <button type="button" onClick={() => setShowFormPasswords((p) => ({ ...p, ui: !p.ui }))} className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600">
                            {showFormPasswords.ui ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>
                      <div>
                        <label className="block text-sm text-gray-600 mb-1">API 测试账号</label>
                        <input value={authForm.api_test_email} onChange={(e) => setAuthForm({ ...authForm, api_test_email: e.target.value })} className="w-full px-3 py-2 border rounded-lg" />
                      </div>
                      <div>
                        <label className="block text-sm text-gray-600 mb-1">API 测试密码</label>
                        <div className="relative">
                          <input type={showFormPasswords.api ? "text" : "password"} value={authForm.api_test_password} onChange={(e) => setAuthForm({ ...authForm, api_test_password: e.target.value })} className="w-full px-3 py-2 pr-10 border rounded-lg" />
                          <button type="button" onClick={() => setShowFormPasswords((p) => ({ ...p, api: !p.api }))} className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600">
                            {showFormPasswords.api ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>
                    </div>
                    <div className="flex justify-end gap-2">
                      <button onClick={handleCancelAuth} className="px-3 py-1.5 text-gray-600 border rounded hover:bg-gray-100">取消</button>
                      <button onClick={handleSaveAuth} className="px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700">保存</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center gap-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{c.name}</span>
                          {c.is_active ? <span className="text-xs bg-green-500 text-white px-2 py-0.5 rounded-full">已激活</span> : null}
                        </div>
                        <div className="text-sm text-gray-500 mt-1 space-y-0.5">
                          <div>UI 账号: {c.ui_test_email || "-"} | 密码: {visible ? c.ui_test_password || "-" : "••••••••"}</div>
                          <div>API 账号: {c.api_test_email || "-"} | 密码: {visible ? c.api_test_password || "-" : "••••••••"}</div>
                          <div>Open API Key: {c.open_api_key ? (visible ? c.open_api_key : c.open_api_key.slice(0, 10) + "...") : "-"}</div>
                        </div>
                      </div>
                      <button onClick={() => togglePassword(c.id)} className="p-1.5 text-gray-500 hover:bg-gray-200 rounded" title={visible ? "隐藏密码" : "显示密码"}>
                        {visible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                      {!c.is_active && <button onClick={() => handleActivateAuth(c.id)} className="px-3 py-1 text-sm text-green-700 hover:bg-green-100 rounded border border-green-300">激活</button>}
                      <button onClick={() => startEditAuth(c)} className="p-1.5 text-gray-500 hover:bg-gray-200 rounded"><Pencil className="w-4 h-4" /></button>
                      <button onClick={() => handleDeleteAuth(c.id)} className="p-1.5 text-red-400 hover:bg-red-100 rounded"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ── LLM 配置 ── */}
      <div className="bg-white rounded-xl shadow-sm p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">LLM 配置</h2>
          {!llmShowNew && (
            <button onClick={llmStartNew} className="flex items-center gap-1 px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              <Plus className="w-4 h-4" /> 添加
            </button>
          )}
        </div>
        {llmShowNew && (
          <div className="border border-blue-300 bg-blue-50 rounded-lg p-4 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-gray-600 mb-1">配置名称</label>
                <input value={llmForm.name} onChange={(e) => setLLMForm({ ...llmForm, name: e.target.value })} placeholder="如：GPT-4o" className="w-full px-3 py-2 border rounded-lg" />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">提供商</label>
                <select value={llmForm.provider} onChange={(e) => setLLMForm({ ...llmForm, provider: e.target.value })} className="w-full px-3 py-2 border rounded-lg">
                  <option value="openai">OpenAI 兼容</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="custom">自定义</option>
                </select>
              </div>
              <div className="col-span-2">
                <label className="block text-sm text-gray-600 mb-1">API Base URL</label>
                <input value={llmForm.base_url} onChange={(e) => setLLMForm({ ...llmForm, base_url: e.target.value })} placeholder="https://api.openai.com/v1" className="w-full px-3 py-2 border rounded-lg" />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">API Key</label>
                <input value={llmForm.api_key} onChange={(e) => setLLMForm({ ...llmForm, api_key: e.target.value })} placeholder="sk-..." className="w-full px-3 py-2 border rounded-lg" />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">模型</label>
                <input value={llmForm.model} onChange={(e) => setLLMForm({ ...llmForm, model: e.target.value })} placeholder="gpt-4o" className="w-full px-3 py-2 border rounded-lg" />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={llmCancel} className="px-4 py-2 text-gray-600 border rounded-lg hover:bg-gray-100">取消</button>
              <button onClick={llmSave} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">保存</button>
            </div>
          </div>
        )}
        <div className="space-y-2">
          {llmConfigs.map((c) => (
            <div key={c.id} className={`p-3 rounded-lg border ${c.is_active ? "border-green-400 bg-green-50" : "border-gray-200 bg-gray-50"}`}>
              {llmEditingId === c.id ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">配置名称</label>
                      <input value={llmForm.name} onChange={(e) => setLLMForm({ ...llmForm, name: e.target.value })} className="w-full px-2 py-1 border rounded" />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">提供商</label>
                      <select value={llmForm.provider} onChange={(e) => setLLMForm({ ...llmForm, provider: e.target.value })} className="w-full px-2 py-1 border rounded">
                        <option value="openai">OpenAI 兼容</option>
                        <option value="anthropic">Anthropic</option>
                        <option value="custom">自定义</option>
                      </select>
                    </div>
                    <div className="col-span-2">
                      <label className="block text-sm text-gray-600 mb-1">API Base URL</label>
                      <input value={llmForm.base_url} onChange={(e) => setLLMForm({ ...llmForm, base_url: e.target.value })} className="w-full px-2 py-1 border rounded" />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">API Key</label>
                      <input value={llmForm.api_key} onChange={(e) => setLLMForm({ ...llmForm, api_key: e.target.value })} className="w-full px-2 py-1 border rounded" />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">模型</label>
                      <input value={llmForm.model} onChange={(e) => setLLMForm({ ...llmForm, model: e.target.value })} className="w-full px-2 py-1 border rounded" />
                    </div>
                  </div>
                  <div className="flex justify-end gap-2">
                    <button onClick={llmCancel} className="px-3 py-1.5 text-gray-600 border rounded hover:bg-gray-100">取消</button>
                    <button onClick={llmSave} className="px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700">保存</button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{c.name}</span>
                      {c.is_active ? <span className="text-xs bg-green-500 text-white px-2 py-0.5 rounded-full">已激活</span> : null}
                    </div>
                    <div className="text-sm text-gray-500 mt-1">
                      {c.provider} · {c.model} · {llmShowKeys[c.id] ? c.api_key : c.api_key.slice(0, 8) + "..."}
                    </div>
                    <div className="text-xs text-gray-400">{c.base_url}</div>
                  </div>
                  <button onClick={() => setLLMShowKeys((p) => ({ ...p, [c.id]: !p[c.id] }))} className="p-1.5 text-gray-500 hover:bg-gray-200 rounded">
                    {llmShowKeys[c.id] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                  {!c.is_active && <button onClick={() => llmActivate(c.id)} className="px-3 py-1 text-sm text-green-700 hover:bg-green-100 rounded border border-green-300">激活</button>}
                  <button onClick={() => llmStartEdit(c)} className="p-1.5 text-gray-500 hover:bg-gray-200 rounded"><Pencil className="w-4 h-4" /></button>
                  <button onClick={() => llmDelete(c.id)} className="p-1.5 text-red-400 hover:bg-red-100 rounded"><Trash2 className="w-4 h-4" /></button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── 禅道配置 ── */}
      <div className="bg-white rounded-xl shadow-sm p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">禅道配置</h2>
          {!ztShowNew && (
            <button onClick={ztStartNew} className="flex items-center gap-1 px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              <Plus className="w-4 h-4" /> 添加
            </button>
          )}
        </div>
        {ztShowNew && (
          <div className="border border-blue-300 bg-blue-50 rounded-lg p-4 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-gray-600 mb-1">配置名称</label>
                <input value={ztForm.name} onChange={(e) => setZtForm({ ...ztForm, name: e.target.value })} placeholder="如：测试环境禅道" className="w-full px-3 py-2 border rounded-lg" />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">产品 ID</label>
                <input type="number" value={ztForm.product_id} onChange={(e) => setZtForm({ ...ztForm, product_id: Number(e.target.value) })} className="w-full px-3 py-2 border rounded-lg" />
              </div>
              <div className="col-span-2">
                <label className="block text-sm text-gray-600 mb-1">禅道地址</label>
                <input value={ztForm.base_url} onChange={(e) => setZtForm({ ...ztForm, base_url: e.target.value })} placeholder="https://zentao.example.com" className="w-full px-3 py-2 border rounded-lg" />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">账号</label>
                <input value={ztForm.username} onChange={(e) => setZtForm({ ...ztForm, username: e.target.value })} placeholder="禅道登录账号" className="w-full px-3 py-2 border rounded-lg" />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">密码</label>
                <input type="password" value={ztForm.password} onChange={(e) => setZtForm({ ...ztForm, password: e.target.value })} placeholder="禅道登录密码" className="w-full px-3 py-2 border rounded-lg" />
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={ztCancel} className="px-4 py-2 text-gray-600 border rounded-lg hover:bg-gray-100">取消</button>
              <button onClick={ztSave} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">保存</button>
            </div>
          </div>
        )}
        <div className="space-y-2">
          {ztConfigs.map((c) => (
            <div key={c.id} className={`p-3 rounded-lg border ${c.is_active ? "border-green-400 bg-green-50" : "border-gray-200 bg-gray-50"}`}>
              {ztEditingId === c.id ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">配置名称</label>
                      <input value={ztForm.name} onChange={(e) => setZtForm({ ...ztForm, name: e.target.value })} className="w-full px-2 py-1 border rounded" />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">产品 ID</label>
                      <input type="number" value={ztForm.product_id} onChange={(e) => setZtForm({ ...ztForm, product_id: Number(e.target.value) })} className="w-full px-2 py-1 border rounded" />
                    </div>
                    <div className="col-span-2">
                      <label className="block text-sm text-gray-600 mb-1">禅道地址</label>
                      <input value={ztForm.base_url} onChange={(e) => setZtForm({ ...ztForm, base_url: e.target.value })} className="w-full px-2 py-1 border rounded" />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">账号</label>
                      <input value={ztForm.username} onChange={(e) => setZtForm({ ...ztForm, username: e.target.value })} className="w-full px-2 py-1 border rounded" />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">密码</label>
                      <input type="password" value={ztForm.password} onChange={(e) => setZtForm({ ...ztForm, password: e.target.value })} className="w-full px-2 py-1 border rounded" />
                    </div>
                  </div>
                  <div className="flex justify-end gap-2">
                    <button onClick={ztCancel} className="px-3 py-1.5 text-gray-600 border rounded hover:bg-gray-100">取消</button>
                    <button onClick={ztSave} className="px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700">保存</button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{c.name}</span>
                      {c.is_active ? <span className="text-xs bg-green-500 text-white px-2 py-0.5 rounded-full">已激活</span> : null}
                    </div>
                    <div className="text-sm text-gray-500 mt-1">账号: {c.username || "-"} · 产品 ID: {c.product_id}</div>
                    <div className="text-xs text-gray-400">{c.base_url}</div>
                  </div>
                  {!c.is_active && <button onClick={() => ztActivate(c.id)} className="px-3 py-1 text-sm text-green-700 hover:bg-green-100 rounded border border-green-300">激活</button>}
                  <button onClick={() => ztStartEdit(c)} className="p-1.5 text-gray-500 hover:bg-gray-200 rounded"><Pencil className="w-4 h-4" /></button>
                  <button onClick={() => ztDelete(c.id)} className="p-1.5 text-red-400 hover:bg-red-100 rounded"><Trash2 className="w-4 h-4" /></button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── 分支轮询配置 ── */}
      <div className="bg-white rounded-xl shadow-sm p-6 space-y-4">
        <h2 className="text-lg font-semibold">分支轮询配置</h2>

        {/* 轮询开关 */}
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-medium text-gray-700">启用轮询</div>
            <div className="text-xs text-gray-400">定时检查 GitHub 仓库的 Open PR</div>
          </div>
          <button
            onClick={() => setBpEnabled(!bpEnabled)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${bpEnabled ? "bg-blue-600" : "bg-gray-300"}`}
          >
            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${bpEnabled ? "translate-x-6" : "translate-x-1"}`} />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3">
          {/* 仓库地址 */}
          <div className="col-span-2">
            <label className="block text-sm text-gray-600 mb-1">仓库地址</label>
            <input value={bpRepo} onChange={(e) => setBpRepo(e.target.value)} placeholder="owner/repo" className="w-full px-3 py-2 border rounded-lg" />
          </div>

          {/* GitHub Token */}
          <div className="col-span-2">
            <label className="block text-sm text-gray-600 mb-1">GitHub Token</label>
            <div className="relative">
              <input
                type={bpShowToken ? "text" : "password"}
                value={bpToken}
                onChange={(e) => setBpToken(e.target.value)}
                placeholder="ghp_..."
                className="w-full px-3 py-2 pr-10 border rounded-lg"
              />
              <button
                type="button"
                onClick={() => setBpShowToken(!bpShowToken)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
              >
                {bpShowToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* 轮询间隔 */}
          <div>
            <label className="block text-sm text-gray-600 mb-1">轮询间隔（秒）</label>
            <input type="number" value={bpInterval} onChange={(e) => setBpInterval(Number(e.target.value))} min={60} className="w-full px-3 py-2 border rounded-lg" />
          </div>

          {/* 空占位 */}
          <div />
        </div>

        {/* 测试连接结果 */}
        {bpTestResult && (
          <div className={`text-sm px-3 py-2 rounded-lg ${bpTestResult.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600"}`}>
            {bpTestResult.msg}
          </div>
        )}

        {/* 轮询消息 */}
        {bpPollMsg && (
          <div className={`text-sm px-3 py-2 rounded-lg ${bpPollMsg.includes("失败") ? "bg-red-50 text-red-600" : "bg-green-50 text-green-700"}`}>
            {bpPollMsg}
          </div>
        )}

        {/* 操作按钮 */}
        <div className="flex items-center gap-2">
          <button
            onClick={bpSave}
            disabled={bpSaving}
            className={`px-4 py-2 text-white rounded-lg ${bpSaving ? "bg-gray-400 cursor-not-allowed" : "bg-blue-600 hover:bg-blue-700"}`}
          >
            {bpSaving ? "保存中..." : "保存配置"}
          </button>
          <button
            onClick={bpTestConnection}
            disabled={bpTesting || !bpRepo || !bpToken}
            className={`px-4 py-2 rounded-lg border ${bpTesting || !bpRepo || !bpToken ? "text-gray-400 border-gray-200 cursor-not-allowed" : "text-gray-700 border-gray-300 hover:bg-gray-100"}`}
          >
            {bpTesting ? "测试中..." : "测试连接"}
          </button>
          <button
            onClick={bpTriggerPoll}
            disabled={bpPolling}
            className={`flex items-center gap-1 px-4 py-2 rounded-lg border ${bpPolling ? "text-gray-400 border-gray-200 cursor-not-allowed" : "text-gray-700 border-gray-300 hover:bg-gray-100"}`}
          >
            <RefreshCw className={`w-4 h-4 ${bpPolling ? "animate-spin" : ""}`} />
            {bpPolling ? "轮询中..." : "立即轮询"}
          </button>
        </div>
      </div>
    </div>
  );
}
