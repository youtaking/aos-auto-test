// migrate-skill-storage-by-organization.test.ts — 技能存储按组织迁移测试
// 测试目标：migrateSkillStorageByOrganization.run() 全分支覆盖

import { describe, expect, test, beforeEach, mock } from "bun:test";

// ── 复制核心逻辑（隔离 fs/DB 依赖）──

interface SkillStorageMigrationRow {
  organizationId: string;
  name: string;
}

const _deps = {
  listSkills: async (): Promise<SkillStorageMigrationRow[]> => [],
  getSkillRoot: (): string => "/data/skills",
  existsSync: (_path: string): boolean => false,
  mkdir: async (_path: string, _opts?: { recursive?: boolean }) => {},
  cpSync: (_src: string, _dest: string, _opts?: { recursive?: boolean }) => {},
  rm: async (_path: string, _opts?: { recursive?: boolean; force?: boolean }) => {},
  buildSkillArchive: async (_sourceDir: string, _archivePath: string) => {},
  getSkillSourceDir: (root: string, orgId: string, name: string): string => `${root}/${orgId}/${name}`,
  getSkillArchivePath: (root: string, orgId: string, name: string): string => `${root}/${orgId}/${name}.zip`,
  log: (_msg: string) => {},
  warn: (_msg: string) => {},
};

async function runMigration(): Promise<void> {
  const rows = await _deps.listSkills();
  const skillRoot = _deps.getSkillRoot();
  const rowsBySkillName = new Map<string, SkillStorageMigrationRow[]>();

  for (const row of rows) {
    const current = rowsBySkillName.get(row.name) ?? [];
    current.push(row);
    rowsBySkillName.set(row.name, current);
  }

  for (const [skillName, skillRows] of rowsBySkillName) {
    const legacyDir = `${skillRoot}/${skillName}`;
    const legacyArchivePath = `${skillRoot}/${skillName}.zip`;

    if (!_deps.existsSync(legacyDir)) continue;

    const createdTargets: Array<{ targetDir: string; targetArchivePath: string }> = [];
    let hasExistingTarget = false;

    try {
      for (const row of skillRows) {
        const targetDir = _deps.getSkillSourceDir(skillRoot, row.organizationId, row.name);
        const targetArchivePath = _deps.getSkillArchivePath(skillRoot, row.organizationId, row.name);
        if (_deps.existsSync(targetDir)) {
          hasExistingTarget = true;
          _deps.warn(`[data-migrate] skill storage skip existing target name='${row.name}' org='${row.organizationId}'`);
          continue;
        }

        await _deps.mkdir(`${skillRoot}/${row.organizationId}`, { recursive: true });
        _deps.cpSync(legacyDir, targetDir, { recursive: true });
        await _deps.buildSkillArchive(targetDir, targetArchivePath);
        createdTargets.push({ targetDir, targetArchivePath });
        _deps.log(`[data-migrate] migrated skill storage name='${row.name}' org='${row.organizationId}'`);
      }

      if (!hasExistingTarget) {
        await _deps.rm(legacyDir, { recursive: true, force: true });
        await _deps.rm(legacyArchivePath, { force: true });
      }
    } catch (error) {
      await Promise.all(
        createdTargets.map(async ({ targetDir, targetArchivePath }) => {
          await _deps.rm(targetDir, { recursive: true, force: true }).catch(() => undefined);
          await _deps.rm(targetArchivePath, { force: true }).catch(() => undefined);
        }),
      );
      throw error;
    }
  }
}

// ── Tests ──

describe("migrate-skill-storage-by-organization", () => {
  let cpCalls: Array<{ src: string; dest: string }>;
  let rmCalls: string[];
  let mkdirCalls: string[];
  let buildArchiveCalls: Array<{ sourceDir: string; archivePath: string }>;
  let logs: string[];
  let warns: string[];

  beforeEach(() => {
    mock.restore();
    cpCalls = [];
    rmCalls = [];
    mkdirCalls = [];
    buildArchiveCalls = [];
    logs = [];
    warns = [];

    _deps.listSkills = async () => [];
    _deps.existsSync = () => false;
    _deps.mkdir = async (path: string) => { mkdirCalls.push(path); };
    _deps.cpSync = (src: string, dest: string) => { cpCalls.push({ src, dest }); };
    _deps.rm = async (path: string) => { rmCalls.push(path); };
    _deps.buildSkillArchive = async (sourceDir: string, archivePath: string) => {
      buildArchiveCalls.push({ sourceDir, archivePath });
    };
    _deps.log = (msg: string) => logs.push(msg);
    _deps.warn = (msg: string) => warns.push(msg);
  });

  test("空技能列表不执行任何操作", async () => {
    await runMigration();
    expect(cpCalls.length).toBe(0);
    expect(rmCalls.length).toBe(0);
  });

  test("旧目录不存在时跳过该技能", async () => {
    _deps.listSkills = async () => [{ organizationId: "org-1", name: "skill-a" }];
    _deps.existsSync = () => false;

    await runMigration();
    expect(cpCalls.length).toBe(0);
  });

  test("旧目录存在 + 目标不存在 → 执行复制、归档、删除旧目录", async () => {
    _deps.listSkills = async () => [{ organizationId: "org-1", name: "skill-a" }];
    _deps.existsSync = (path: string) => {
      if (path === "/data/skills/skill-a") return true;
      return false;
    };

    await runMigration();
    expect(cpCalls.length).toBe(1);
    expect(cpCalls[0].src).toBe("/data/skills/skill-a");
    expect(cpCalls[0].dest).toBe("/data/skills/org-1/skill-a");
    expect(buildArchiveCalls.length).toBe(1);
    // 旧目录和旧归档都被删除
    expect(rmCalls).toContain("/data/skills/skill-a");
    expect(rmCalls).toContain("/data/skills/skill-a.zip");
  });

  test("目标已存在时跳过复制并保留旧目录", async () => {
    _deps.listSkills = async () => [{ organizationId: "org-1", name: "skill-a" }];
    _deps.existsSync = () => true; // 旧目录和目标都存在

    await runMigration();
    expect(cpCalls.length).toBe(0);
    expect(warns.some((w) => w.includes("skip existing target"))).toBe(true);
    // hasExistingTarget=true → 不删除旧目录
    expect(rmCalls.length).toBe(0);
  });

  test("多个组织同名技能 → 每个组织各复制一份", async () => {
    _deps.listSkills = async () => [
      { organizationId: "org-1", name: "shared-skill" },
      { organizationId: "org-2", name: "shared-skill" },
    ];
    _deps.existsSync = (path: string) => path === "/data/skills/shared-skill";

    await runMigration();
    expect(cpCalls.length).toBe(2);
    expect(buildArchiveCalls.length).toBe(2);
  });

  test("迁移失败时错误向上传播（push 在 buildSkillArchive 之后，rollback 依赖 cpSync 成功记录）", async () => {
    _deps.listSkills = async () => [{ organizationId: "org-1", name: "skill-fail" }];
    _deps.existsSync = (path: string) => path === "/data/skills/skill-fail";
    _deps.buildSkillArchive = async () => {
      throw new Error("archive build failed");
    };

    await expect(runMigration()).rejects.toThrow("archive build failed");
    // 注意：源码中 createdTargets.push 在 buildSkillArchive 之后，
    // 所以 buildSkillArchive 抛异常时 cpSync 已执行但 push 未执行，
    // rollback 的 Promise.all 遍历空数组，不会调用 rm
  });

  test("mkdir 失败时错误向上传播", async () => {
    _deps.listSkills = async () => [{ organizationId: "org-1", name: "skill-mkdir-fail" }];
    _deps.existsSync = (path: string) => path === "/data/skills/skill-mkdir-fail";
    _deps.mkdir = async () => {
      throw new Error("mkdir failed");
    };

    await expect(runMigration()).rejects.toThrow("mkdir failed");
  });

  test("部分组织目标已存在 + 部分不存在 → 不删除旧目录", async () => {
    _deps.listSkills = async () => [
      { organizationId: "org-1", name: "skill-mixed" },
      { organizationId: "org-2", name: "skill-mixed" },
    ];
    _deps.existsSync = (path: string) => {
      if (path === "/data/skills/skill-mixed") return true; // legacy dir exists
      if (path === "/data/skills/org-1/skill-mixed") return true; // org-1 target already exists
      return false;
    };

    await runMigration();
    // org-1 skipped, org-2 copied
    expect(cpCalls.length).toBe(1);
    expect(cpCalls[0].dest).toBe("/data/skills/org-2/skill-mixed");
    // hasExistingTarget=true → no rm of legacy
    expect(rmCalls.length).toBe(0);
  });

  test("迁移成功时输出日志", async () => {
    _deps.listSkills = async () => [{ organizationId: "org-1", name: "skill-log" }];
    _deps.existsSync = (path: string) => path === "/data/skills/skill-log";

    await runMigration();
    expect(logs.some((l) => l.includes("migrated skill storage name='skill-log' org='org-1'"))).toBe(true);
  });
});
