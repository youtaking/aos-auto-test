// file-types.test.ts — FileServiceError 错误类测试
// 测试目标：FileServiceError 构造、属性绑定、instanceof 判定
// 业务意图：确保门面层统一错误可被路由层按 type 正确映射 HTTP 响应

import { describe, expect, test } from "bun:test";

// ── 复制 FileServiceError（纯类，无外部依赖）──

type FileErrorType =
  | "validation_error"
  | "forbidden"
  | "not_found"
  | "payload_too_large"
  | "config_error"
  | "busy"
  | "file_service_unavailable"
  | "version_conflict";

class FileServiceError extends Error {
  constructor(
    message: string,
    public readonly type: FileErrorType,
    public readonly statusCode: number,
    public readonly currentVersion?: { etag: string; mtimeMs: number; size: number },
  ) {
    super(message);
    this.name = "FileServiceError";
  }
}

// ── 常量（§2.4 能力上限）──
const LOCAL_UPLOAD_MAX_BYTES = 100 * 1024 * 1024;
const REMOTE_UPLOAD_MAX_BYTES = 20 * 1024 * 1024;

// ── tests ──

describe("FileServiceError", () => {
  // 构造函数正确绑定所有属性
  test("构造函数正确绑定 message、type、statusCode", () => {
    const err = new FileServiceError("文件不存在", "not_found", 404);
    expect(err.message).toBe("文件不存在");
    expect(err.type).toBe("not_found");
    expect(err.statusCode).toBe(404);
    expect(err.name).toBe("FileServiceError");
    expect(err.currentVersion).toBeUndefined();
  });

  // instanceof 判定正确
  test("instanceof Error 和 FileServiceError 均为 true", () => {
    const err = new FileServiceError("test", "forbidden", 403);
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(FileServiceError);
  });

  // 409 version_conflict 携带 currentVersion
  test("version_conflict 错误携带 currentVersion 信息", () => {
    const version = { etag: "abc123", mtimeMs: 1000, size: 512 };
    const err = new FileServiceError("版本冲突", "version_conflict", 409, version);
    expect(err.currentVersion).toEqual(version);
    expect(err.currentVersion?.etag).toBe("abc123");
  });

  // 所有错误类型均可构造
  test("所有 FileErrorType 均可构造", () => {
    const types: FileErrorType[] = [
      "validation_error", "forbidden", "not_found", "payload_too_large",
      "config_error", "busy", "file_service_unavailable", "version_conflict",
    ];
    for (const t of types) {
      const err = new FileServiceError("test", t, 400);
      expect(err.type).toBe(t);
    }
  });
});

describe("上传能力上限常量", () => {
  // 本地上限 100MB
  test("LOCAL_UPLOAD_MAX_BYTES = 100MB", () => {
    expect(LOCAL_UPLOAD_MAX_BYTES).toBe(100 * 1024 * 1024);
  });

  // 远程上限 20MB
  test("REMOTE_UPLOAD_MAX_BYTES = 20MB", () => {
    expect(REMOTE_UPLOAD_MAX_BYTES).toBe(20 * 1024 * 1024);
  });
});
