import { useEffect, useState } from "react";
import { GitBranch } from "lucide-react";
import { listBranches, type BranchInfo } from "../api/branches";

interface Props {
  value: string;
  onChange: (branch: string) => void;
}

export default function BranchSelector({ value, onChange }: Props) {
  const [branches, setBranches] = useState<BranchInfo[]>([]);

  useEffect(() => {
    listBranches()
      .then((data) => {
        // 确保 main 始终在列表中
        const hasMain = data.some((b) => b.branch_name === "main");
        if (!hasMain) {
          data.unshift({
            branch_name: "main",
            last_commit_sha: "",
            pr_number: null,
            dev_status: "up_to_date",
            case_status: "active",
            discovered_at: null,
            updated_at: null,
            has_dir: false,
          });
        }
        setBranches(data);
      })
      .catch(console.error);
  }, []);

  return (
    <div className="flex items-center gap-2">
      <GitBranch className="w-4 h-4 text-gray-500" />
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="px-3 py-1.5 border rounded-lg text-sm font-medium bg-white hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {branches.map((b) => (
          <option key={b.branch_name} value={b.branch_name}>
            {b.branch_name}
            {b.dev_status === "merged" ? " (已合入)" : ""}
            {b.dev_status === "closed" ? " (已关闭)" : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
