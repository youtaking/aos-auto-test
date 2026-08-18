// error-classes.test.ts — 错误类单元测试
//
// 【双源冲突说明】FenixAgent 仓库中同时存在 src/errors.ts 和 src/errors/index.ts：
//   - src/errors.ts：AppError(message, code, statusCode=500)，属性 code + statusCode
//     → 被绝大多数 source 文件通过 "../../errors" / "../errors" 导入（Bun 模块解析
//       优先文件而非目录 index.ts），error-handler.ts 也访问 error.code + error.statusCode
//   - src/errors/index.ts：AppError(message, statusCode, type)，属性 type + statusCode
//     → 导出 toErrorResponse()，但因被 errors.ts 遮蔽，实际未被业务代码使用
//
// 本测试对齐 src/errors.ts（实际生效模块），使用 pure function copy 模式。

import { describe, expect, test } from "bun:test";

// ── 纯函数副本（对齐 src/errors.ts） ──

class AppError extends Error {
  readonly code: string;
  readonly statusCode: number;
  constructor(message: string, code: string, statusCode: number = 500) {
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

class NotFoundError extends AppError {
  constructor(message: string) {
    super(message, "NOT_FOUND", 404);
    this.name = "NotFoundError";
  }
}

class ForbiddenError extends AppError {
  constructor(message: string) {
    super(message, "FORBIDDEN", 403);
    this.name = "ForbiddenError";
  }
}

class ConflictError extends AppError {
  constructor(message: string) {
    super(message, "ALREADY_EXISTS", 409);
    this.name = "ConflictError";
  }
}

class ConfigWriteError extends AppError {
  constructor(message: string) {
    super(message, "CONFIG_WRITE_ERROR", 500);
    this.name = "ConfigWriteError";
  }
}

// ── AppError ──

describe("AppError", () => {
  test("默认 statusCode 为 500", () => {
    const err = new AppError("something broke", "INTERNAL_ERROR");
    expect(err.statusCode).toBe(500);
    expect(err.code).toBe("INTERNAL_ERROR");
    expect(err.message).toBe("something broke");
    expect(err.name).toBe("AppError");
  });

  test("可自定义 statusCode", () => {
    const err = new AppError("forbidden", "FORBIDDEN", 403);
    expect(err.statusCode).toBe(403);
    expect(err.code).toBe("FORBIDDEN");
    expect(err.message).toBe("forbidden");
  });

  test("是 Error 的实例", () => {
    expect(new AppError("x", "X")).toBeInstanceOf(Error);
  });

  test("是 AppError 的实例", () => {
    expect(new AppError("x", "X")).toBeInstanceOf(AppError);
  });

  test("name 属性为 AppError", () => {
    const err = new AppError("test", "TEST_CODE");
    expect(err.name).toBe("AppError");
  });

  test("继承 Error 的 stack 属性", () => {
    const err = new AppError("stack test", "STACK_TEST");
    expect(err.stack).toBeDefined();
    expect(typeof err.stack).toBe("string");
  });
});

// ── ValidationError ──

describe("ValidationError", () => {
  test("statusCode 为 400，code 为 VALIDATION_ERROR", () => {
    const err = new ValidationError("field required");
    expect(err.statusCode).toBe(400);
    expect(err.code).toBe("VALIDATION_ERROR");
    expect(err.name).toBe("ValidationError");
    expect(err.message).toBe("field required");
  });

  test("是 AppError 的实例", () => {
    expect(new ValidationError("x")).toBeInstanceOf(AppError);
  });

  test("是 Error 的实例", () => {
    expect(new ValidationError("x")).toBeInstanceOf(Error);
  });

  test("name 覆盖父类为 ValidationError", () => {
    const err = new ValidationError("x");
    expect(err.name).toBe("ValidationError");
    expect(err.name).not.toBe("AppError");
  });
});

// ── NotFoundError ──

describe("NotFoundError", () => {
  test("statusCode 为 404，code 为 NOT_FOUND", () => {
    const err = new NotFoundError("resource not found");
    expect(err.statusCode).toBe(404);
    expect(err.code).toBe("NOT_FOUND");
    expect(err.name).toBe("NotFoundError");
    expect(err.message).toBe("resource not found");
  });

  test("是 AppError 的实例", () => {
    expect(new NotFoundError("x")).toBeInstanceOf(AppError);
  });

  test("是 Error 的实例", () => {
    expect(new NotFoundError("x")).toBeInstanceOf(Error);
  });

  test("name 覆盖父类为 NotFoundError", () => {
    const err = new NotFoundError("x");
    expect(err.name).toBe("NotFoundError");
    expect(err.name).not.toBe("AppError");
  });
});

// ── ForbiddenError ──

describe("ForbiddenError", () => {
  test("statusCode 为 403，code 为 FORBIDDEN", () => {
    const err = new ForbiddenError("access denied");
    expect(err.statusCode).toBe(403);
    expect(err.code).toBe("FORBIDDEN");
    expect(err.name).toBe("ForbiddenError");
    expect(err.message).toBe("access denied");
  });

  test("是 AppError 的实例", () => {
    expect(new ForbiddenError("x")).toBeInstanceOf(AppError);
  });

  test("是 Error 的实例", () => {
    expect(new ForbiddenError("x")).toBeInstanceOf(Error);
  });
});

// ── ConflictError ──

describe("ConflictError", () => {
  test("statusCode 为 409，code 为 ALREADY_EXISTS", () => {
    const err = new ConflictError("already exists");
    expect(err.statusCode).toBe(409);
    expect(err.code).toBe("ALREADY_EXISTS");
    expect(err.name).toBe("ConflictError");
    expect(err.message).toBe("already exists");
  });

  test("是 AppError 的实例", () => {
    expect(new ConflictError("x")).toBeInstanceOf(AppError);
  });

  test("是 Error 的实例", () => {
    expect(new ConflictError("x")).toBeInstanceOf(Error);
  });
});

// ── ConfigWriteError ──

describe("ConfigWriteError", () => {
  test("statusCode 为 500，code 为 CONFIG_WRITE_ERROR", () => {
    const err = new ConfigWriteError("write failed");
    expect(err.statusCode).toBe(500);
    expect(err.code).toBe("CONFIG_WRITE_ERROR");
    expect(err.name).toBe("ConfigWriteError");
    expect(err.message).toBe("write failed");
  });

  test("是 AppError 的实例", () => {
    expect(new ConfigWriteError("x")).toBeInstanceOf(AppError);
  });

  test("是 Error 的实例", () => {
    expect(new ConfigWriteError("x")).toBeInstanceOf(Error);
  });
});
