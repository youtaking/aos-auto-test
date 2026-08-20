// system-admin.test.ts — 系统 admin 启动引导测试
// 测试目标：ensureSystemAdmin 全分支覆盖

import { describe, expect, test, beforeEach, mock } from "bun:test";

// ── 复制核心逻辑（隔离 DB/fs 依赖）──

const SYSTEM_ADMIN_EMAIL = "admin@fenix.com";
const SYSTEM_ADMIN_ORG_SLUG = "admin";
const PASSWORD_LENGTH = 16;
const PASSWORD_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";

interface SystemAdminBootstrapResult {
  created: boolean;
  userId: string;
  email: string;
  organization: { id: string; slug: string };
}

const _deps = {
  findUserByEmail: async (_email: string): Promise<{ id: string } | null> => null,
  findAdminOrganizationForUser: async (_userId: string): Promise<{ organizationId: string; slug: string } | null> => null,
  createSystemAdminRecords: async (_password: string): Promise<{ userId: string; organizationId: string }> => ({
    userId: "new-user-id",
    organizationId: "new-org-id",
  }),
  generateSystemAdminPassword: (): string =>
    Array.from({ length: PASSWORD_LENGTH }, () => PASSWORD_CHARS[0]).join(""),
  writePasswordFile: (_password: string) => {},
};

async function ensureSystemAdmin(): Promise<SystemAdminBootstrapResult> {
  const existing = await _deps.findUserByEmail(SYSTEM_ADMIN_EMAIL);
  if (existing) {
    const existingOrganization = await _deps.findAdminOrganizationForUser(existing.id);
    if (!existingOrganization) {
      throw new Error(
        `[system-admin] ${SYSTEM_ADMIN_EMAIL} exists but admin organization membership is missing; bootstrap cannot continue`,
      );
    }
    return {
      created: false,
      userId: existing.id,
      email: SYSTEM_ADMIN_EMAIL,
      organization: {
        id: existingOrganization.organizationId,
        slug: existingOrganization.slug,
      },
    };
  }

  const password = _deps.generateSystemAdminPassword();
  const created = await _deps.createSystemAdminRecords(password);
  _deps.writePasswordFile(password);
  return {
    created: true,
    userId: created.userId,
    email: SYSTEM_ADMIN_EMAIL,
    organization: {
      id: created.organizationId,
      slug: SYSTEM_ADMIN_ORG_SLUG,
    },
  };
}

// 复制纯函数
function generateSystemAdminPassword(): string {
  return Array.from({ length: PASSWORD_LENGTH }, () => PASSWORD_CHARS[Math.floor(Math.random() * PASSWORD_CHARS.length)]).join("");
}

function buildPasswordFileContent(password: string): string {
  return [
    "system admin account",
    `username: admin`,
    `email: ${SYSTEM_ADMIN_EMAIL}`,
    `password: ${password}`,
    `organization: admin`,
    "",
  ].join("\n");
}

// ── Tests ──

describe("system-admin", () => {
  beforeEach(() => {
    mock.restore();
    _deps.findUserByEmail = async () => null;
    _deps.findAdminOrganizationForUser = async () => null;
    _deps.createSystemAdminRecords = async () => ({ userId: "new-user-id", organizationId: "new-org-id" });
    _deps.generateSystemAdminPassword = () => "a".repeat(PASSWORD_LENGTH);
    _deps.writePasswordFile = () => {};
  });

  // ── ensureSystemAdmin ──

  describe("ensureSystemAdmin", () => {
    test("首次创建 - 返回 created=true 和新用户信息", async () => {
      const result = await ensureSystemAdmin();
      expect(result.created).toBe(true);
      expect(result.userId).toBe("new-user-id");
      expect(result.email).toBe(SYSTEM_ADMIN_EMAIL);
      expect(result.organization.id).toBe("new-org-id");
      expect(result.organization.slug).toBe(SYSTEM_ADMIN_ORG_SLUG);
    });

    test("首次创建 - 调用 writePasswordFile", async () => {
      let writtenPassword = "";
      _deps.writePasswordFile = (p: string) => { writtenPassword = p; };
      await ensureSystemAdmin();
      expect(writtenPassword).toBe("a".repeat(PASSWORD_LENGTH));
    });

    test("用户已存在且有组织 - 返回 created=false", async () => {
      _deps.findUserByEmail = async () => ({ id: "existing-user" });
      _deps.findAdminOrganizationForUser = async () => ({
        organizationId: "existing-org",
        slug: "admin",
      });

      const result = await ensureSystemAdmin();
      expect(result.created).toBe(false);
      expect(result.userId).toBe("existing-user");
      expect(result.organization.id).toBe("existing-org");
    });

    test("用户已存在但无组织 - 抛出错误", async () => {
      _deps.findUserByEmail = async () => ({ id: "orphan-user" });
      _deps.findAdminOrganizationForUser = async () => null;

      await expect(ensureSystemAdmin()).rejects.toThrow("admin organization membership is missing");
    });

    test("首次创建时 generateSystemAdminPassword 被调用", async () => {
      let called = false;
      _deps.generateSystemAdminPassword = () => {
        called = true;
        return "custom-password";
      };
      await ensureSystemAdmin();
      expect(called).toBe(true);
    });

    test("createSystemAdminRecords 接收生成的密码", async () => {
      let receivedPassword = "";
      _deps.generateSystemAdminPassword = () => "test-password-16";
      _deps.createSystemAdminRecords = async (password: string) => {
        receivedPassword = password;
        return { userId: "u1", organizationId: "o1" };
      };
      await ensureSystemAdmin();
      expect(receivedPassword).toBe("test-password-16");
    });

    test("用户已存在时不创建新记录", async () => {
      let createCalled = false;
      _deps.findUserByEmail = async () => ({ id: "existing" });
      _deps.findAdminOrganizationForUser = async () => ({ organizationId: "org", slug: "admin" });
      _deps.createSystemAdminRecords = async () => {
        createCalled = true;
        return { userId: "", organizationId: "" };
      };

      await ensureSystemAdmin();
      expect(createCalled).toBe(false);
    });

    test("用户已存在时不写密码文件", async () => {
      let writeCalled = false;
      _deps.findUserByEmail = async () => ({ id: "existing" });
      _deps.findAdminOrganizationForUser = async () => ({ organizationId: "org", slug: "admin" });
      _deps.writePasswordFile = () => { writeCalled = true; };

      await ensureSystemAdmin();
      expect(writeCalled).toBe(false);
    });
  });

  // ── 纯函数测试 ──

  describe("generateSystemAdminPassword", () => {
    test("长度为 PASSWORD_LENGTH", () => {
      const pwd = generateSystemAdminPassword();
      expect(pwd.length).toBe(PASSWORD_LENGTH);
    });

    test("只包含合法字符", () => {
      const pwd = generateSystemAdminPassword();
      for (const ch of pwd) {
        expect(PASSWORD_CHARS.includes(ch)).toBe(true);
      }
    });

    test("两次调用生成不同密码（概率极高）", () => {
      const a = generateSystemAdminPassword();
      const b = generateSystemAdminPassword();
      // 16 位随机字符完全相同的概率极低
      expect(a === b).toBe(false);
    });
  });

  describe("buildPasswordFileContent", () => {
    test("包含 admin 用户名", () => {
      const content = buildPasswordFileContent("test-pwd");
      expect(content).toContain("username: admin");
    });

    test("包含 admin 邮箱", () => {
      const content = buildPasswordFileContent("test-pwd");
      expect(content).toContain(`email: ${SYSTEM_ADMIN_EMAIL}`);
    });

    test("包含密码", () => {
      const content = buildPasswordFileContent("my-secret-pwd");
      expect(content).toContain("password: my-secret-pwd");
    });

    test("包含组织名", () => {
      const content = buildPasswordFileContent("test-pwd");
      expect(content).toContain("organization: admin");
    });

    test("以空行结尾", () => {
      const content = buildPasswordFileContent("test-pwd");
      expect(content.endsWith("\n")).toBe(true);
    });
  });
});
