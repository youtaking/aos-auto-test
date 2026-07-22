import { useEffect, useState } from "react";
import { listProjects, createProject } from "../api/projects";
import type { Project } from "../api/types";

export default function Settings() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");

  useEffect(() => {
    listProjects().then(setProjects).catch(console.error);
  }, []);

  const handleCreate = async () => {
    if (!name || !url) return;
    await createProject({ name, url });
    listProjects().then(setProjects);
    setName("");
    setUrl("");
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">设置</h1>
      <div className="bg-white rounded-xl shadow-sm p-6 space-y-4">
        <h2 className="text-lg font-semibold">项目管理</h2>
        <div className="flex gap-2">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="项目名称" className="px-3 py-2 border rounded-lg" />
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="项目 URL" className="px-3 py-2 border rounded-lg flex-1" />
          <button onClick={handleCreate} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">添加</button>
        </div>
        <div className="space-y-2">
          {projects.map((p) => (
            <div key={p.id} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
              <div>
                <div className="font-medium">{p.name}</div>
                <div className="text-sm text-gray-500">{p.url}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
