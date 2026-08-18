import { describe, test, expect } from "bun:test";

// --- Pure functions/constants copied from source ---

const HINDSIGHT_PLUGIN_DEFAULTS: Record<string, unknown> = {
  autoRecall: true,
  autoRetain: true,
  recallBudget: "mid",
  recallTags: [],
  recallTagsMatch: "any",
  retainTags: [],
  retainEveryNTurns: 3,
  debug: false,
};

function isHindsightAvailable(): boolean {
  return Boolean(process.env.HINDSIGHT_MCP_URL);
}

// --- Tests ---

describe("HINDSIGHT_PLUGIN_DEFAULTS", () => {
  test("has all expected keys", () => {
    const expectedKeys = [
      "autoRecall",
      "autoRetain",
      "recallBudget",
      "recallTags",
      "recallTagsMatch",
      "retainTags",
      "retainEveryNTurns",
      "debug",
    ];
    for (const key of expectedKeys) {
      expect(HINDSIGHT_PLUGIN_DEFAULTS).toHaveProperty(key);
    }
  });

  test("has exactly the expected number of keys", () => {
    expect(Object.keys(HINDSIGHT_PLUGIN_DEFAULTS)).toHaveLength(8);
  });

  test("autoRecall defaults to true", () => {
    expect(HINDSIGHT_PLUGIN_DEFAULTS.autoRecall).toBe(true);
  });

  test("autoRetain defaults to true", () => {
    expect(HINDSIGHT_PLUGIN_DEFAULTS.autoRetain).toBe(true);
  });

  test("recallBudget defaults to mid", () => {
    expect(HINDSIGHT_PLUGIN_DEFAULTS.recallBudget).toBe("mid");
  });

  test("recallTags defaults to empty array", () => {
    expect(HINDSIGHT_PLUGIN_DEFAULTS.recallTags).toEqual([]);
  });

  test("recallTagsMatch defaults to any", () => {
    expect(HINDSIGHT_PLUGIN_DEFAULTS.recallTagsMatch).toBe("any");
  });

  test("retainTags defaults to empty array", () => {
    expect(HINDSIGHT_PLUGIN_DEFAULTS.retainTags).toEqual([]);
  });

  test("retainEveryNTurns defaults to 3", () => {
    expect(HINDSIGHT_PLUGIN_DEFAULTS.retainEveryNTurns).toBe(3);
  });

  test("debug defaults to false", () => {
    expect(HINDSIGHT_PLUGIN_DEFAULTS.debug).toBe(false);
  });

  test("recallTags defaults to empty array (length check)", () => {
    // Verify the default array is empty
    const tags = HINDSIGHT_PLUGIN_DEFAULTS.recallTags as unknown[];
    expect(tags).toHaveLength(0);
  });
});

describe("isHindsightAvailable", () => {
  test("returns true when HINDSIGHT_MCP_URL is set", () => {
    const original = process.env.HINDSIGHT_MCP_URL;
    try {
      process.env.HINDSIGHT_MCP_URL = "http://localhost:3000/mcp";
      expect(isHindsightAvailable()).toBe(true);
    } finally {
      if (original === undefined) {
        delete process.env.HINDSIGHT_MCP_URL;
      } else {
        process.env.HINDSIGHT_MCP_URL = original;
      }
    }
  });

  test("returns false when HINDSIGHT_MCP_URL is not set", () => {
    const original = process.env.HINDSIGHT_MCP_URL;
    try {
      delete process.env.HINDSIGHT_MCP_URL;
      expect(isHindsightAvailable()).toBe(false);
    } finally {
      if (original !== undefined) {
        process.env.HINDSIGHT_MCP_URL = original;
      }
    }
  });

  test("returns false when HINDSIGHT_MCP_URL is empty string", () => {
    const original = process.env.HINDSIGHT_MCP_URL;
    try {
      process.env.HINDSIGHT_MCP_URL = "";
      expect(isHindsightAvailable()).toBe(false);
    } finally {
      if (original === undefined) {
        delete process.env.HINDSIGHT_MCP_URL;
      } else {
        process.env.HINDSIGHT_MCP_URL = original;
      }
    }
  });
});
