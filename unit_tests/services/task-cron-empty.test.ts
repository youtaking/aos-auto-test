import { describe, expect, it } from "bun:test";

// ── validateTaskInput 空 cron 更新路径验证 ──
// 副本来源：src/services/task-v2.ts validateTaskInput
// R36 修复：更新模式下 cron="" 不再静默通过（data.cron !== undefined 确保空串也进入校验）

type CreateTaskV2Input = {
  name: string;
  description?: string;
  cron: string;
  timezone?: string | null;
  timeoutSeconds?: number;
  type: "http" | "agent";
  agentId?: string | null;
  definition: Record<string, unknown>;
};

function validateTaskInput(
  data: Partial<CreateTaskV2Input>,
  isUpdate = false,
): string | null {
  // cron 语义格式校验（5 字段 + 合法字符，Zod 只校验非空）。
  // 用 !== undefined 而非真值判断：更新路径传空串 cron 时也必须被拒绝（R36 不变量），
  // 否则空 cron 会被写入并仅靠 reschedule 时静默失败。
  if (data.cron !== undefined) {
    const parts = data.cron.trim().split(/\s+/);
    if (parts.length !== 5) return "cron 表达式必须为 5 字段（分 时 日 月 周）";
    const validPattern = /^[\d*/?\-,LW#]+$/;
    for (const part of parts) {
      if (!validPattern.test(part)) return `cron 字段 "${part}" 包含非法字符`;
    }
  }

  // 跨字段约束：agent 类型必须绑定 agentId（Zod schema 中 agentId 为 optional/nullable）
  if (!isUpdate && data.type === "agent" && !data.agentId) return "Agent 任务必须指定 agentId";

  return null;
}

describe("validateTaskInput: empty cron on update", () => {
  it("rejects empty string cron on update", () => {
    expect(validateTaskInput({ cron: "" }, true)).not.toBeNull();
  });

  it("rejects whitespace-only cron on update", () => {
    expect(validateTaskInput({ cron: "   " }, true)).not.toBeNull();
  });

  it("accepts valid cron on update", () => {
    expect(validateTaskInput({ cron: "*/5 * * * *" }, true)).toBeNull();
  });

  it("accepts undefined cron on update (cron not being updated)", () => {
    expect(validateTaskInput({}, true)).toBeNull();
  });

  it("rejects empty string cron on create", () => {
    expect(validateTaskInput({ type: "http", cron: "" })).not.toBeNull();
  });
});
