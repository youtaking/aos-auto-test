import { describe, expect, test } from "bun:test";
import {
  AppError,
  ValidationError,
  NotFoundError,
  ConflictError,
  ConfigWriteError,
} from "@fenix/errors";

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
  });

  test("是 Error 的实例", () => {
    expect(new AppError("x", "X")).toBeInstanceOf(Error);
  });
});

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
});

describe("NotFoundError", () => {
  test("statusCode 为 404，code 为 NOT_FOUND", () => {
    const err = new NotFoundError("resource not found");
    expect(err.statusCode).toBe(404);
    expect(err.code).toBe("NOT_FOUND");
    expect(err.name).toBe("NotFoundError");
  });

  test("是 AppError 的实例", () => {
    expect(new NotFoundError("x")).toBeInstanceOf(AppError);
  });
});

describe("ConflictError", () => {
  test("statusCode 为 409，code 为 ALREADY_EXISTS", () => {
    const err = new ConflictError("already exists");
    expect(err.statusCode).toBe(409);
    expect(err.code).toBe("ALREADY_EXISTS");
    expect(err.name).toBe("ConflictError");
  });

  test("是 AppError 的实例", () => {
    expect(new ConflictError("x")).toBeInstanceOf(AppError);
  });
});

describe("ConfigWriteError", () => {
  test("statusCode 为 500，code 为 CONFIG_WRITE_ERROR", () => {
    const err = new ConfigWriteError("write failed");
    expect(err.statusCode).toBe(500);
    expect(err.code).toBe("CONFIG_WRITE_ERROR");
    expect(err.name).toBe("ConfigWriteError");
  });

  test("是 AppError 的实例", () => {
    expect(new ConfigWriteError("x")).toBeInstanceOf(AppError);
  });
});
