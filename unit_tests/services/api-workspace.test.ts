// api-workspace.test.ts — v1 Workspace 上传/下载/文件树纯逻辑测试
// 测试目标：uploadWorkspaceFiles / getWorkspaceFileTree / downloadWorkspaceFile
// 业务意图：确保整批上传先校验后执行、重复目标被拒、文件服务错误正确映射为 HTTP 语义
// 源：packages/resources/machine/src/server/services/api-workspace.ts（main a7f477a9e）

import { beforeEach, describe, expect, mock, test } from "bun:test";
import { once } from "node:events";
import { posix } from "node:path";
import { Readable } from "node:stream";

// ── 复制纯逻辑（执行面 createAgentFileService 通过 deps 注入） ──

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

class ValidationError extends AppError {
  constructor(message: string) {
    super(message, "VALIDATION_ERROR", 400);
    this.name = "ValidationError";
  }
}

type FileErrorType =
  | "validation_error"
  | "forbidden"
  | "not_found"
  | "path_conflict"
  | "version_conflict"
  | "payload_too_large"
  | "config_error"
  | "busy"
  | "file_service_unavailable";

class FileServiceError extends Error {
  constructor(
    message: string,
    public readonly type: FileErrorType,
    public readonly statusCode: number,
  ) {
    super(message);
    this.name = "FileServiceError";
  }
}

const LOCAL_UPLOAD_MAX_BYTES = 92 * 1024 * 1024;

function hasPathControlCharacter(value: string): boolean {
  for (let i = 0; i < value.length; i++) {
    const code = value.charCodeAt(i);
    if (code <= 0x1f || code === 0x7f || (code >= 0x80 && code <= 0x9f)) return true;
  }
  return false;
}

function isAbsolutePath(p: string): boolean {
  if (p.startsWith("/")) return true;
  return /^[a-zA-Z]:[\\/]/.test(p);
}

function assertSafePath(path: string): void {
  if (hasPathControlCharacter(path)) throw new ValidationError("路径不合法：不允许控制字符");
  const trimmed = path.trim();
  if (!trimmed) return;
  if (isAbsolutePath(trimmed)) throw new ValidationError("路径不合法：不允许绝对路径");
  for (const segment of trimmed.split(/[\\/]+/)) {
    if (segment === "..") throw new ValidationError("路径不合法：不允许 `..` 段");
  }
}

function normalizeUploadRelativePath(relPath: unknown): string | null {
  if (relPath === undefined) return "";
  if (typeof relPath !== "string") return null;
  const trimmed = relPath.trim();
  if (!trimmed) return "";
  if (trimmed === ".") return null;
  if (isAbsolutePath(trimmed)) return null;
  if (hasPathControlCharacter(trimmed)) return null;
  for (const segment of trimmed.split(/[\\/]+/)) {
    if (segment === "..") return null;
  }
  return trimmed;
}

interface UploadInput {
  name: string;
  relativePath: string;
  content: Uint8Array;
}

interface TreeResultLike {
  paths: string[];
  mtimes?: Record<string, number>;
  errors?: Array<{ path: string; message: string }>;
}

interface FileServiceLike {
  tree(): Promise<TreeResultLike>;
  read(path: string, mode: "binary"): Promise<
    | { type: "binary"; name: string; stream: NodeJS.ReadableStream }
    | { type: "text"; name: string; content: string }
  >;
  upload(dir: string, inputs: UploadInput[]): Promise<{ files: Array<{ name: string; path: string; size: number }> }>;
}

const defaults = {
  createAgentFileService: (_scope: { environmentId: string; actorId: string; source: "api" }): FileServiceLike => {
    throw new Error("not configured");
  },
};
let overrides: Partial<typeof defaults> | null = null;
function setApiWorkspaceDeps(next: Partial<typeof defaults> | null): void {
  overrides = next;
}

interface WorkspaceFileTreeResult {
  environmentId: string;
  paths: string[];
  mtimes?: Record<string, number>;
  errors?: Array<{ path: string; message: string }>;
}

async function getWorkspaceFileTree(environmentId: string, actorId: string): Promise<WorkspaceFileTreeResult> {
  const service = (overrides?.createAgentFileService ?? defaults.createAgentFileService)({
    environmentId,
    actorId,
    source: "api",
  });
  const result = await service.tree();
  return {
    environmentId,
    paths: [...result.paths],
    ...(result.mtimes ? { mtimes: { ...result.mtimes } } : {}),
    ...(result.errors?.length
      ? { errors: result.errors.map(({ path }) => ({ path, message: "Directory could not be read" })) }
      : {}),
  };
}

async function downloadWorkspaceFile(
  environmentId: string,
  path: string,
  actorId: string,
): Promise<{ name: string; stream: Readable }> {
  const service = (overrides?.createAgentFileService ?? defaults.createAgentFileService)({
    environmentId,
    actorId,
    source: "api",
  });
  const result = await service.read(path, "binary");
  if (result.type !== "binary" || !(result.stream instanceof Readable))
    throw new AppError("Unexpected file download result", "INTERNAL_ERROR", 500);
  const stream = result.stream;
  try {
    if (stream.readableLength === 0 && !stream.readableEnded) await once(stream, "readable");
  } catch (error) {
    stream.destroy();
    throw mapFileError(error);
  }
  return { name: result.name, stream: result.stream };
}

function mapFileError(err: unknown): FileServiceError {
  if (err instanceof FileServiceError) return err;
  if (err instanceof AppError) {
    return new FileServiceError(err.message, "file_service_unavailable", err.statusCode);
  }
  return new FileServiceError("文件服务不可用，请稍后重试", "file_service_unavailable", 503);
}

function assertUploadSize(size: number): void {
  if (size > LOCAL_UPLOAD_MAX_BYTES) throw new AppError("Single file limit is 92 MiB", "PAYLOAD_TOO_LARGE", 413);
}

async function uploadWorkspaceFiles(
  environmentId: string,
  formData: FormData,
  actorId: string,
): Promise<{ environmentId: string; files: Array<{ name: string; path: string; size: number }> }> {
  const entries = formData.getAll("files");
  if (entries.length === 0 || entries.some((file) => !(file instanceof File)))
    throw new ValidationError("Files required");
  const files = entries as File[];
  const rawDir = formData.get("path") ?? "user";
  if (typeof rawDir !== "string") throw new ValidationError("Invalid path");
  assertSafePath(rawDir);
  const normalizedDir = posix.normalize(rawDir).replace(/\/$/, "");
  const dir = normalizedDir === "." ? "" : normalizedDir;
  let paths: string[] | undefined;
  const rawPaths = formData.get("relativePaths");
  if (rawPaths !== null) {
    try {
      const parsed: unknown = JSON.parse(String(rawPaths));
      if (!Array.isArray(parsed) || parsed.length !== files.length || parsed.some((path) => typeof path !== "string"))
        throw new Error("invalid");
      paths = parsed;
    } catch {
      throw new ValidationError("relativePaths must match files");
    }
  }
  const targets = new Set<string>();
  const validated = files.map((file, index) => {
    const path = paths?.[index] ?? file.name;
    if (!normalizeUploadRelativePath(file.name) || !normalizeUploadRelativePath(path))
      throw new ValidationError("Invalid upload path");
    const normalized = posix.normalize(path);
    if (targets.has(normalized)) throw new ValidationError("Duplicate upload target");
    targets.add(normalized);
    assertUploadSize(file.size);
    return { file, path: normalized };
  });
  const inputs = await Promise.all(
    validated.map(async ({ file, path }) => ({
      name: file.name,
      relativePath: path,
      content: new Uint8Array(await file.arrayBuffer()),
    })),
  );
  const service = (overrides?.createAgentFileService ?? defaults.createAgentFileService)({
    environmentId,
    actorId,
    source: "api",
  });
  try {
    const result = await service.upload(dir, inputs);
    return { environmentId, files: result.files };
  } catch (error) {
    if (error instanceof FileServiceError)
      throw new AppError(
        error.statusCode >= 500 ? "File service unavailable" : error.message,
        error.type.toUpperCase(),
        error.statusCode,
      );
    throw error;
  }
}

// ── 测试辅助 ──

function makeForm(files: Array<{ name: string; content?: string }>, extra: Record<string, string> = {}): FormData {
  const form = new FormData();
  for (const file of files) form.append("files", new File([file.content ?? "data"], file.name));
  for (const [key, value] of Object.entries(extra)) form.append(key, value);
  return form;
}

function fakeService(overrides: Partial<FileServiceLike> = {}): FileServiceLike {
  return {
    tree: mock(async () => ({ paths: ["user/a.txt"] })),
    read: mock(async (_path: string) => ({
      type: "binary" as const,
      name: "a.txt",
      stream: Readable.from([Buffer.from("hi")]),
    })),
    upload: mock(async (_dir: string, inputs: UploadInput[]) => ({
      files: inputs.map((input) => ({ name: input.name, path: `user/${input.relativePath}`, size: input.content.length })),
    })),
    ...overrides,
  };
}

// ── tests ──

describe("api-workspace v1 工作区文件接口", () => {
  beforeEach(() => {
    mock.restore();
    setApiWorkspaceDeps(null);
  });

  describe("uploadWorkspaceFiles 整批校验", () => {
    test("无文件时抛 ValidationError", async () => {
      await expect(uploadWorkspaceFiles("env-1", new FormData(), "actor-1")).rejects.toMatchObject({
        code: "VALIDATION_ERROR",
        message: "Files required",
      });
    });

    test("path 不是字符串时拒绝", async () => {
      const form = makeForm([{ name: "a.txt" }]);
      form.append("path", new File(["x"], "path.bin"));
      await expect(uploadWorkspaceFiles("env-1", form, "actor-1")).rejects.toThrow("Invalid path");
    });

    test("默认目录为 user", async () => {
      const service = fakeService();
      setApiWorkspaceDeps({ createAgentFileService: () => service });
      await uploadWorkspaceFiles("env-1", makeForm([{ name: "a.txt" }]), "actor-1");
      expect(service.upload).toHaveBeenCalledWith("user", [expect.objectContaining({ relativePath: "a.txt" })]);
    });

    test("目录尾部斜杠被去掉", async () => {
      const service = fakeService();
      setApiWorkspaceDeps({ createAgentFileService: () => service });
      await uploadWorkspaceFiles("env-1", makeForm([{ name: "a.txt" }], { path: "user/docs/" }), "actor-1");
      expect(service.upload).toHaveBeenCalledWith("user/docs", expect.any(Array));
    });

    test("目录为 . 时归一化为空串", async () => {
      const service = fakeService();
      setApiWorkspaceDeps({ createAgentFileService: () => service });
      await uploadWorkspaceFiles("env-1", makeForm([{ name: "a.txt" }], { path: "." }), "actor-1");
      expect(service.upload).toHaveBeenCalledWith("", expect.any(Array));
    });

    test("绝对路径目录被拒绝", async () => {
      await expect(
        uploadWorkspaceFiles("env-1", makeForm([{ name: "a.txt" }], { path: "/etc" }), "actor-1"),
      ).rejects.toThrow("不允许绝对路径");
    });

    test("含 .. 段的目录被拒绝", async () => {
      await expect(
        uploadWorkspaceFiles("env-1", makeForm([{ name: "a.txt" }], { path: "user/../etc" }), "actor-1"),
      ).rejects.toThrow("不允许 `..` 段");
    });

    test("relativePaths 非法 JSON 被拒绝", async () => {
      await expect(
        uploadWorkspaceFiles("env-1", makeForm([{ name: "a.txt" }], { relativePaths: "not-json" }), "actor-1"),
      ).rejects.toThrow("relativePaths must match files");
    });

    test("relativePaths 长度与文件数不一致被拒绝", async () => {
      await expect(
        uploadWorkspaceFiles("env-1", makeForm([{ name: "a.txt" }], { relativePaths: '["a.txt","b.txt"]' }), "actor-1"),
      ).rejects.toThrow("relativePaths must match files");
    });

    test("relativePaths 含非字符串元素被拒绝", async () => {
      await expect(
        uploadWorkspaceFiles("env-1", makeForm([{ name: "a.txt" }], { relativePaths: "[42]" }), "actor-1"),
      ).rejects.toThrow("relativePaths must match files");
    });

    test("relativePaths 正常写入目标路径", async () => {
      const service = fakeService();
      setApiWorkspaceDeps({ createAgentFileService: () => service });
      await uploadWorkspaceFiles(
        "env-1",
        makeForm([{ name: "a.txt", content: "hello" }], { relativePaths: '["sub/a.txt"]' }),
        "actor-1",
      );
      expect(service.upload).toHaveBeenCalledWith("user", [
        expect.objectContaining({ name: "a.txt", relativePath: "sub/a.txt" }),
      ]);
    });

    test("文件名含 .. 段时整批拒绝", async () => {
      await expect(
        uploadWorkspaceFiles("env-1", makeForm([{ name: "../evil.txt" }]), "actor-1"),
      ).rejects.toThrow("Invalid upload path");
    });

    test("relativePaths 指向 .. 时整批拒绝", async () => {
      await expect(
        uploadWorkspaceFiles(
          "env-1",
          makeForm([{ name: "a.txt" }], { relativePaths: '["../escape.txt"]' }),
          "actor-1",
        ),
      ).rejects.toThrow("Invalid upload path");
    });

    test("重复目标路径被拒绝", async () => {
      await expect(
        uploadWorkspaceFiles("env-1", makeForm([{ name: "a.txt" }, { name: "b.txt" }], { relativePaths: '["x/a.txt","x/a.txt"]' }), "actor-1"),
      ).rejects.toThrow("Duplicate upload target");
    });

    test("恰好 92MiB 允许上传", () => {
      expect(() => assertUploadSize(LOCAL_UPLOAD_MAX_BYTES)).not.toThrow();
    });

    test("超过 92MiB 单文件上限返回 413", () => {
      expect(() => assertUploadSize(LOCAL_UPLOAD_MAX_BYTES + 1)).toThrow("Single file limit is 92 MiB");
      try {
        assertUploadSize(LOCAL_UPLOAD_MAX_BYTES + 1);
      } catch (error) {
        expect(error).toMatchObject({ code: "PAYLOAD_TOO_LARGE", statusCode: 413 });
      }
    });

    test("成功时透传 environmentId 与执行面结果", async () => {
      const service = fakeService();
      setApiWorkspaceDeps({ createAgentFileService: () => service });
      const result = await uploadWorkspaceFiles("env-1", makeForm([{ name: "a.txt" }]), "actor-9");
      expect(result).toEqual({ environmentId: "env-1", files: [{ name: "a.txt", path: "user/a.txt", size: 4 }] });
    });

    test("以 api 来源与 actorId 构造执行面", async () => {
      const createAgentFileService = mock(() => fakeService());
      setApiWorkspaceDeps({ createAgentFileService });
      await uploadWorkspaceFiles("env-1", makeForm([{ name: "a.txt" }]), "actor-9");
      expect(createAgentFileService).toHaveBeenCalledWith({ environmentId: "env-1", actorId: "actor-9", source: "api" });
    });

    test("文件服务 4xx 错误保留 message 并转大写错误码", async () => {
      const service = fakeService({
        upload: mock(async () => {
          throw new FileServiceError("目标已存在", "path_conflict", 409);
        }),
      });
      setApiWorkspaceDeps({ createAgentFileService: () => service });
      await expect(uploadWorkspaceFiles("env-1", makeForm([{ name: "a.txt" }]), "actor-1")).rejects.toMatchObject({
        message: "目标已存在",
        code: "PATH_CONFLICT",
        statusCode: 409,
      });
    });

    test("文件服务 5xx 错误脱敏为 File service unavailable", async () => {
      const service = fakeService({
        upload: mock(async () => {
          throw new FileServiceError("内部堆栈细节", "file_service_unavailable", 503);
        }),
      });
      setApiWorkspaceDeps({ createAgentFileService: () => service });
      await expect(uploadWorkspaceFiles("env-1", makeForm([{ name: "a.txt" }]), "actor-1")).rejects.toMatchObject({
        message: "File service unavailable",
        code: "FILE_SERVICE_UNAVAILABLE",
        statusCode: 503,
      });
    });

    test("非 FileServiceError 原样抛出", async () => {
      const service = fakeService({
        upload: mock(async () => {
          throw new Error("unexpected");
        }),
      });
      setApiWorkspaceDeps({ createAgentFileService: () => service });
      await expect(uploadWorkspaceFiles("env-1", makeForm([{ name: "a.txt" }]), "actor-1")).rejects.toThrow(
        "unexpected",
      );
    });
  });

  describe("getWorkspaceFileTree 文件树", () => {
    test("返回工作区相对路径与 mtimes 副本", async () => {
      const service = fakeService({
        tree: mock(async () => ({ paths: ["user/a.txt"], mtimes: { "user/a.txt": 123 } })),
      });
      setApiWorkspaceDeps({ createAgentFileService: () => service });
      expect(await getWorkspaceFileTree("env-1", "actor-1")).toEqual({
        environmentId: "env-1",
        paths: ["user/a.txt"],
        mtimes: { "user/a.txt": 123 },
      });
    });

    test("遍历错误只暴露脱敏提示", async () => {
      const service = fakeService({
        tree: mock(async () => ({
          paths: [],
          errors: [{ path: "user/secret", message: "EACCES: permission denied, scandir '/srv/ws/user/secret'" }],
        })),
      });
      setApiWorkspaceDeps({ createAgentFileService: () => service });
      const result = await getWorkspaceFileTree("env-1", "actor-1");
      expect(result.errors).toEqual([{ path: "user/secret", message: "Directory could not be read" }]);
    });

    test("无错误时不带 errors 字段", async () => {
      const service = fakeService({ tree: mock(async () => ({ paths: [], errors: [] })) });
      setApiWorkspaceDeps({ createAgentFileService: () => service });
      expect(await getWorkspaceFileTree("env-1", "actor-1")).toEqual({ environmentId: "env-1", paths: [] });
    });
  });

  describe("downloadWorkspaceFile 二进制下载", () => {
    test("返回文件名与流", async () => {
      const service = fakeService();
      setApiWorkspaceDeps({ createAgentFileService: () => service });
      const result = await downloadWorkspaceFile("env-1", "user/a.txt", "actor-1");
      expect(result.name).toBe("a.txt");
      expect(result.stream).toBeInstanceOf(Readable);
      expect(service.read).toHaveBeenCalledWith("user/a.txt", "binary");
    });

    test("执行面返回文本结果时抛 500", async () => {
      const service = fakeService({
        read: mock(async () => ({ type: "text" as const, name: "a.txt", content: "text" })),
      });
      setApiWorkspaceDeps({ createAgentFileService: () => service });
      await expect(downloadWorkspaceFile("env-1", "user/a.txt", "actor-1")).rejects.toMatchObject({
        code: "INTERNAL_ERROR",
        statusCode: 500,
      });
    });
  });
});
