import { useEffect, useState, useMemo } from "react";
import { listCollections, createCollection, deleteCollection, updateCollection, getCollection } from "../api/collections";
import type { Collection, TestCase, TestSuite } from "../api/types";
import type { CollectionCaseInfo } from "../api/collections";
import { X, Plus, Trash2, Edit2, FolderOpen } from "lucide-react";

interface Props {
  selectedCaseIds: number[];
  allCases: TestCase[];
  suites: TestSuite[];
  onAddSelectedToCollection: (collectionId: number, caseIds: number[]) => void;
  onClose: () => void;
}

export default function CollectionManager({ selectedCaseIds, allCases, suites, onAddSelectedToCollection, onClose }: Props) {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [expandedCases, setExpandedCases] = useState<CollectionCaseInfo[]>([]);
  const [loadingCases, setLoadingCases] = useState(false);
  const [editName, setEditName] = useState("");
  const [showAddPicker, setShowAddPicker] = useState(false);
  const [addPickerChecked, setAddPickerChecked] = useState<Set<number>>(new Set());

  const load = () => {
    listCollections().then(setCollections).catch(console.error);
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    await createCollection({ name: newName.trim(), description: newDesc, case_ids: selectedCaseIds });
    setNewName("");
    setNewDesc("");
    setShowCreate(false);
    load();
  };

  const handleToggleExpand = async (id: number) => {
    if (expanded === id) {
      setExpanded(null);
      setExpandedCases([]);
      return;
    }
    setExpanded(id);
    setLoadingCases(true);
    try {
      const data = await getCollection(id);
      setExpandedCases(data.cases);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingCases(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("确定删除此用例集？")) return;
    await deleteCollection(id);
    load();
  };

  const handleSaveEdit = async (id: number) => {
    await updateCollection(id, { name: editName.trim() });
    setEditing(null);
    load();
  };

  const handleRemoveCase = async (collectionId: number, caseId: number) => {
    const col = collections.find(c => c.id === collectionId);
    if (!col) return;
    const newIds = col.case_ids.filter(id => id !== caseId);
    await updateCollection(collectionId, { case_ids: newIds });
    setExpandedCases(prev => prev.filter(c => c.id !== caseId));
    load();
  };

  const availableCases = useMemo(() => {
    if (expanded === null) return [];
    const col = collections.find(c => c.id === expanded);
    const existingIds = new Set(col?.case_ids ?? []);
    return allCases.filter(c => !existingIds.has(c.id));
  }, [allCases, collections, expanded]);

  const suiteMap = useMemo(() => Object.fromEntries(suites.map(s => [s.id, s])), [suites]);

  const handleConfirmAdd = async () => {
    if (expanded === null || addPickerChecked.size === 0) return;
    const col = collections.find(c => c.id === expanded);
    if (!col) return;
    const merged = [...new Set([...col.case_ids, ...addPickerChecked])];
    await updateCollection(expanded, { case_ids: merged });
    setShowAddPicker(false);
    setAddPickerChecked(new Set());
    // 刷新展开的用例列表
    const data = await getCollection(expanded);
    setExpandedCases(data.cases);
    load();
  };

  const toggleAddCheck = (id: number) => {
    setAddPickerChecked(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  return (
    <div className="fixed right-0 top-0 h-full w-96 bg-white shadow-xl border-l z-50 flex flex-col">
      <div className="flex items-center justify-between p-4 border-b">
        <h2 className="font-semibold text-lg">用例集管理</h2>
        <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded"><X className="w-5 h-5" /></button>
      </div>

      {selectedCaseIds.length > 0 && (
        <div className="p-3 bg-blue-50 border-b text-sm">
          已选 {selectedCaseIds.length} 个用例
          <button onClick={() => setShowCreate(true)} className="ml-2 text-blue-600 hover:underline">
            创建新集合
          </button>
          {collections.length > 0 && (
            <div className="mt-2">
              <span className="text-gray-500">添加到：</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {collections.map(c => (
                  <button key={c.id} onClick={() => onAddSelectedToCollection(c.id, selectedCaseIds)}
                    className="text-xs px-2 py-0.5 bg-white border rounded hover:bg-blue-50">
                    {c.name}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {showCreate && (
        <div className="p-3 border-b bg-gray-50">
          <input value={newName} onChange={e => setNewName(e.target.value)}
            placeholder="集合名称" className="w-full px-2 py-1.5 border rounded text-sm mb-2" />
          <input value={newDesc} onChange={e => setNewDesc(e.target.value)}
            placeholder="描述（可选）" className="w-full px-2 py-1.5 border rounded text-sm mb-2" />
          <div className="flex gap-2">
            <button onClick={handleCreate} className="px-3 py-1 bg-blue-600 text-white rounded text-sm">创建</button>
            <button onClick={() => setShowCreate(false)} className="px-3 py-1 border rounded text-sm">取消</button>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {collections.length === 0 && !showCreate && (
          <div className="text-center text-gray-400 py-8">
            <FolderOpen className="w-8 h-8 mx-auto mb-2 opacity-50" />
            暂无用例集
            <br />
            <button onClick={() => setShowCreate(true)} className="text-blue-600 hover:underline text-sm mt-2">
              <Plus className="w-3 h-3 inline" /> 创建第一个
            </button>
          </div>
        )}
        {collections.map(c => (
          <div key={c.id} className="border rounded-lg overflow-hidden">
            <div className="p-3 hover:bg-gray-50">
              {editing === c.id ? (
                <div className="flex gap-1">
                  <input value={editName} onChange={e => setEditName(e.target.value)}
                    className="flex-1 px-2 py-1 border rounded text-sm" />
                  <button onClick={() => handleSaveEdit(c.id)} className="text-green-600 text-sm">保存</button>
                  <button onClick={() => setEditing(null)} className="text-gray-400 text-sm">取消</button>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <div className="flex-1 cursor-pointer" onClick={() => handleToggleExpand(c.id)}>
                    <div className="font-medium text-sm">{c.name}</div>
                    <div className="text-xs text-gray-400">{c.case_ids.length} 个用例{c.description ? ` · ${c.description}` : ""}</div>
                  </div>
                  <div className="flex gap-1">
                    <button onClick={() => handleToggleExpand(c.id)}
                      className="p-1 hover:bg-gray-200 rounded text-xs text-gray-500">
                      {expanded === c.id ? "收起" : "查看"}
                    </button>
                    <button onClick={() => { setEditing(c.id); setEditName(c.name); }}
                      className="p-1 hover:bg-gray-200 rounded"><Edit2 className="w-3.5 h-3.5 text-gray-400" /></button>
                    <button onClick={() => handleDelete(c.id)}
                      className="p-1 hover:bg-red-50 rounded"><Trash2 className="w-3.5 h-3.5 text-red-400" /></button>
                  </div>
                </div>
              )}
            </div>
            {expanded === c.id && (
              <div className="border-t bg-gray-50 p-2 max-h-[60vh] overflow-y-auto">
                {loadingCases ? (
                  <div className="text-center text-xs text-gray-400 py-3">加载中...</div>
                ) : (
                  <>
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-xs text-gray-500">{expandedCases.length} 个用例</span>
                      <button
                        onClick={() => { setShowAddPicker(true); setAddPickerChecked(new Set()); }}
                        className="text-xs text-blue-600 hover:underline flex items-center gap-0.5"
                      >
                        <Plus className="w-3 h-3" /> 添加用例
                      </button>
                    </div>
                    {expandedCases.length === 0 ? (
                      <div className="text-center text-xs text-gray-400 py-3">无用例（部分用例可能已被删除）</div>
                    ) : (
                      <div className="space-y-1">
                        {expandedCases.map(tc => (
                          <div key={tc.id} className="flex items-start gap-2 px-2 py-1.5 bg-white rounded text-sm group">
                            <span className={`font-mono px-1 py-0.5 rounded text-xs ${
                              tc.priority === "P0" ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"
                            }`}>{tc.priority}</span>
                            <span className="flex-1">{tc.name}</span>
                            <span className="text-gray-400 text-xs">{tc.function_name}</span>
                            <button
                              onClick={() => handleRemoveCase(c.id, tc.id)}
                              className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-red-50 rounded text-red-400 hover:text-red-600 transition-opacity"
                              title="从集合中移除"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
      {/* 添加用例弹窗 */}
      {showAddPicker && expanded !== null && (
        <div className="fixed inset-0 bg-black/30 z-[60] flex items-center justify-center">
          <div className="bg-white rounded-xl shadow-xl w-[520px] max-h-[70vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="font-semibold text-sm">添加用例到集合</h3>
              <button onClick={() => setShowAddPicker(false)} className="p-1 hover:bg-gray-100 rounded">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-3">
              {availableCases.length === 0 ? (
                <div className="text-center text-gray-400 text-sm py-8">所有用例已在集合中</div>
              ) : (
                <div className="space-y-1">
                  {availableCases.map(tc => (
                    <label key={tc.id}
                      className={`flex items-start gap-2 px-2 py-1.5 rounded cursor-pointer text-sm hover:bg-blue-50 ${addPickerChecked.has(tc.id) ? "bg-blue-50" : ""}`}>
                      <input type="checkbox" checked={addPickerChecked.has(tc.id)}
                        onChange={() => toggleAddCheck(tc.id)} className="mt-0.5" />
                      <span className={`font-mono px-1 py-0.5 rounded text-xs ${
                        tc.priority === "P0" ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"
                      }`}>{tc.priority}</span>
                      <span className="flex-1">{tc.name}</span>
                      <span className="text-xs text-gray-400">{suiteMap[tc.suite_id]?.name ?? ""}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
            <div className="flex items-center justify-between p-3 border-t">
              <span className="text-xs text-gray-500">已选 {addPickerChecked.size} 个</span>
              <div className="flex gap-2">
                <button onClick={() => setShowAddPicker(false)}
                  className="px-3 py-1 border rounded text-sm">取消</button>
                <button onClick={handleConfirmAdd} disabled={addPickerChecked.size === 0}
                  className="px-3 py-1 bg-blue-600 text-white rounded text-sm disabled:opacity-40">
                  添加
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
