import { describe, expect, test, beforeEach, mock } from "bun:test";

// ── Mock tokenRepo ──

const mockRepo = {
  create: mock(async (_username: string, _token: string) => {}),
  getByToken: mock(async (_token: string): Promise<{ username: string } | null> => null),
};

mock.module("@fenix/repositories", () => ({
  tokenRepo: mockRepo,
}));

import { issueToken, resolveToken } from "@fenix/auth/token";

describe("token 认证", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("issueToken", () => {
    test("正常签发返回 rct_ 前缀 token 和 86400 秒过期时间", async () => {
      const result = await issueToken("alice");
      expect(result.token.startsWith("rct_")).toBe(true);
      expect(result.expires_in).toBe(86400);
    });

    test("token 写入 tokenRepo.create", async () => {
      await issueToken("bob");
      expect(mockRepo.create.mock.calls.length).toBeGreaterThan(0);
      const lastCallArgs = mockRepo.create.mock.calls[mockRepo.create.mock.calls.length - 1];
      expect(lastCallArgs[0]).toBe("bob");
    });

    test("连续两次签发产生不同 token", async () => {
      const r1 = await issueToken("alice");
      const r2 = await issueToken("alice");
      expect(r1.token).not.toBe(r2.token);
    });
  });

  describe("resolveToken", () => {
    test("undefined token 返回 null", async () => {
      expect(await resolveToken(undefined)).toBeNull();
    });

    test("空字符串 token 返回 null", async () => {
      expect(await resolveToken("")).toBeNull();
    });

    test("repo 未找到记录时返回 null", async () => {
      mockRepo.getByToken.mockImplementation(async () => null);
      expect(await resolveToken("rct_invalid")).toBeNull();
    });

    test("有效 token 返回对应用户名", async () => {
      mockRepo.getByToken.mockImplementation(async () => ({ username: "carol" }));
      const result = await resolveToken("rct_valid_token");
      expect(result).toBe("carol");
    });

    test("解析时查询了正确的 token 值", async () => {
      mockRepo.getByToken.mockImplementation(async () => ({ username: "dave" }));
      await resolveToken("rct_abc123");
      expect(mockRepo.getByToken).toHaveBeenCalledWith("rct_abc123");
    });
  });
});
