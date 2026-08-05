import type { EnvironmentSlot } from "../api/types";
import { Server, Database, Cpu, Globe } from "lucide-react";

interface Props {
  slot: EnvironmentSlot;
}

const statusColors: Record<string, string> = {
  available: "bg-green-100 text-green-700 border-green-300",
  occupied: "bg-blue-100 text-blue-700 border-blue-300",
  maintenance: "bg-yellow-100 text-yellow-700 border-yellow-300",
};

const statusLabels: Record<string, string> = {
  available: "空闲",
  occupied: "占用中",
  maintenance: "维护中",
};

export default function SlotCard({ slot }: Props) {
  const isLocal = !slot.host || slot.host === "localhost" || slot.host === "127.0.0.1";

  return (
    <div className={`rounded-xl border p-4 ${statusColors[slot.status] || "bg-gray-50 border-gray-200"}`}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-lg">{slot.name}</h3>
        <span className="text-xs px-2 py-0.5 rounded-full border">{statusLabels[slot.status]}</span>
      </div>
      <div className="space-y-1 text-sm">
        <div className="flex items-center gap-1.5">
          <Globe className="w-3.5 h-3.5" />
          <span>{isLocal ? "本地" : slot.host}</span>
          {!isLocal && <span className="text-xs opacity-60">(SSH:{slot.ssh_port})</span>}
        </div>
        <div className="flex items-center gap-1.5">
          <Server className="w-3.5 h-3.5" />
          <span>RCS: <code>:{slot.rcs_port}</code></span>
        </div>
        <div className="flex items-center gap-1.5">
          <Database className="w-3.5 h-3.5" />
          <span>PG: <code>:{slot.postgres_port}</code></span>
        </div>
        <div className="flex items-center gap-1.5">
          <Cpu className="w-3.5 h-3.5" />
          <span>LLM: <code>:{slot.litellm_port}</code></span>
        </div>
      </div>
      {slot.pipeline_pr_id && (
        <div className="mt-2 text-xs text-gray-600">
          PR #{slot.pipeline_pr_id} · {slot.pipeline_status}
        </div>
      )}
    </div>
  );
}
