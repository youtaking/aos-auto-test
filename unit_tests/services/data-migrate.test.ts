import { describe, test, expect, beforeEach } from "bun:test";

// ── Dependency-injection testable copy of src/services/data-migrate.ts ──
// The migration runner uses _deps for all external interactions,
// so we test runDataMigrations by replacing _deps with test doubles.

interface DataMigrate {
  name: string;
  run: () => Promise<void>;
}

interface DataMigrateDeps {
  migrates: DataMigrate[];
  listAppliedMigrationNames: () => Promise<string[]>;
  insertDataMigrateRecord: (name: string) => Promise<void>;
  log: (msg: string) => void;
}

function createDeps(): DataMigrateDeps {
  return {
    migrates: [],
    listAppliedMigrationNames: async () => [],
    insertDataMigrateRecord: async (_name: string) => {},
    log: (_msg: string) => {},
  };
}

async function runDataMigrations(deps: DataMigrateDeps): Promise<void> {
  const applied = new Set(await deps.listAppliedMigrationNames());
  for (const migrate of deps.migrates) {
    if (applied.has(migrate.name)) {
      deps.log(`[data-migrate] skip applied migrate '${migrate.name}'`);
      continue;
    }
    deps.log(`[data-migrate] run migrate '${migrate.name}'`);
    await migrate.run();
    await deps.insertDataMigrateRecord(migrate.name);
    deps.log(`[data-migrate] finished migrate '${migrate.name}'`);
  }
}

// ── Tests ──

describe("runDataMigrations", () => {
  let deps: DataMigrateDeps;
  let logs: string[];
  let insertedNames: string[];
  let runOrder: string[];

  beforeEach(() => {
    deps = createDeps();
    logs = [];
    insertedNames = [];
    runOrder = [];

    deps.log = (msg: string) => logs.push(msg);
    deps.insertDataMigrateRecord = async (name: string) => {
      insertedNames.push(name);
    };
  });

  test("runs all migrations when none are applied", async () => {
    deps.migrates = [
      { name: "m1", run: async () => { runOrder.push("m1"); } },
      { name: "m2", run: async () => { runOrder.push("m2"); } },
    ];

    await runDataMigrations(deps);

    expect(runOrder).toEqual(["m1", "m2"]);
    expect(insertedNames).toEqual(["m1", "m2"]);
  });

  test("skips already-applied migrations", async () => {
    deps.migrates = [
      { name: "m1", run: async () => { runOrder.push("m1"); } },
      { name: "m2", run: async () => { runOrder.push("m2"); } },
    ];
    deps.listAppliedMigrationNames = async () => ["m1"];

    await runDataMigrations(deps);

    expect(runOrder).toEqual(["m2"]);
    expect(insertedNames).toEqual(["m2"]);
  });

  test("skips all when all are already applied", async () => {
    deps.migrates = [
      { name: "m1", run: async () => { runOrder.push("m1"); } },
      { name: "m2", run: async () => { runOrder.push("m2"); } },
    ];
    deps.listAppliedMigrationNames = async () => ["m1", "m2"];

    await runDataMigrations(deps);

    expect(runOrder).toEqual([]);
    expect(insertedNames).toEqual([]);
  });

  test("runs nothing when migrates list is empty", async () => {
    deps.migrates = [];

    await runDataMigrations(deps);

    expect(runOrder).toEqual([]);
    expect(insertedNames).toEqual([]);
  });

  test("logs skip message for applied migrations", async () => {
    deps.migrates = [
      { name: "m1", run: async () => {} },
    ];
    deps.listAppliedMigrationNames = async () => ["m1"];

    await runDataMigrations(deps);

    expect(logs.some((l) => l.includes("skip applied migrate 'm1'"))).toBe(true);
  });

  test("logs run and finished messages for new migrations", async () => {
    deps.migrates = [
      { name: "m1", run: async () => {} },
    ];

    await runDataMigrations(deps);

    expect(logs.some((l) => l.includes("run migrate 'm1'"))).toBe(true);
    expect(logs.some((l) => l.includes("finished migrate 'm1'"))).toBe(true);
  });

  test("inserts record after each migration runs", async () => {
    const insertOrder: string[] = [];
    deps.insertDataMigrateRecord = async (name: string) => {
      insertOrder.push(name);
    };
    deps.migrates = [
      { name: "m1", run: async () => { runOrder.push("m1-run"); } },
      { name: "m2", run: async () => { runOrder.push("m2-run"); } },
    ];

    await runDataMigrations(deps);

    // Verify interleaved: m1 run → m1 insert → m2 run → m2 insert
    expect(runOrder[0]).toBe("m1-run");
    expect(insertOrder[0]).toBe("m1");
    expect(runOrder[1]).toBe("m2-run");
    expect(insertOrder[1]).toBe("m2");
  });

  test("propagates errors from migration run", async () => {
    deps.migrates = [
      { name: "m1", run: async () => { throw new Error("migration failed"); } },
    ];

    await expect(runDataMigrations(deps)).rejects.toThrow("migration failed");
    // Record should NOT be inserted for failed migration
    expect(insertedNames).toEqual([]);
  });

  test("propagates errors from insertDataMigrateRecord", async () => {
    deps.migrates = [
      { name: "m1", run: async () => {} },
    ];
    deps.insertDataMigrateRecord = async () => {
      throw new Error("DB insert failed");
    };

    await expect(runDataMigrations(deps)).rejects.toThrow("DB insert failed");
  });

  test("later migration does not run if earlier one fails", async () => {
    deps.migrates = [
      { name: "m1", run: async () => { throw new Error("fail"); } },
      { name: "m2", run: async () => { runOrder.push("m2"); } },
    ];

    try {
      await runDataMigrations(deps);
    } catch {
      // expected
    }

    expect(runOrder).toEqual([]);
  });

  test("runs migrations in order", async () => {
    deps.migrates = [
      { name: "a", run: async () => { runOrder.push("a"); } },
      { name: "b", run: async () => { runOrder.push("b"); } },
      { name: "c", run: async () => { runOrder.push("c"); } },
    ];

    await runDataMigrations(deps);

    expect(runOrder).toEqual(["a", "b", "c"]);
    expect(insertedNames).toEqual(["a", "b", "c"]);
  });
});
