// system-log-service.test.ts — 系统日志服务纯函数测试
// 测试目标：parseLogEntry、entryMatchesQuery、isErrorEntry、toLogFile、文件名校验

import { describe, expect, test } from "bun:test";

// ── 复制纯函数 ──

interface SystemLogEntry {
  timestamp: string | null;
  level: string | null;
  module: string | null;
  requestId: string | null;
  message: string;
  error: { type: string | null; message: string | null; stack: string | null } | null;
}

interface SystemLogFile {
  name: string;
  size: number;
  modifiedAt: string;
  isErrorLog: boolean;
}

function parseLogEntry(line: string): SystemLogEntry {
  try {
    const value: unknown = JSON.parse(line);
    if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("not an object");

    const record = value as Record<string, unknown>;
    const error =
      typeof record.err === "object" && record.err !== null && !Array.isArray(record.err) ? record.err : null;
    const errorRecord = error as Record<string, unknown> | null;
    return {
      timestamp: typeof record.time === "string" ? record.time : null,
      level: typeof record.level === "string" ? record.level : null,
      module: typeof record.module === "string" ? record.module : null,
      requestId: typeof record.requestId === "string" ? record.requestId : null,
      message: typeof record.msg === "string" ? record.msg : line,
      error: errorRecord
        ? {
            type: typeof errorRecord.type === "string" ? errorRecord.type : null,
            message: typeof errorRecord.message === "string" ? errorRecord.message : null,
            stack: typeof errorRecord.stack === "string" ? errorRecord.stack : null,
          }
        : null,
    };
  } catch {
    return { timestamp: null, level: null, module: null, requestId: null, message: line, error: null };
  }
}

function entryMatchesQuery(entry: SystemLogEntry, query: string): boolean {
  return !query || JSON.stringify(entry).toLocaleLowerCase().includes(query);
}

function isErrorEntry(entry: SystemLogEntry): boolean {
  return entry.level?.toLocaleLowerCase() === "error" || /error/i.test(entry.message);
}

const LOG_FILE_PATTERN = /^[^/\\\0]+\.log$/i;

function toLogFile(name: string, size: number, mtime: Date): SystemLogFile {
  return {
    name,
    size,
    modifiedAt: mtime.toISOString(),
    isErrorLog: /(?:^|[._-])err(?:or)?(?:[._-]|$)/i.test(name),
  };
}

// ── Tests ──

describe("parseLogEntry", () => {
  test("合法 JSON 日志行解析所有字段", () => {
    const line = JSON.stringify({
      time: "2026-01-01T00:00:00Z",
      level: "info",
      module: "auth",
      requestId: "req-123",
      msg: "User logged in",
    });
    const entry = parseLogEntry(line);
    expect(entry.timestamp).toBe("2026-01-01T00:00:00Z");
    expect(entry.level).toBe("info");
    expect(entry.module).toBe("auth");
    expect(entry.requestId).toBe("req-123");
    expect(entry.message).toBe("User logged in");
    expect(entry.error).toBeNull();
  });

  test("含 err 对象的日志解析 error 字段", () => {
    const line = JSON.stringify({
      time: "2026-01-01T00:00:00Z",
      level: "error",
      msg: "Something failed",
      err: { type: "TypeError", message: "undefined is not a function", stack: "at foo.js:1" },
    });
    const entry = parseLogEntry(line);
    expect(entry.error).not.toBeNull();
    expect(entry.error!.type).toBe("TypeError");
    expect(entry.error!.message).toBe("undefined is not a function");
    expect(entry.error!.stack).toBe("at foo.js:1");
  });

  test("err 为非对象值时 error 为 null", () => {
    const line = JSON.stringify({ msg: "test", err: "string error" });
    const entry = parseLogEntry(line);
    expect(entry.error).toBeNull();
  });

  test("err 为数组时 error 为 null", () => {
    const line = JSON.stringify({ msg: "test", err: [1, 2, 3] });
    const entry = parseLogEntry(line);
    expect(entry.error).toBeNull();
  });

  test("非 JSON 行回退为原始消息", () => {
    const entry = parseLogEntry("plain text log line");
    expect(entry.message).toBe("plain text log line");
    expect(entry.timestamp).toBeNull();
    expect(entry.level).toBeNull();
    expect(entry.module).toBeNull();
    expect(entry.error).toBeNull();
  });

  test("JSON 数组行回退为原始消息", () => {
    const line = "[1,2,3]";
    const entry = parseLogEntry(line);
    expect(entry.message).toBe(line);
    expect(entry.timestamp).toBeNull();
  });

  test("JSON null 回退为原始消息", () => {
    const entry = parseLogEntry("null");
    expect(entry.message).toBe("null");
  });

  test("缺少 msg 字段时使用原始行作为 message", () => {
    const line = JSON.stringify({ time: "2026-01-01", level: "debug" });
    const entry = parseLogEntry(line);
    expect(entry.message).toBe(line);
    expect(entry.timestamp).toBe("2026-01-01");
  });

  test("err 中部分字段缺失时对应为 null", () => {
    const line = JSON.stringify({
      msg: "partial error",
      err: { message: "only message" },
    });
    const entry = parseLogEntry(line);
    expect(entry.error!.type).toBeNull();
    expect(entry.error!.message).toBe("only message");
    expect(entry.error!.stack).toBeNull();
  });

  test("空字符串行回退为原始消息", () => {
    const entry = parseLogEntry("");
    expect(entry.message).toBe("");
    expect(entry.timestamp).toBeNull();
  });
});

// ── entryMatchesQuery ──

describe("entryMatchesQuery", () => {
  const baseEntry: SystemLogEntry = {
    timestamp: "2026-01-01",
    level: "info",
    module: "auth",
    requestId: "req-1",
    message: "User logged in successfully",
    error: null,
  };

  test("空查询匹配所有条目", () => {
    expect(entryMatchesQuery(baseEntry, "")).toBe(true);
  });

  test("已 lowercased 的查询匹配 message 内容", () => {
    expect(entryMatchesQuery(baseEntry, "user logged")).toBe(true);
  });

  test("大写查询不匹配（调用方需预转换小写）", () => {
    // entryMatchesQuery 只对 entry 做 toLocaleLowerCase，query 需调用方预归一化
    expect(entryMatchesQuery(baseEntry, "USER LOGGED")).toBe(false);
  });

  test("匹配 module 字段", () => {
    expect(entryMatchesQuery(baseEntry, "auth")).toBe(true);
  });

  test("不匹配返回 false", () => {
    expect(entryMatchesQuery(baseEntry, "nonexistent-keyword")).toBe(false);
  });

  test("匹配 requestId", () => {
    expect(entryMatchesQuery(baseEntry, "req-1")).toBe(true);
  });
});

// ── isErrorEntry ──

describe("isErrorEntry", () => {
  test("level 为 error 时返回 true", () => {
    const entry: SystemLogEntry = {
      timestamp: null, level: "error", module: null, requestId: null, message: "ok", error: null,
    };
    expect(isErrorEntry(entry)).toBe(true);
  });

  test("level 为 ERROR（大写）时返回 true", () => {
    const entry: SystemLogEntry = {
      timestamp: null, level: "ERROR", module: null, requestId: null, message: "ok", error: null,
    };
    expect(isErrorEntry(entry)).toBe(true);
  });

  test("message 包含 error 时返回 true", () => {
    const entry: SystemLogEntry = {
      timestamp: null, level: "warn", module: null, requestId: null, message: "an error occurred", error: null,
    };
    expect(isErrorEntry(entry)).toBe(true);
  });

  test("level 为 info 且 message 无 error 时返回 false", () => {
    const entry: SystemLogEntry = {
      timestamp: null, level: "info", module: null, requestId: null, message: "all good", error: null,
    };
    expect(isErrorEntry(entry)).toBe(false);
  });

  test("level 为 null 且 message 无 error 时返回 false", () => {
    const entry: SystemLogEntry = {
      timestamp: null, level: null, module: null, requestId: null, message: "plain text", error: null,
    };
    expect(isErrorEntry(entry)).toBe(false);
  });
});

// ── LOG_FILE_PATTERN ──

describe("LOG_FILE_PATTERN", () => {
  test("合法文件名: app.log", () => {
    expect(LOG_FILE_PATTERN.test("app.log")).toBe(true);
  });

  test("合法文件名: error.2026.log", () => {
    expect(LOG_FILE_PATTERN.test("error.2026.log")).toBe(true);
  });

  test("大写扩展名: APP.LOG", () => {
    expect(LOG_FILE_PATTERN.test("APP.LOG")).toBe(true);
  });

  test("含路径分隔符非法: ../etc.log", () => {
    expect(LOG_FILE_PATTERN.test("../etc.log")).toBe(false);
  });

  test("含反斜杠非法: dir\\file.log", () => {
    expect(LOG_FILE_PATTERN.test("dir\\file.log")).toBe(false);
  });

  test("非 .log 扩展名: app.txt", () => {
    expect(LOG_FILE_PATTERN.test("app.txt")).toBe(false);
  });

  test("空文件名不匹配", () => {
    expect(LOG_FILE_PATTERN.test("")).toBe(false);
  });
});

// ── toLogFile ──

describe("toLogFile", () => {
  test("普通日志文件 isErrorLog=false", () => {
    const file = toLogFile("app.log", 1024, new Date("2026-01-01"));
    expect(file.name).toBe("app.log");
    expect(file.size).toBe(1024);
    expect(file.isErrorLog).toBe(false);
  });

  test("error 前缀文件名 isErrorLog=true", () => {
    const file = toLogFile("error.log", 512, new Date("2026-01-01"));
    expect(file.isErrorLog).toBe(true);
  });

  test("err 后缀文件名 isErrorLog=true", () => {
    const file = toLogFile("app.err.log", 256, new Date("2026-01-01"));
    expect(file.isErrorLog).toBe(true);
  });

  test("含 error 中缀的文件名 isErrorLog=true", () => {
    const file = toLogFile("app-error-2026.log", 128, new Date("2026-01-01"));
    expect(file.isErrorLog).toBe(true);
  });

  test("modifiedAt 为 ISO 字符串", () => {
    const date = new Date("2026-06-15T12:30:00Z");
    const file = toLogFile("test.log", 100, date);
    expect(file.modifiedAt).toBe(date.toISOString());
  });
});
