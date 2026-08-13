import { describe, expect, test } from "bun:test";
import {
  normalizeChineseMainlandPhoneNumber,
  buildPhoneTempEmail,
  isEmailIdentifier,
} from "@fenix/services/phone-number";

describe("phone-number", () => {
  test("归一化带 +86 前缀的手机号", () => {
    expect(normalizeChineseMainlandPhoneNumber("+86 188-2648-0215")).toBe("18826480215");
  });

  test("归一化带 86 前缀的 13 位手机号", () => {
    expect(normalizeChineseMainlandPhoneNumber("8618826480215")).toBe("18826480215");
  });

  test("归一化纯 11 位手机号", () => {
    expect(normalizeChineseMainlandPhoneNumber("18826480215")).toBe("18826480215");
  });

  test("归一化带空格和括号的手机号", () => {
    expect(normalizeChineseMainlandPhoneNumber("(188) 2648 0215")).toBe("18826480215");
  });

  test("拒绝 12 位非法手机号", () => {
    expect(() => normalizeChineseMainlandPhoneNumber("188264802150")).toThrow("手机号格式不正确");
  });

  test("拒绝非 1 开头的手机号", () => {
    expect(() => normalizeChineseMainlandPhoneNumber("28826480215")).toThrow("手机号格式不正确");
  });

  test("拒绝空字符串", () => {
    expect(() => normalizeChineseMainlandPhoneNumber("")).toThrow("手机号格式不正确");
  });

  test("生成临时邮箱", () => {
    expect(buildPhoneTempEmail("18826480215")).toBe("18826480215@fenix.com");
  });

  test("判断邮箱标识符 - 包含 @", () => {
    expect(isEmailIdentifier("user@example.com")).toBe(true);
  });

  test("判断邮箱标识符 - 手机号", () => {
    expect(isEmailIdentifier("18826480215")).toBe(false);
  });
});
