// agent-expert-sync.test.ts — 专家名称消毒函数测试
// 测试目标：sanitizeExpertName 的合法/非法名称判定
// 业务意图：防止 frontmatter.name 含路径分隔符或相对路径逃逸，保障文件渲染安全

import { describe, expect, test } from "bun:test";

// ── 复制源函数（纯函数，无外部依赖）──

function sanitizeExpertName(name: string): string | null {
  if (name.length === 0 || name.length > 64) return null;
  if (name.includes("/") || name.includes("\\") || name.includes("..")) return null;
  return /^[\p{L}0-9][\p{L}0-9 -]*[\p{L}0-9]$|^[\p{L}0-9]$/u.test(name) ? name : null;
}

// ── 合法名称 ──

describe("sanitizeExpertName 合法名称", () => {
  // 简单英文
  test("简单英文名称通过", () => {
    expect(sanitizeExpertName("Code Reviewer")).toBe("Code Reviewer");
  });

  // 单字符
  test("单个字母通过", () => {
    expect(sanitizeExpertName("A")).toBe("A");
  });

  // 单数字
  test("单个数字通过", () => {
    expect(sanitizeExpertName("5")).toBe("5");
  });

  // 含连字符
  test("含连字符的名称通过", () => {
    expect(sanitizeExpertName("code-reviewer")).toBe("code-reviewer");
  });

  // 含中文
  test("中文名称通过", () => {
    expect(sanitizeExpertName("代码审查")).toBe("代码审查");
  });

  // 中英混合
  test("中英混合名称通过", () => {
    expect(sanitizeExpertName("Code 审查专家")).toBe("Code 审查专家");
  });

  // 数字开头
  test("数字开头的名称通过", () => {
    expect(sanitizeExpertName("1st Reviewer")).toBe("1st Reviewer");
  });

  // 最大长度（64 字符）
  test("64 字符名称通过", () => {
    const name = "A".repeat(64);
    expect(sanitizeExpertName(name)).toBe(name);
  });
});

// ── 非法名称 ──

describe("sanitizeExpertName 非法名称", () => {
  // 空字符串
  test("空字符串返回 null", () => {
    expect(sanitizeExpertName("")).toBeNull();
  });

  // 超过 64 字符
  test("超过 64 字符返回 null", () => {
    expect(sanitizeExpertName("A".repeat(65))).toBeNull();
  });

  // 含正斜杠
  test("含正斜杠返回 null（路径穿越防护）", () => {
    expect(sanitizeExpertName("path/name")).toBeNull();
  });

  // 含反斜杠
  test("含反斜杠返回 null（路径穿越防护）", () => {
    expect(sanitizeExpertName("path\\name")).toBeNull();
  });

  // 含 ..
  test("含 .. 返回 null（相对路径逃逸防护）", () => {
    expect(sanitizeExpertName("../../../etc")).toBeNull();
  });

  // 以空格开头
  test("以空格开头返回 null", () => {
    expect(sanitizeExpertName(" leading")).toBeNull();
  });

  // 以空格结尾
  test("以空格结尾返回 null", () => {
    expect(sanitizeExpertName("trailing ")).toBeNull();
  });

  // 以连字符开头
  test("以连字符开头返回 null", () => {
    expect(sanitizeExpertName("-leading")).toBeNull();
  });

  // 以连字符结尾
  test("以连字符结尾返回 null", () => {
    expect(sanitizeExpertName("trailing-")).toBeNull();
  });

  // 含特殊字符（emoji）
  test("含 emoji 返回 null", () => {
    expect(sanitizeExpertName("Expert 🤖")).toBeNull();
  });

  // 含特殊符号
  test("含 @ 符号返回 null", () => {
    expect(sanitizeExpertName("user@domain")).toBeNull();
  });

  // 含下划线
  test("含下划线返回 null", () => {
    expect(sanitizeExpertName("code_reviewer")).toBeNull();
  });

  // 含冒号
  test("含冒号返回 null", () => {
    expect(sanitizeExpertName("name:version")).toBeNull();
  });

  // 纯空格
  test("纯空格返回 null", () => {
    expect(sanitizeExpertName("   ")).toBeNull();
  });

  // 纯连字符
  test("纯连字符返回 null", () => {
    expect(sanitizeExpertName("---")).toBeNull();
  });
});

// ── 边界情况 ──

describe("sanitizeExpertName 边界情况", () => {
  // 两字符名称（首尾各一个合法字符）
  test("两字符合法名称通过", () => {
    expect(sanitizeExpertName("AB")).toBe("AB");
  });

  // 中间含空格
  test("中间含空格通过", () => {
    expect(sanitizeExpertName("A B")).toBe("A B");
  });

  // 中间含连字符
  test("中间含连字符通过", () => {
    expect(sanitizeExpertName("A-B")).toBe("A-B");
  });

  // Unicode 字母（日文）
  test("日文名称通过", () => {
    expect(sanitizeExpertName("コードレビュー")).toBe("コードレビュー");
  });

  // Unicode 字母（韩文）
  test("韩文名称通过", () => {
    expect(sanitizeExpertName("코드리뷰")).toBe("코드리뷰");
  });
});
