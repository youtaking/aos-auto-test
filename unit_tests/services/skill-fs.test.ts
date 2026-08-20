// skill-fs.test.ts — Skill 文件系统纯函数测试
// 测试目标：assertValidSkillName、parseFrontmatter、buildSkillMd、normalizeUploadPath、groupUploadFiles、resolveImportPlan
// 业务意图：确保 Skill 名称校验、frontmatter 解析、上传文件分组等基础工具函数正确

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数 ──

function createSkillValidationError(message: string): Error & { code: string } {
  const error = new Error(message) as Error & { code: string };
  error.code = "VALIDATION_ERROR";
  return error;
}

function assertValidSkillName(name: string): string {
  const skillName = name.trim();
  if (!skillName || skillName === "." || skillName === ".." || skillName.includes("/") || skillName.includes("\\")) {
    throw createSkillValidationError(`Skill 名称不合法: ${skillName}`);
  }
  return skillName;
}

function getSkillOrganizationDir(skillRoot: string, organizationId: string): string {
  return `${skillRoot}/${organizationId}`;
}

function getSkillSourceDir(skillRoot: string, organizationId: string, name: string): string {
  return `${getSkillOrganizationDir(skillRoot, organizationId)}/${assertValidSkillName(name)}`;
}

function getSkillMdPath(skillRoot: string, organizationId: string, name: string): string {
  return `${getSkillSourceDir(skillRoot, organizationId, name)}/SKILL.md`;
}

function getSkillArchivePath(skillRoot: string, organizationId: string, name: string): string {
  return `${getSkillOrganizationDir(skillRoot, organizationId)}/${assertValidSkillName(name)}.zip`;
}

function normalizeUploadPath(relativePath: string): string {
  const normalized = relativePath.replaceAll("\\", "/").trim();
  if (!normalized || normalized === "." || normalized.startsWith("/")) {
    throw createSkillValidationError("上传文件路径无效");
  }
  const segments = normalized.split("/");
  if (segments.some((segment) => !segment || segment === "." || segment === "..")) {
    throw createSkillValidationError("上传文件路径无效");
  }
  return segments.join("/");
}

interface UploadSkillFile {
  skillName: string;
  relativePath: string;
  content: string;
}

function groupUploadFiles(files: UploadSkillFile[]): Map<string, UploadSkillFile[]> {
  const grouped = new Map<string, UploadSkillFile[]>();
  for (const file of files) {
    const skillName = assertValidSkillName(file.skillName);
    const normalizedPath = normalizeUploadPath(file.relativePath);
    const items = grouped.get(skillName) ?? [];
    if (items.some((item) => item.relativePath === normalizedPath)) {
      throw createSkillValidationError(`Skill "${skillName}" 包含重复文件: ${normalizedPath}`);
    }
    items.push({ ...file, skillName, relativePath: normalizedPath });
    grouped.set(skillName, items);
  }
  return grouped;
}

interface ImportSkillsConflict {
  name: string;
  enabled: boolean;
  path: string;
}

function resolveImportPlan(
  grouped: Map<string, UploadSkillFile[]>,
  conflicts: ImportSkillsConflict[],
  strategy?: "ignore" | "overwrite",
): { pendingEntries: [string, UploadSkillFile[]][]; skipped: string[] } {
  const conflictNames = new Set(conflicts.map((item) => item.name));
  const skipped = strategy === "ignore" ? [...conflictNames] : [];
  const pendingEntries = [...grouped.entries()].filter(([name]) => strategy !== "ignore" || !conflictNames.has(name));
  return { pendingEntries, skipped };
}

function yamlScalar(value: string): string {
  if (!value.includes("\n")) return value;
  const indented = value.split("\n").map((line) => `  ${line}`).join("\n");
  return `|\n${indented}`;
}

function buildSkillMd(name: string, description: string, content: string, metadata?: Record<string, string>): string {
  const meta: Record<string, string> = { name, description, ...(metadata ?? {}) };
  const frontmatter = Object.entries(meta).map(([k, v]) => `${k}: ${yamlScalar(v)}`).join("\n");
  return `---\n${frontmatter}\n---\n${content}`;
}

function stripNameAndDescription(metadata: Record<string, string>): Record<string, string> {
  return Object.fromEntries(Object.entries(metadata).filter(([k]) => k !== "name" && k !== "description"));
}

// ── tests ──

describe("skill-fs 文件系统工具", () => {
  beforeEach(() => {
    mock.restore();
  });

  describe("assertValidSkillName 名称校验", () => {
    test("正常名称通过", () => {
      expect(assertValidSkillName("my-skill")).toBe("my-skill");
    });

    test("前后空格被 trim", () => {
      expect(assertValidSkillName("  my-skill  ")).toBe("my-skill");
    });

    test("空名称抛错", () => {
      expect(() => assertValidSkillName("")).toThrow("Skill 名称不合法");
    });

    test("纯空格抛错", () => {
      expect(() => assertValidSkillName("   ")).toThrow("Skill 名称不合法");
    });

    test("单点抛错", () => {
      expect(() => assertValidSkillName(".")).toThrow("Skill 名称不合法");
    });

    test("双点抛错", () => {
      expect(() => assertValidSkillName("..")).toThrow("Skill 名称不合法");
    });

    test("含正斜杠抛错", () => {
      expect(() => assertValidSkillName("path/skill")).toThrow("Skill 名称不合法");
    });

    test("含反斜杠抛错", () => {
      expect(() => assertValidSkillName("path\\skill")).toThrow("Skill 名称不合法");
    });

    test("错误的 code 为 VALIDATION_ERROR", () => {
      try {
        assertValidSkillName("");
      } catch (e: any) {
        expect(e.code).toBe("VALIDATION_ERROR");
      }
    });
  });

  describe("路径构建", () => {
    test("getSkillOrganizationDir 拼接正确", () => {
      expect(getSkillOrganizationDir("/skills", "org-1")).toBe("/skills/org-1");
    });

    test("getSkillSourceDir 拼接正确", () => {
      expect(getSkillSourceDir("/skills", "org-1", "my-skill")).toBe("/skills/org-1/my-skill");
    });

    test("getSkillMdPath 拼接正确", () => {
      expect(getSkillMdPath("/skills", "org-1", "my-skill")).toBe("/skills/org-1/my-skill/SKILL.md");
    });

    test("getSkillArchivePath 拼接正确", () => {
      expect(getSkillArchivePath("/skills", "org-1", "my-skill")).toBe("/skills/org-1/my-skill.zip");
    });

    test("路径构建拒绝非法名称", () => {
      expect(() => getSkillSourceDir("/skills", "org-1", "../escape")).toThrow("Skill 名称不合法");
    });
  });

  describe("normalizeUploadPath 路径规范化", () => {
    test("正常相对路径通过", () => {
      expect(normalizeUploadPath("SKILL.md")).toBe("SKILL.md");
    });

    test("子目录路径通过", () => {
      expect(normalizeUploadPath("sub/dir/file.txt")).toBe("sub/dir/file.txt");
    });

    test("反斜杠转成正斜杠", () => {
      expect(normalizeUploadPath("sub\\dir\\file.txt")).toBe("sub/dir/file.txt");
    });

    test("前后空格被 trim", () => {
      expect(normalizeUploadPath("  SKILL.md  ")).toBe("SKILL.md");
    });

    test("空路径抛错", () => {
      expect(() => normalizeUploadPath("")).toThrow("上传文件路径无效");
    });

    test("单点抛错", () => {
      expect(() => normalizeUploadPath(".")).toThrow("上传文件路径无效");
    });

    test("绝对路径抛错", () => {
      expect(() => normalizeUploadPath("/etc/passwd")).toThrow("上传文件路径无效");
    });

    test("含 .. 抛错", () => {
      expect(() => normalizeUploadPath("../escape")).toThrow("上传文件路径无效");
    });

    test("中间段含 .. 抛错", () => {
      expect(() => normalizeUploadPath("sub/../escape")).toThrow("上传文件路径无效");
    });

    test("空段抛错", () => {
      expect(() => normalizeUploadPath("sub//file")).toThrow("上传文件路径无效");
    });
  });

  describe("groupUploadFiles 文件分组", () => {
    test("按 skillName 分组", () => {
      const files: UploadSkillFile[] = [
        { skillName: "skill-a", relativePath: "SKILL.md", content: "a" },
        { skillName: "skill-a", relativePath: "README.md", content: "b" },
        { skillName: "skill-b", relativePath: "SKILL.md", content: "c" },
      ];
      const grouped = groupUploadFiles(files);
      expect(grouped.size).toBe(2);
      expect(grouped.get("skill-a")!.length).toBe(2);
      expect(grouped.get("skill-b")!.length).toBe(1);
    });

    test("空文件列表返回空 Map", () => {
      const grouped = groupUploadFiles([]);
      expect(grouped.size).toBe(0);
    });

    test("重复文件抛错", () => {
      const files: UploadSkillFile[] = [
        { skillName: "skill-a", relativePath: "SKILL.md", content: "a" },
        { skillName: "skill-a", relativePath: "SKILL.md", content: "b" },
      ];
      expect(() => groupUploadFiles(files)).toThrow("包含重复文件");
    });

    test("非法 skill 名称抛错", () => {
      const files: UploadSkillFile[] = [
        { skillName: "../escape", relativePath: "SKILL.md", content: "a" },
      ];
      expect(() => groupUploadFiles(files)).toThrow("Skill 名称不合法");
    });

    test("反斜杠路径被规范化", () => {
      const files: UploadSkillFile[] = [
        { skillName: "skill-a", relativePath: "sub\\file.txt", content: "a" },
      ];
      const grouped = groupUploadFiles(files);
      expect(grouped.get("skill-a")![0].relativePath).toBe("sub/file.txt");
    });
  });

  describe("resolveImportPlan 导入计划", () => {
    const grouped = new Map<string, UploadSkillFile[]>([
      ["skill-a", [{ skillName: "skill-a", relativePath: "SKILL.md", content: "a" }]],
      ["skill-b", [{ skillName: "skill-b", relativePath: "SKILL.md", content: "b" }]],
      ["skill-c", [{ skillName: "skill-c", relativePath: "SKILL.md", content: "c" }]],
    ]);

    test("无冲突时全部 pending", () => {
      const result = resolveImportPlan(grouped, []);
      expect(result.pendingEntries.length).toBe(3);
      expect(result.skipped.length).toBe(0);
    });

    test("strategy=ignore 时冲突的被 skip", () => {
      const conflicts = [{ name: "skill-b", enabled: true, path: "/path" }];
      const result = resolveImportPlan(grouped, conflicts, "ignore");
      expect(result.pendingEntries.length).toBe(2);
      expect(result.skipped).toEqual(["skill-b"]);
    });

    test("strategy=overwrite 时冲突的在 pending 中", () => {
      const conflicts = [{ name: "skill-b", enabled: true, path: "/path" }];
      const result = resolveImportPlan(grouped, conflicts, "overwrite");
      expect(result.pendingEntries.length).toBe(3);
      expect(result.skipped.length).toBe(0);
    });

    test("无 strategy 时冲突的在 pending 中", () => {
      const conflicts = [{ name: "skill-a", enabled: true, path: "/path" }];
      const result = resolveImportPlan(grouped, conflicts);
      expect(result.pendingEntries.length).toBe(3);
      expect(result.skipped.length).toBe(0);
    });
  });

  describe("buildSkillMd 文件构建", () => {
    test("基本构建包含 frontmatter", () => {
      const result = buildSkillMd("my-skill", "A test skill", "Content here");
      expect(result).toContain("---");
      expect(result).toContain("name: my-skill");
      expect(result).toContain("description: A test skill");
      expect(result).toContain("Content here");
    });

    test("带额外 metadata", () => {
      const result = buildSkillMd("my-skill", "desc", "content", { version: "1.0" });
      expect(result).toContain("version: 1.0");
    });

    test("多行 description 使用 YAML 块标量", () => {
      const result = buildSkillMd("my-skill", "line1\nline2", "content");
      expect(result).toContain("|");
      expect(result).toContain("  line1");
      expect(result).toContain("  line2");
    });

    test("单行 description 不使用块标量", () => {
      const result = buildSkillMd("my-skill", "single line", "content");
      expect(result).not.toContain("|");
      expect(result).toContain("description: single line");
    });
  });

  describe("stripNameAndDescription 字段过滤", () => {
    test("过滤掉 name 和 description", () => {
      const result = stripNameAndDescription({ name: "test", description: "desc", version: "1.0", author: "me" });
      expect(result).toEqual({ version: "1.0", author: "me" });
    });

    test("空对象返回空对象", () => {
      const result = stripNameAndDescription({});
      expect(result).toEqual({});
    });

    test("只有 name 和 description 时返回空对象", () => {
      const result = stripNameAndDescription({ name: "test", description: "desc" });
      expect(result).toEqual({});
    });
  });
});
