import { useEffect, useState } from "react";
import { listProjects, createProject, updateProject, deleteProject, activateProject } from "../api/projects";
import type { Project } from "../api/types";
import { Check, Trash2, Pencil, X } from "lucide-react";

export default function Settings() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editUrl, setEditUrl] = useState("");

  const load = () => listProjects().then(setProjects).catch(console.error);
  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    if (!name || !url) return;
    await createProject({ name, url });
    setName(""); setUrl("");
    load();
  };

  const handleDelete = async (id: number) => {
    if (!confirm("确定删除此项目？")) return;
    await deleteProject(id);
    load();
  };

  const handleActivate = async (id: number) => {
    await activateProject(id);
    load();
  };

  const startEdit = (p: Project) => {
    setEditingId(p.id);
    setEditName(p.name);
    setEditUrl(p.url);
  };

  const handleSave = async () => {
    if (editingId === null) return;
    await updateProject(editingId, { name: editName, url: editUrl });
    setEditingId(null);
    load();
  };

  const handleCancel = () => setEditingId(null);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">设置</h1>

      <div className="bg-white rounded-xl shadow-sm p-6 space-y-4">
        <h2 className="text-lg font-semibold">项目管理</h2>

        {/* 添加项目 */}
        <div className="flex gap-2">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="项目名称" className="px-3 py-2 border rounded-lg" />
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="项目 URL" className="px-3 py-2 border rounded-lg flex-1" />
          <button onClick={handleCreate} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">添加</button>
        </div>

        {/* 项目列表 */}
        <div className="space-y-2">
          {projects.map((p) => (
            <div key={p.id} className={`flex items-center gap-3 p-3 rounded-lg border ${
              p.is_active ? "border-green-400 bg-green-50" : "border-gray-200 bg-gray-50"
            }`}>
              {editingId === p.id ? (
                <>
                  <input value={editName} onChange={(e) => setEditName(e.target.value)} className="px-2 py-1 border rounded" />
                  <input value={editUrl} onChange={(e) => setEditUrl(e.target.value)} className="px-2 py-1 border rounded flex-1" />
                  <button onClick={handleSave} className="p-1.5 text-green-600 hover:bg-green-100 rounded"><Check className="w-4 h-4" /></button>
                  <button onClick={handleCancel} className="p-1.5 text-gray-400 hover:bg-gray-200 rounded"><X className="w-4 h-4" /></button>
                </>
              ) : (
                <>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{p.name}</span>
                      {p.is_active ? (
                        <span className="text-xs bg-green-500 text-white px-2 py-0.5 rounded-full">已激活</span>
                      ) : null}
                    </div>
                    <div className="text-sm text-gray-500">{p.url}</div>
                  </div>
                  {!p.is_active && (
                    <button onClick={() => handleActivate(p.id)} className="px-3 py-1 text-sm text-green-700 hover:bg-green-100 rounded border border-green-300">
                      激活
                    </button>
                  )}
                  <button onClick={() => startEdit(p)} className="p-1.5 text-gray-500 hover:bg-gray-200 rounded"><Pencil className="w-4 h-4" /></button>
                  <button onClick={() => handleDelete(p.id)} className="p-1.5 text-red-400 hover:bg-red-100 rounded"><Trash2 className="w-4 h-4" /></button>
                </>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
