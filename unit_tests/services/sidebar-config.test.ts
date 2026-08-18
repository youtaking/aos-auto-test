import { describe, test, expect } from "bun:test";

// ── Pure function copies from src/services/sidebar-config.ts ──

/**
 * Parses APP_HIDDEN_SIDEBAR_TABS into a stable tab id list.
 * Splits by comma, trims whitespace, deduplicates, filters empty entries.
 */
function parseHiddenSidebarTabs(rawValue: string | undefined): string[] {
  if (!rawValue?.trim()) return [];

  const uniqueTabs = new Set<string>();
  for (const rawTabId of rawValue.split(",")) {
    const tabId = rawTabId.trim();
    if (!tabId) continue;
    uniqueTabs.add(tabId);
  }

  return [...uniqueTabs];
}

// ── Tests ──

describe("parseHiddenSidebarTabs", () => {
  test("returns empty array for undefined", () => {
    expect(parseHiddenSidebarTabs(undefined)).toEqual([]);
  });

  test("returns empty array for empty string", () => {
    expect(parseHiddenSidebarTabs("")).toEqual([]);
  });

  test("returns empty array for whitespace-only string", () => {
    expect(parseHiddenSidebarTabs("   ")).toEqual([]);
  });

  test("parses single tab id", () => {
    expect(parseHiddenSidebarTabs("settings")).toEqual(["settings"]);
  });

  test("parses multiple tab ids", () => {
    expect(parseHiddenSidebarTabs("settings,agents,knowledge")).toEqual([
      "settings",
      "agents",
      "knowledge",
    ]);
  });

  test("trims whitespace around tab ids", () => {
    expect(parseHiddenSidebarTabs(" settings , agents , knowledge ")).toEqual([
      "settings",
      "agents",
      "knowledge",
    ]);
  });

  test("deduplicates tab ids (preserves first occurrence order)", () => {
    expect(parseHiddenSidebarTabs("settings,agents,settings")).toEqual([
      "settings",
      "agents",
    ]);
  });

  test("filters empty entries from extra commas", () => {
    expect(parseHiddenSidebarTabs("settings,,agents,,,knowledge")).toEqual([
      "settings",
      "agents",
      "knowledge",
    ]);
  });

  test("filters whitespace-only entries between commas", () => {
    expect(parseHiddenSidebarTabs("settings,  ,agents")).toEqual([
      "settings",
      "agents",
    ]);
  });

  test("handles trailing comma", () => {
    expect(parseHiddenSidebarTabs("settings,agents,")).toEqual([
      "settings",
      "agents",
    ]);
  });

  test("handles leading comma", () => {
    expect(parseHiddenSidebarTabs(",settings,agents")).toEqual([
      "settings",
      "agents",
    ]);
  });

  test("all duplicates returns single entry", () => {
    expect(parseHiddenSidebarTabs("x,x,x,x")).toEqual(["x"]);
  });

  test("preserves insertion order for unique entries", () => {
    expect(parseHiddenSidebarTabs("c,b,a")).toEqual(["c", "b", "a"]);
  });

  test("returns stable array (same output for same input)", () => {
    const input = "z,y,x";
    const result1 = parseHiddenSidebarTabs(input);
    const result2 = parseHiddenSidebarTabs(input);
    expect(result1).toEqual(result2);
  });
});
