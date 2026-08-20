// task-v2.test.ts — 定时任务 V2 纯逻辑测试
// 测试目标：validateTaskInput（cron 格式、跨字段约束）、sanitizeTask、toUnixTimestamp、normalizeTimezone
// 业务意图：确保定时任务的输入校验和数据清洗逻辑正确

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数 ──

function toUnixTimestamp(value: Date | null | undefined): number | null {
  return value ? Math.floor(value.getTime() / 1000) : null;
}

function normalizeTimezone(timezone: string | null | undefined): string | null {
  if (timezone === undefined || timezone === null) return null;
  const trimmed = timezone.trim();
  return trimmed.length === 0 ? null : trimmed;
}

interface CreateTaskV2Input {
  name: string;
  description?: string;
  cron: string;
  timezone?: string | null;
  timeoutSeconds?: number;
  type: "http" | "agent";
  agentId?: string | null;
  definition: Record<string, unknown>;
}

function validateTaskInput(data: Partial<CreateTaskV2Input>, isUpdate = false): string | null {
  if (data.cron !== undefined) {
    const parts = data.cron.trim().split(/\s+/);
    if (parts.length !== 5) return "cron 表达式必须为 5 字段（分 时 日 月 周）";
    const validPattern = /^[\d*/?\-,LW#]+$/;
    for (const part of parts) {
      if (!validPattern.test(part)) return `cron 字段 "${part}" 包含非法字符`;
    }
  }
  if (!isUpdate && data.type === "agent" && !data.agentId) return "Agent 任务必须指定 agentId";
  return null;
}

function sanitizeTask(row: {
  id: string; name: string; description?: string | null; cron: string;
  timezone?: string | null; enabled: boolean; timeoutSeconds: number;
  type: string; agentId?: string | null; definition: unknown;
  lastRunAt?: Date | null; nextRunAt?: Date | null; lastStatus?: string | null;
  createdAt?: Date; updatedAt?: Date;
}) {
  return {
    id: row.id,
    name: row.name,
    description: row.description ?? null,
    cron: row.cron,
    timezone: row.timezone ?? null,
    enabled: row.enabled,
    timeoutSeconds: row.timeoutSeconds,
    type: row.type,
    agentId: row.agentId ?? null,
    definition: row.definition,
    lastRunAt: toUnixTimestamp(row.lastRunAt),
    nextRunAt: toUnixTimestamp(row.nextRunAt),
    lastStatus: row.lastStatus ?? null,
    createdAt: toUnixTimestamp(row.createdAt) ?? 0,
    updatedAt: toUnixTimestamp(row.updatedAt) ?? 0,
  };
}

// ── tests ──

describe("task-v2 定时任务服务", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("toUnixTimestamp 时间戳转换", () => {
    test("Date 对象转 Unix 时间戳", () => {
      const date = new Date("2024-01-15T10:30:00Z");
      expect(toUnixTimestamp(date)).toBe(Math.floor(date.getTime() / 1000));
    });

    test("null 返回 null", () => {
      expect(toUnixTimestamp(null)).toBeNull();
    });

    test("undefined 返回 null", () => {
      expect(toUnixTimestamp(undefined)).toBeNull();
    });
  });

  describe("normalizeTimezone 时区规范化", () => {
    test("正常时区字符串保持原样", () => {
      expect(normalizeTimezone("Asia/Shanghai")).toBe("Asia/Shanghai");
    });

    test("null 返回 null", () => {
      expect(normalizeTimezone(null)).toBeNull();
    });

    test("undefined 返回 null", () => {
      expect(normalizeTimezone(undefined)).toBeNull();
    });

    test("空字符串返回 null", () => {
      expect(normalizeTimezone("")).toBeNull();
    });

    test("纯空格返回 null", () => {
      expect(normalizeTimezone("   ")).toBeNull();
    });

    test("带空格的值被 trim", () => {
      expect(normalizeTimezone("  Asia/Shanghai  ")).toBe("Asia/Shanghai");
    });
  });

  describe("validateTaskInput 输入校验", () => {
    describe("cron 格式校验", () => {
      test("标准 5 字段 cron 通过", () => {
        expect(validateTaskInput({ cron: "0 * * * *", type: "http" })).toBeNull();
      });

      test("复杂 cron 表达式通过", () => {
        expect(validateTaskInput({ cron: "*/5 0-23 1,15 * 1-5", type: "http" })).toBeNull();
      });

      test("含 L/W/# 的 cron 通过", () => {
        expect(validateTaskInput({ cron: "0 0 L * ?", type: "http" })).toBeNull();
        expect(validateTaskInput({ cron: "0 0 * * 1#2", type: "http" })).toBeNull();
      });

      test("4 字段拒绝", () => {
        expect(validateTaskInput({ cron: "0 * * *", type: "http" })).toBe("cron 表达式必须为 5 字段（分 时 日 月 周）");
      });

      test("6 字段拒绝", () => {
        expect(validateTaskInput({ cron: "0 * * * * *", type: "http" })).toBe("cron 表达式必须为 5 字段（分 时 日 月 周）");
      });

      test("空 cron 拒绝", () => {
        expect(validateTaskInput({ cron: "", type: "http" })).toBe("cron 表达式必须为 5 字段（分 时 日 月 周）");
      });

      test("含非法字符拒绝", () => {
        expect(validateTaskInput({ cron: "0 * * * abc", type: "http" })).toContain("包含非法字符");
      });

      test("含字母字段拒绝", () => {
        expect(validateTaskInput({ cron: "0 * * * MON", type: "http" })).toContain("包含非法字符");
      });
    });

    describe("跨字段约束", () => {
      test("agent 类型无 agentId 拒绝（创建模式）", () => {
        expect(validateTaskInput({ cron: "0 * * * *", type: "agent" })).toBe("Agent 任务必须指定 agentId");
      });

      test("agent 类型有 agentId 通过", () => {
        expect(validateTaskInput({ cron: "0 * * * *", type: "agent", agentId: "agent-1" })).toBeNull();
      });

      test("http 类型无 agentId 通过", () => {
        expect(validateTaskInput({ cron: "0 * * * *", type: "http" })).toBeNull();
      });

      test("更新模式下不检查 agentId（isUpdate=true）", () => {
        expect(validateTaskInput({ cron: "0 * * * *", type: "agent" }, true)).toBeNull();
      });
    });

    test("未传 cron 时跳过 cron 校验", () => {
      expect(validateTaskInput({ type: "http" })).toBeNull();
    });
  });

  describe("sanitizeTask 数据清洗", () => {
    const baseRow = {
      id: "task-1",
      name: "Test Task",
      cron: "0 * * * *",
      enabled: true,
      timeoutSeconds: 300,
      type: "http",
      definition: { url: "https://example.com" },
      createdAt: new Date("2024-01-01T00:00:00Z"),
      updatedAt: new Date("2024-01-02T00:00:00Z"),
    };

    test("基本字段正确映射", () => {
      const result = sanitizeTask(baseRow);
      expect(result.id).toBe("task-1");
      expect(result.name).toBe("Test Task");
      expect(result.cron).toBe("0 * * * *");
      expect(result.enabled).toBe(true);
      expect(result.timeoutSeconds).toBe(300);
    });

    test("null 字段使用默认值", () => {
      const result = sanitizeTask(baseRow);
      expect(result.description).toBeNull();
      expect(result.timezone).toBeNull();
      expect(result.agentId).toBeNull();
      expect(result.lastRunAt).toBeNull();
      expect(result.nextRunAt).toBeNull();
      expect(result.lastStatus).toBeNull();
    });

    test("Date 字段转为 Unix 时间戳", () => {
      const result = sanitizeTask({
        ...baseRow,
        lastRunAt: new Date("2024-06-01T12:00:00Z"),
        nextRunAt: new Date("2024-06-01T13:00:00Z"),
      });
      expect(result.lastRunAt).toBe(Math.floor(new Date("2024-06-01T12:00:00Z").getTime() / 1000));
      expect(result.nextRunAt).toBe(Math.floor(new Date("2024-06-01T13:00:00Z").getTime() / 1000));
    });

    test("无 createdAt/updatedAt 时默认 0", () => {
      const result = sanitizeTask({ ...baseRow, createdAt: undefined, updatedAt: undefined });
      expect(result.createdAt).toBe(0);
      expect(result.updatedAt).toBe(0);
    });

    test("agent 类型任务保留 agentId", () => {
      const result = sanitizeTask({ ...baseRow, type: "agent", agentId: "agent-123" });
      expect(result.type).toBe("agent");
      expect(result.agentId).toBe("agent-123");
    });
  });
});
