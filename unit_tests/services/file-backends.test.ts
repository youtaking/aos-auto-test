// file-backends.test.ts — If-Match 版本比对与安全上传纯函数测试
// 测试目标：etagEquals、assertVersionMatch、computeReadFingerprint、上传路径校验、errno 映射

import { describe, expect, test } from "bun:test";
import { isAbsolute, relative, resolve, sep } from "node:path";

// ── 复制纯函数（避免引入 workspace-fs / remote-file-service 依赖链）──

function etagEquals(ifMatch: string, etag: string): boolean {
  const normalize = (v: string) => v.trim().replace(/^W\//, "").replace(/^"|"$/g, "");
  return normalize(ifMatch) === normalize(etag);
}

function computeReadFingerprint(size: number, mtimeMs: number | undefined): string {
  if (mtimeMs === undefined || mtimeMs === 0) {
    return `size-${size}`;
  }
  return `"${size}-${mtimeMs}"`;
}

class FileServiceError extends Error {
  readonly type: string;
  readonly statusCode: number;
  readonly detail: unknown;
  constructor(message: string, type: string, statusCode: number, detail?: unknown) {
    super(message);
    this.name = "FileServiceError";
    this.type = type;
    this.statusCode = statusCode;
    this.detail = detail;
  }
}

function assertVersionMatch(
  ifMatch: string | undefined,
  displayPath: string,
  size: number,
  mtimeMs: number | undefined,
): void {
  if (ifMatch === undefined) return;
  if (ifMatch.trim() === "*") return;
  const currentEtag = computeReadFingerprint(size, mtimeMs);
  if (!etagEquals(ifMatch, currentEtag)) {
    throw new FileServiceError(`文件已被修改 (${displayPath})，请刷新后重试`, "version_conflict", 409, {
      etag: currentEtag,
      mtimeMs: mtimeMs ?? 0,
      size,
    });
  }
}

// ── etagEquals ──

describe("etagEquals", () => {
  test("完全相同字符串匹配", () => {
    expect(etagEquals("abc123", "abc123")).toBe(true);
  });

  test("带引号的 ETag 匹配无引号版本", () => {
    expect(etagEquals('"abc123"', "abc123")).toBe(true);
  });

  test("带 W/ 弱验证前缀匹配", () => {
    expect(etagEquals('W/"abc123"', "abc123")).toBe(true);
  });

  test("两端都有引号和弱前缀", () => {
    expect(etagEquals('W/"size-100-1234"', '"size-100-1234"')).toBe(true);
  });

  test("不匹配的值返回 false", () => {
    expect(etagEquals("abc", "def")).toBe(false);
  });

  test("空字符串匹配空字符串", () => {
    expect(etagEquals("", "")).toBe(true);
  });

  test("前后空格被 trim", () => {
    expect(etagEquals("  abc  ", "abc")).toBe(true);
  });

  test("大小写敏感", () => {
    expect(etagEquals("ABC", "abc")).toBe(false);
  });
});

// ── computeReadFingerprint ──

describe("computeReadFingerprint", () => {
  test("有 mtimeMs 时返回带引号的 size-mtime 格式", () => {
    expect(computeReadFingerprint(1024, 1700000000000)).toBe('"1024-1700000000000"');
  });

  test("mtimeMs 为 undefined 时退化为 size-only", () => {
    expect(computeReadFingerprint(512, undefined)).toBe("size-512");
  });

  test("mtimeMs 为 0 时退化为 size-only", () => {
    expect(computeReadFingerprint(256, 0)).toBe("size-256");
  });

  test("size 为 0 且有 mtimeMs 时正常返回", () => {
    expect(computeReadFingerprint(0, 1000)).toBe('"0-1000"');
  });
});

// ── assertVersionMatch ──

describe("assertVersionMatch", () => {
  test("ifMatch 为 undefined 时不抛异常", () => {
    expect(() => assertVersionMatch(undefined, "/test.txt", 100, 1000)).not.toThrow();
  });

  test("ifMatch 为 * 通配符时不抛异常", () => {
    expect(() => assertVersionMatch("*", "/test.txt", 100, 1000)).not.toThrow();
  });

  test("ifMatch 为 ' * ' 带空格时也不抛异常", () => {
    expect(() => assertVersionMatch(" * ", "/test.txt", 100, 1000)).not.toThrow();
  });

  test("版本匹配时不抛异常（带 mtime）", () => {
    const etag = computeReadFingerprint(100, 1000);
    expect(() => assertVersionMatch(etag, "/test.txt", 100, 1000)).not.toThrow();
  });

  test("版本匹配时不抛异常（size-only 弱指纹）", () => {
    const etag = computeReadFingerprint(200, undefined);
    expect(() => assertVersionMatch(etag, "/test.txt", 200, undefined)).not.toThrow();
  });

  test("版本不匹配时抛出 409 FileServiceError", () => {
    expect(() => assertVersionMatch('"old-etag"', "/test.txt", 100, 2000)).toThrow(FileServiceError);
  });

  test("409 错误包含 version_conflict 类型", () => {
    try {
      assertVersionMatch('"old-etag"', "/test.txt", 100, 2000);
      expect.unreachable("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(FileServiceError);
      expect((err as FileServiceError).type).toBe("version_conflict");
      expect((err as FileServiceError).statusCode).toBe(409);
    }
  });

  test("409 错误 detail 包含当前 etag", () => {
    try {
      assertVersionMatch('"old-etag"', "/test.txt", 100, 2000);
      expect.unreachable("should have thrown");
    } catch (err) {
      const detail = (err as FileServiceError).detail as Record<string, unknown>;
      expect(detail.etag).toBe('"100-2000"');
      expect(detail.size).toBe(100);
      expect(detail.mtimeMs).toBe(2000);
    }
  });

  test("错误消息包含文件路径", () => {
    try {
      assertVersionMatch('"wrong"', "/docs/readme.md", 50, 500);
      expect.unreachable("should have thrown");
    } catch (err) {
      expect((err as FileServiceError).message).toContain("/docs/readme.md");
    }
  });

  test("size-only 模式下 size 不同则冲突", () => {
    const etag = computeReadFingerprint(100, undefined);
    expect(() => assertVersionMatch(etag, "/test.txt", 200, undefined)).toThrow(FileServiceError);
  });
});

// ── 安全上传（plugin-sdk/secure-workspace-upload）──

class ValidationError extends Error {
  readonly type = "validation_error";
  readonly statusCode = 400;
  constructor(message: string) {
    super(message);
    this.name = "ValidationError";
  }
}

/** 复制 secure-workspace-upload 的路径校验部分（原生 openat 在纯函数测试中不执行）。 */
function resolveUploadLocalPath(workspace: string, path: string): string {
  const local = relative(resolve(workspace), resolve(workspace, path));
  if (!local || isAbsolute(path) || local === ".." || local.startsWith(`..${sep}`) || path.includes("\0"))
    throw new Error("Invalid upload path");
  return local;
}

/** 复制 errno → 错误码映射表。 */
function mapUploadErrno(platform: "darwin" | "linux", value: number): string {
  return (
    ({ 17: "EEXIST", 20: "ENOTDIR", [platform === "darwin" ? 62 : 40]: "ELOOP" } as Record<number, string>)[value] ??
    "EIO"
  );
}

/** file-backends 对上传错误的统一映射：符号链接/非目录 → 校验错误。 */
function mapUploadError(error: unknown): unknown {
  if (
    error instanceof Error &&
    "code" in error &&
    ["ELOOP", "ENOTDIR"].includes(String((error as NodeJS.ErrnoException).code ?? ""))
  )
    throw new ValidationError("上传目标路径包含 symbolic link");
  throw error;
}

describe("resolveUploadLocalPath 上传路径校验", () => {
  const workspace = resolve("workspace-root");

  test("工作区内相对路径被保留", () => {
    expect(resolveUploadLocalPath(workspace, "user/a.txt")).toBe(`user${sep}a.txt`);
    expect(resolveUploadLocalPath(workspace, "user/sub/a.txt")).toBe(`user${sep}sub${sep}a.txt`);
  });

  test("空路径被拒绝", () => {
    expect(() => resolveUploadLocalPath(workspace, "")).toThrow("Invalid upload path");
  });

  test("绝对路径被拒绝", () => {
    expect(() => resolveUploadLocalPath(workspace, resolve("external", "a.txt"))).toThrow("Invalid upload path");
  });

  test("逃出工作区的 .. 被拒绝", () => {
    expect(() => resolveUploadLocalPath(workspace, "../escape.txt")).toThrow("Invalid upload path");
    expect(() => resolveUploadLocalPath(workspace, "user/../../escape.txt")).toThrow("Invalid upload path");
  });

  test("路径中间含 .. 但仍在工作区内时允许", () => {
    expect(resolveUploadLocalPath(workspace, "user/sub/../a.txt")).toBe(`user${sep}a.txt`);
  });

  test("NUL 字符被拒绝", () => {
    expect(() => resolveUploadLocalPath(workspace, "user/a\0.txt")).toThrow("Invalid upload path");
  });
});

describe("mapUploadErrno errno 映射", () => {
  test("EEXIST 表示已存在", () => {
    expect(mapUploadErrno("linux", 17)).toBe("EEXIST");
  });

  test("ENOTDIR 表示路径段不是目录", () => {
    expect(mapUploadErrno("linux", 20)).toBe("ENOTDIR");
  });

  test("Linux 下 40 为 ELOOP（符号链接环）", () => {
    expect(mapUploadErrno("linux", 40)).toBe("ELOOP");
  });

  test("Darwin 下 62 为 ELOOP", () => {
    expect(mapUploadErrno("darwin", 62)).toBe("ELOOP");
  });

  test("未知 errno 退化为 EIO", () => {
    expect(mapUploadErrno("linux", 999)).toBe("EIO");
  });

  test("同一数值在平台间语义不同", () => {
    expect(mapUploadErrno("darwin", 40)).toBe("EIO");
  });
});

describe("mapUploadError 上传错误映射", () => {
  test("ELOOP 转为 400 校验错误", () => {
    const error = Object.assign(new Error("loop"), { code: "ELOOP" });
    expect(() => mapUploadError(error)).toThrow("上传目标路径包含 symbolic link");
  });

  test("ENOTDIR 转为 400 校验错误", () => {
    const error = Object.assign(new Error("notdir"), { code: "ENOTDIR" });
    expect(() => mapUploadError(error)).toThrow(ValidationError);
  });

  test("其他 errno 原样抛出", () => {
    const error = Object.assign(new Error("exists"), { code: "EEXIST" });
    expect(() => mapUploadError(error)).toThrow("exists");
  });

  test("普通错误原样抛出", () => {
    expect(() => mapUploadError(new Error("boom"))).toThrow("boom");
  });
});
