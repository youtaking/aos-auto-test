import { describe, expect, it } from "bun:test";

// 复制 task-v2.ts 内部验证逻辑进行纯单元测试（private 函数无法直接 import）
// 覆盖 validateCron、normalizeTimezone、validateTaskInput 的边界场景

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

function validateCron(cron: string): string | null {
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return "cron 表达式必须为 5 字段（分 时 日 月 周）";
  const validPattern = /^[\d*/?\-,LW#]+$/;
  for (const part of parts) {
    if (!validPattern.test(part)) return `cron 字段 "${part}" 包含非法字符`;
  }
  return null;
}

function normalizeTimezone(timezone: string | null | undefined): string | null {
  if (timezone === undefined || timezone === null) return null;
  const trimmed = timezone.trim();
  return trimmed.length === 0 ? null : trimmed;
}

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

// ── validateCron ──

describe("validateCron", () => {
  it("接受标准的 5 字段 cron", () => {
    expect(validateCron("*/5 * * * *")).toBeNull();
    expect(validateCron("0 12 * * 1")).toBeNull();
    expect(validateCron("30 4 1 1 *")).toBeNull();
  });

  it("拒绝非 5 字段表达式", () => {
    expect(validateCron("* * *")).not.toBeNull();
    expect(validateCron("* * * * * *")).not.toBeNull();
    expect(validateCron("")).not.toBeNull();
  });

  it("拒绝包含非法字符的字段", () => {
    expect(validateCron("abc * * * *")).not.toBeNull();
    expect(validateCron("0 0 * * SUN")).not.toBeNull();
  });

  it("接受合法 cron 特殊字符", () => {
    expect(validateCron("*/5 * * * *")).toBeNull();
    expect(validateCron("1-30 * * * *")).toBeNull();
    expect(validateCron("1,15 * * * *")).toBeNull();
  });

  it("自动 trim 前后空白", () => {
    expect(validateCron("  */5 * * * *  ")).toBeNull();
  });
});

// ── normalizeTimezone ──

describe("normalizeTimezone", () => {
  it("null/undefined 返回 null", () => {
    expect(normalizeTimezone(null)).toBeNull();
    expect(normalizeTimezone(undefined)).toBeNull();
  });

  it("空字符串返回 null", () => {
    expect(normalizeTimezone("")).toBeNull();
  });

  it("纯空白字符串返回 null", () => {
    expect(normalizeTimezone("   ")).toBeNull();
  });

  it("保留有效时区字符串", () => {
    expect(normalizeTimezone("UTC")).toBe("UTC");
    expect(normalizeTimezone("Asia/Shanghai")).toBe("Asia/Shanghai");
    expect(normalizeTimezone("America/New_York")).toBe("America/New_York");
  });

  it("trim 两侧空白", () => {
    expect(normalizeTimezone("  UTC  ")).toBe("UTC");
  });
});

// ── validateTaskInput ──

describe("validateTaskInput", () => {
  it("未提供 cron 时不报错（cron 校验跳过）", () => {
    expect(validateTaskInput({})).toBeNull();
    expect(validateTaskInput({ type: "http" })).toBeNull();
  });

  it("提供有效 cron 时通过", () => {
    expect(validateTaskInput({ type: "http", cron: "* * * * *" })).toBeNull();
  });

  it("拒绝非法 cron 表达式", () => {
    expect(validateTaskInput({ type: "http", cron: "* * *" })).not.toBeNull();
    expect(validateTaskInput({ type: "http", cron: "abc * * * *" })).not.toBeNull();
  });

  it("拒绝空字符串 cron", () => {
    expect(validateTaskInput({ type: "http", cron: "" })).not.toBeNull();
  });

  it("创建模式：agent 类型缺少 agentId 报错", () => {
    expect(validateTaskInput({ type: "agent", cron: "* * * * *" })).toBe(
      "Agent 任务必须指定 agentId",
    );
  });

  it("创建模式：agent 类型带 agentId 通过", () => {
    expect(
      validateTaskInput({ type: "agent", cron: "* * * * *", agentId: "agent-1" }),
    ).toBeNull();
  });

  it("创建模式：agent 类型 agentId 为空字符串时报错（falsy）", () => {
    expect(
      validateTaskInput({ type: "agent", cron: "* * * * *", agentId: "" }),
    ).toBe("Agent 任务必须指定 agentId");
  });

  it("创建模式：agent 类型 agentId 为 null 时报错", () => {
    expect(
      validateTaskInput({ type: "agent", cron: "* * * * *", agentId: null }),
    ).toBe("Agent 任务必须指定 agentId");
  });

  it("创建模式：http 类型不需要 agentId", () => {
    expect(validateTaskInput({ type: "http", cron: "* * * * *" })).toBeNull();
  });

  it("更新模式：不强制 agentId 要求", () => {
    expect(validateTaskInput({ type: "agent", cron: "* * * * *" }, true)).toBeNull();
  });

  it("更新模式：空串 cron 被拒绝（R36 不变量）", () => {
    expect(validateTaskInput({ cron: "" }, true)).not.toBeNull();
  });

  it("更新模式：未提供 cron 时通过", () => {
    expect(validateTaskInput({ name: "new-name" }, true)).toBeNull();
  });

  it("不校验 name/url/method 等字段（由 Zod schema 负责）", () => {
    // 源码 validateTaskInput 不校验 name、url、method，这些由 Zod schema 层处理
    expect(validateTaskInput({ type: "http", cron: "*/5 * * * *" })).toBeNull();
    // 即使 name 为空也不会报错（源码不校验 name）
    expect(validateTaskInput({ type: "http", cron: "*/5 * * * *", name: "" })).toBeNull();
  });
});
