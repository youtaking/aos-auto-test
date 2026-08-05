import { useEffect, useState } from "react";
import { getCIConfig, updateCIConfig, regenerateToken } from "../api/ciConfig";
import { listSlots, updateSlot } from "../api/slots";
import { listCollections } from "../api/collections";
import type { CIConfig, EnvironmentSlot, Collection } from "../api/types";
import { X, Eye, EyeOff, RefreshCw, Copy } from "lucide-react";

interface Props {
  onClose: () => void;
}

export default function CIConfigModal({ onClose }: Props) {
  const [config, setConfig] = useState<CIConfig | null>(null);
  const [slots, setSlots] = useState<EnvironmentSlot[]>([]);
  const [showToken, setShowToken] = useState(false);
  const [saving, setSaving] = useState(false);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selectedCollectionIds, setSelectedCollectionIds] = useState<number[]>([]);

  const load = () => {
    getCIConfig().then((c) => {
      setConfig(c);
      if (c.collection_ids) setSelectedCollectionIds(c.collection_ids);
    }).catch(console.error);
    listSlots().then(setSlots).catch(console.error);
    listCollections().then(setCollections).catch(console.error);
  };
  useEffect(() => { load(); }, []);

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      await updateCIConfig({
        timeout_minutes: config.timeout_minutes,
        max_queue_size: config.max_queue_size,
        collection_ids: selectedCollectionIds.length > 0 ? selectedCollectionIds : null,
      });
      for (const s of slots) {
        await updateSlot(s.id, {
          name: s.name,
          rcs_port: s.rcs_port,
          postgres_port: s.postgres_port,
          litellm_port: s.litellm_port,
        });
      }
      onClose();
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const handleRegenToken = async () => {
    if (!confirm("重新生成 Token 后旧 Token 将立即失效，确定？")) return;
    const result = await regenerateToken();
    setConfig((prev) => prev ? { ...prev, auth_token: result.token } : null);
  };

  const handleCopyToken = () => {
    if (config?.auth_token) {
      navigator.clipboard.writeText(config.auth_token);
    }
  };

  if (!config) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-[600px] max-h-[80vh] overflow-y-auto p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold">CI 配置</h2>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded"><X className="w-5 h-5" /></button>
        </div>

        {/* 全局配置 */}
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">超时销毁时间（分钟）</label>
              <input
                type="number"
                value={config.timeout_minutes}
                onChange={(e) => setConfig({ ...config, timeout_minutes: Number(e.target.value) })}
                className="w-full px-3 py-2 border rounded-lg"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">队列上限</label>
              <input
                type="number"
                value={config.max_queue_size}
                onChange={(e) => setConfig({ ...config, max_queue_size: Number(e.target.value) })}
                className="w-full px-3 py-2 border rounded-lg"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-600 mb-1">认证 Token</label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <input
                  type={showToken ? "text" : "password"}
                  value={config.auth_token || "（未设置）"}
                  readOnly
                  className="w-full px-3 py-2 pr-10 border rounded-lg bg-gray-50"
                />
                <button
                  type="button"
                  onClick={() => setShowToken(!showToken)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
                >
                  {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <button onClick={handleCopyToken} className="p-2 border rounded-lg hover:bg-gray-50" title="复制">
                <Copy className="w-4 h-4" />
              </button>
              <button onClick={handleRegenToken} className="p-2 border rounded-lg hover:bg-gray-50" title="重新生成">
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">CI 运行用例集</label>
            {collections.length === 0 ? (
              <p className="text-xs text-gray-400">暂无用例集，请先在用例管理页创建</p>
            ) : (
              <div className="space-y-1 max-h-32 overflow-y-auto border rounded p-2">
                {collections.map(c => (
                  <label key={c.id} className="flex items-center gap-2 text-sm">
                    <input type="checkbox"
                      checked={selectedCollectionIds.includes(c.id)}
                      onChange={e => {
                        if (e.target.checked) setSelectedCollectionIds(prev => [...prev, c.id]);
                        else setSelectedCollectionIds(prev => prev.filter(id => id !== c.id));
                      }} />
                    {c.name} <span className="text-gray-400">({c.case_ids.length} 用例)</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Slot 配置 */}
        <div className="space-y-3">
          <h3 className="font-semibold">Slot 配置</h3>
          {slots.map((s, i) => (
            <div key={s.id} className="border rounded-lg p-3">
              <div className="font-medium text-sm mb-2">{s.name}</div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-xs text-gray-500">RCS 端口</label>
                  <input
                    type="number"
                    value={s.rcs_port}
                    onChange={(e) => {
                      const updated = [...slots];
                      updated[i] = { ...s, rcs_port: Number(e.target.value) };
                      setSlots(updated);
                    }}
                    className="w-full px-2 py-1 border rounded text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500">PG 端口</label>
                  <input
                    type="number"
                    value={s.postgres_port}
                    onChange={(e) => {
                      const updated = [...slots];
                      updated[i] = { ...s, postgres_port: Number(e.target.value) };
                      setSlots(updated);
                    }}
                    className="w-full px-2 py-1 border rounded text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500">LLM 端口</label>
                  <input
                    type="number"
                    value={s.litellm_port}
                    onChange={(e) => {
                      const updated = [...slots];
                      updated[i] = { ...s, litellm_port: Number(e.target.value) };
                      setSlots(updated);
                    }}
                    className="w-full px-2 py-1 border rounded text-sm"
                  />
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="flex justify-end gap-2 pt-4 border-t">
          <button onClick={onClose} className="px-4 py-2 text-gray-600 border rounded-lg hover:bg-gray-100">取消</button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300"
          >
            {saving ? "保存中..." : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
