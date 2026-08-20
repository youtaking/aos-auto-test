// agent-file-service.test.ts — Agent 文件服务纯逻辑测试
// 测试目标：mapFileError 错误映射
// 业务意图：确保后端异常被正确映射为面向用户的 FileServiceError

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数/类 ──

type FileErrorType =
  | "validation_error"
  | "forbidden"
  | "not_found"
  | "version_conflict"
  | "payload_too_large"
  | "config_error"
  | "busy"
  | "file_service_unavailable";

class FileServiceError extends Error {
  type: FileErrorType;
  statusCode: number;
  constructor(message: string, type: FileErrorType, statusCode: number) {
    super(message);
    this.name = "FileServiceError";
    this.type = type;
    this.statusCode = statusCode;
  }
}

class BusyError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "BusyError";
  }
}

class AppError extends Error {
  code: string;
  statusCode: number;
  constructor(message: string, code: string, statusCode: number) {
    super(message);
    this.name = "AppError";
    this.code = code;
    this.statusCode = statusCode;
  }
}

function mapFileError(err: unknown): FileServiceError {
  if (err instanceof FileServiceError) return err;
  if (err instanceof BusyError) return new FileServiceError("文件服务繁忙，请稍后重试", "busy", 429);
  if (err instanceof AppError) {
    const byStatus: Record<number, FileErrorType> = {
      400: "validation_error",
      403: "forbidden",
      404: "not_found",
      409: "version_conflict",
      413: "payload_too_large",
      422: "config_error",
      429: "busy",
      503: "file_service_unavailable",
    };
    const type = byStatus[err.statusCode] ?? "file_service_unavailable";
    return new FileServiceError(err.message, type, err.statusCode);
  }
  return new FileServiceError("文件服务不可用，请稍后重试", "file_service_unavailable", 503);
}

// ── tests ──

describe("agent-file-service 文件服务", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("mapFileError 错误映射", () => {
    test("FileServiceError 原样返回", () => {
      const original = new FileServiceError("custom error", "not_found", 404);
      const result = mapFileError(original);
      expect(result).toBe(original);
    });

    test("BusyError 映射为 busy/429", () => {
      const result = mapFileError(new BusyError("too many requests"));
      expect(result.type).toBe("busy");
      expect(result.statusCode).toBe(429);
      expect(result.message).toBe("文件服务繁忙，请稍后重试");
    });

    test("AppError 400 映射为 validation_error", () => {
      const result = mapFileError(new AppError("bad input", "BAD_INPUT", 400));
      expect(result.type).toBe("validation_error");
      expect(result.statusCode).toBe(400);
      expect(result.message).toBe("bad input");
    });

    test("AppError 403 映射为 forbidden", () => {
      const result = mapFileError(new AppError("no access", "FORBIDDEN", 403));
      expect(result.type).toBe("forbidden");
      expect(result.statusCode).toBe(403);
    });

    test("AppError 404 映射为 not_found", () => {
      const result = mapFileError(new AppError("not found", "NOT_FOUND", 404));
      expect(result.type).toBe("not_found");
      expect(result.statusCode).toBe(404);
    });

    test("AppError 409 映射为 version_conflict", () => {
      const result = mapFileError(new AppError("conflict", "CONFLICT", 409));
      expect(result.type).toBe("version_conflict");
      expect(result.statusCode).toBe(409);
    });

    test("AppError 413 映射为 payload_too_large", () => {
      const result = mapFileError(new AppError("too large", "TOO_LARGE", 413));
      expect(result.type).toBe("payload_too_large");
      expect(result.statusCode).toBe(413);
    });

    test("AppError 422 映射为 config_error", () => {
      const result = mapFileError(new AppError("bad config", "CONFIG", 422));
      expect(result.type).toBe("config_error");
      expect(result.statusCode).toBe(422);
    });

    test("AppError 429 映射为 busy", () => {
      const result = mapFileError(new AppError("rate limited", "RATE_LIMIT", 429));
      expect(result.type).toBe("busy");
      expect(result.statusCode).toBe(429);
    });

    test("AppError 503 映射为 file_service_unavailable", () => {
      const result = mapFileError(new AppError("down", "DOWN", 503));
      expect(result.type).toBe("file_service_unavailable");
      expect(result.statusCode).toBe(503);
    });

    test("AppError 未知状态码降级为 file_service_unavailable", () => {
      const result = mapFileError(new AppError("weird", "WEIRD", 500));
      expect(result.type).toBe("file_service_unavailable");
      expect(result.statusCode).toBe(500);
    });

    test("裸 Error 降级为 503 file_service_unavailable", () => {
      const result = mapFileError(new Error("unexpected"));
      expect(result.type).toBe("file_service_unavailable");
      expect(result.statusCode).toBe(503);
      expect(result.message).toBe("文件服务不可用，请稍后重试");
    });

    test("字符串错误降级为 503", () => {
      const result = mapFileError("string error");
      expect(result.type).toBe("file_service_unavailable");
      expect(result.statusCode).toBe(503);
    });

    test("null 降级为 503", () => {
      const result = mapFileError(null);
      expect(result.type).toBe("file_service_unavailable");
      expect(result.statusCode).toBe(503);
    });
  });
});
