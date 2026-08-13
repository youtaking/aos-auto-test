import { describe, expect, test } from "bun:test";
import { buildHealthInfo, buildInfo, resolveCommitId } from "@fenix/services/build-info";

describe("resolveCommitId", () => {
  test("无注入且无 git 时返回 unknown", () => {
    expect(resolveCommitId(undefined, () => undefined)).toBe("unknown");
  });

  test("构建注入值优先于 git 回调", () => {
    expect(resolveCommitId("built-commit", () => "working-tree-commit")).toBe("built-commit");
  });

  test("无注入时使用 git 回调值", () => {
    expect(resolveCommitId(undefined, () => "startup-commit")).toBe("startup-commit");
  });

  test("空白注入值被忽略，使用 git 回调", () => {
    expect(resolveCommitId("  ", () => "fallback")).toBe("fallback");
  });

  test("unknown 注入值被忽略，使用 git 回调", () => {
    expect(resolveCommitId("unknown", () => "fallback")).toBe("fallback");
  });
});

describe("buildHealthInfo", () => {
  test("包含 status ok 和 startedAt", () => {
    const startedAt = "2026-07-31T10:20:30.123Z";
    const result = buildHealthInfo(startedAt);
    expect(result.status).toBe("ok");
    expect(result.startedAt).toBe(startedAt);
    expect(result.commitId).toBe(buildInfo.commitId);
  });
});
