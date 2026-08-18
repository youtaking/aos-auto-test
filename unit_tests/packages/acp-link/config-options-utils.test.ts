import { describe, test, expect } from "bun:test";

// ========== Pure function copies from packages/acp-link/src/config-options-utils.ts ==========

function flattenOptions(rawOptions: unknown): Array<Record<string, unknown>> {
  const arr: Array<Record<string, unknown>> = Array.isArray(rawOptions) ? rawOptions : [];
  const flatOptions: Array<Record<string, unknown>> = [];
  for (const opt of arr) {
    if ("group" in opt && Array.isArray(opt.options)) {
      flatOptions.push(...(opt.options as Array<Record<string, unknown>>));
    } else {
      flatOptions.push(opt);
    }
  }
  return flatOptions;
}

function sanitizeCurrentId(rawId: string, validIds: string[], kind: "model" | "mode"): string {
  if (!rawId) return rawId;
  if (validIds.length === 0) {
    return rawId;
  }
  if (validIds.includes(rawId)) return rawId;
  return validIds[0];
}

function extractModelState(
  configOptions: Array<Record<string, unknown>> | null | undefined,
): { currentModelId: string; availableModels: Array<{ modelId: string; name: string; description: string | null; modalities: unknown }> } | null {
  if (!configOptions) return null;
  const modelOption = configOptions.find(
    (o) => o.type === "select" && (o.id === "model" || o.category === "model"),
  );
  if (!modelOption) return null;
  const flatOptions = flattenOptions(modelOption.options);
  const availableModels = flatOptions.map((o) => ({
    modelId: String(o.value ?? ""),
    name: String(o.name ?? ""),
    description: (o.description as string) ?? null,
    modalities: (o.modalities as unknown) ?? null,
  }));
  const rawCurrent = String(modelOption.currentValue ?? modelOption.value ?? "");
  const currentModelId = sanitizeCurrentId(
    rawCurrent,
    availableModels.map((m) => m.modelId),
    "model",
  );
  return { currentModelId, availableModels };
}

function extractModeState(
  configOptions: Array<Record<string, unknown>> | null | undefined,
): { currentModeId: string; availableModes: Array<{ id: string; name: string; description: string | null }> } | null {
  if (!configOptions) return null;
  const modeOption = configOptions.find(
    (o) => o.type === "select" && (o.id === "mode" || o.category === "mode"),
  );
  if (!modeOption) return null;
  const flatOptions = flattenOptions(modeOption.options);
  const availableModes = flatOptions.map((o) => ({
    id: String(o.value ?? ""),
    name: String(o.name ?? ""),
    description: (o.description as string) ?? null,
  }));
  const rawCurrent = String(modeOption.currentValue ?? modeOption.value ?? "");
  const currentModeId = sanitizeCurrentId(
    rawCurrent,
    availableModes.map((m) => m.id),
    "mode",
  );
  return { currentModeId, availableModes };
}

// ========== Tests ==========

describe("flattenOptions", () => {
  test("returns flat array as-is", () => {
    const opts = [
      { value: "a", name: "A" },
      { value: "b", name: "B" },
    ];
    const result = flattenOptions(opts);
    expect(result).toEqual([
      { value: "a", name: "A" },
      { value: "b", name: "B" },
    ]);
  });

  test("flattens grouped options", () => {
    const opts = [
      {
        group: "Group1",
        options: [
          { value: "a", name: "A" },
          { value: "b", name: "B" },
        ],
      },
      {
        group: "Group2",
        options: [{ value: "c", name: "C" }],
      },
    ];
    const result = flattenOptions(opts);
    expect(result).toEqual([
      { value: "a", name: "A" },
      { value: "b", name: "B" },
      { value: "c", name: "C" },
    ]);
  });

  test("mixes flat and grouped options", () => {
    const opts = [
      { value: "x", name: "X" },
      {
        group: "G",
        options: [{ value: "y", name: "Y" }],
      },
    ];
    const result = flattenOptions(opts);
    expect(result).toEqual([
      { value: "x", name: "X" },
      { value: "y", name: "Y" },
    ]);
  });

  test("returns empty array for non-array input", () => {
    expect(flattenOptions(null)).toEqual([]);
    expect(flattenOptions(undefined)).toEqual([]);
    expect(flattenOptions("string")).toEqual([]);
    expect(flattenOptions(42)).toEqual([]);
  });

  test("returns empty array for empty array input", () => {
    expect(flattenOptions([])).toEqual([]);
  });
});

describe("sanitizeCurrentId", () => {
  test("returns empty string for empty rawId", () => {
    expect(sanitizeCurrentId("", ["a", "b"], "model")).toBe("");
  });

  test("returns same id if it exists in validIds", () => {
    expect(sanitizeCurrentId("b", ["a", "b", "c"], "model")).toBe("b");
  });

  test("falls back to first valid id if rawId is not in validIds", () => {
    expect(sanitizeCurrentId("invalid", ["a", "b", "c"], "model")).toBe("a");
  });

  test("returns rawId if validIds is empty", () => {
    expect(sanitizeCurrentId("raw", [], "model")).toBe("raw");
  });

  test("works with mode kind", () => {
    expect(sanitizeCurrentId("x", ["x", "y"], "mode")).toBe("x");
    expect(sanitizeCurrentId("z", ["x", "y"], "mode")).toBe("x");
  });
});

describe("extractModelState", () => {
  test("returns null for null input", () => {
    expect(extractModelState(null)).toBeNull();
  });

  test("returns null for undefined input", () => {
    expect(extractModelState(undefined)).toBeNull();
  });

  test("returns null when no model option exists", () => {
    const opts = [{ type: "text", id: "other" }];
    expect(extractModelState(opts)).toBeNull();
  });

  test("returns null when model option has wrong type", () => {
    const opts = [{ type: "text", id: "model" }];
    expect(extractModelState(opts)).toBeNull();
  });

  test("extracts from flat model options", () => {
    const opts = [
      {
        type: "select",
        id: "model",
        currentValue: "model-b",
        options: [
          { value: "model-a", name: "Model A", description: "First model", modalities: ["text"] },
          { value: "model-b", name: "Model B" },
        ],
      },
    ];
    const result = extractModelState(opts);
    expect(result).not.toBeNull();
    expect(result!.currentModelId).toBe("model-b");
    expect(result!.availableModels).toEqual([
      { modelId: "model-a", name: "Model A", description: "First model", modalities: ["text"] },
      { modelId: "model-b", name: "Model B", description: null, modalities: null },
    ]);
  });

  test("extracts from grouped model options", () => {
    const opts = [
      {
        type: "select",
        id: "model",
        currentValue: "gpt-4",
        options: [
          {
            group: "OpenAI",
            options: [
              { value: "gpt-4", name: "GPT-4" },
              { value: "gpt-3.5", name: "GPT-3.5" },
            ],
          },
          {
            group: "Anthropic",
            options: [{ value: "claude-3", name: "Claude 3" }],
          },
        ],
      },
    ];
    const result = extractModelState(opts);
    expect(result).not.toBeNull();
    expect(result!.currentModelId).toBe("gpt-4");
    expect(result!.availableModels.length).toBe(3);
    expect(result!.availableModels[0]).toEqual({ modelId: "gpt-4", name: "GPT-4", description: null, modalities: null });
  });

  test("falls back to first model when currentValue is invalid", () => {
    const opts = [
      {
        type: "select",
        id: "model",
        currentValue: "nonexistent",
        options: [
          { value: "model-a", name: "Model A" },
          { value: "model-b", name: "Model B" },
        ],
      },
    ];
    const result = extractModelState(opts);
    expect(result!.currentModelId).toBe("model-a");
  });

  test("uses value as fallback when currentValue is absent", () => {
    const opts = [
      {
        type: "select",
        id: "model",
        value: "model-x",
        options: [
          { value: "model-x", name: "Model X" },
          { value: "model-y", name: "Model Y" },
        ],
      },
    ];
    const result = extractModelState(opts);
    expect(result!.currentModelId).toBe("model-x");
  });

  test("matches model by category", () => {
    const opts = [
      {
        type: "select",
        category: "model",
        currentValue: "m1",
        options: [{ value: "m1", name: "M1" }],
      },
    ];
    const result = extractModelState(opts);
    expect(result).not.toBeNull();
    expect(result!.currentModelId).toBe("m1");
  });
});

describe("extractModeState", () => {
  test("returns null for null input", () => {
    expect(extractModeState(null)).toBeNull();
  });

  test("returns null for undefined input", () => {
    expect(extractModeState(undefined)).toBeNull();
  });

  test("returns null when no mode option exists", () => {
    const opts = [{ type: "text", id: "other" }];
    expect(extractModeState(opts)).toBeNull();
  });

  test("extracts mode options correctly", () => {
    const opts = [
      {
        type: "select",
        id: "mode",
        currentValue: "chat",
        options: [
          { value: "chat", name: "Chat", description: "Chat mode" },
          { value: "code", name: "Code" },
        ],
      },
    ];
    const result = extractModeState(opts);
    expect(result).not.toBeNull();
    expect(result!.currentModeId).toBe("chat");
    expect(result!.availableModes).toEqual([
      { id: "chat", name: "Chat", description: "Chat mode" },
      { id: "code", name: "Code", description: null },
    ]);
  });

  test("falls back to first mode when currentValue is invalid", () => {
    const opts = [
      {
        type: "select",
        id: "mode",
        currentValue: "invalid",
        options: [
          { value: "chat", name: "Chat" },
          { value: "code", name: "Code" },
        ],
      },
    ];
    const result = extractModeState(opts);
    expect(result!.currentModeId).toBe("chat");
  });

  test("matches mode by category", () => {
    const opts = [
      {
        type: "select",
        category: "mode",
        currentValue: "agent",
        options: [{ value: "agent", name: "Agent" }],
      },
    ];
    const result = extractModeState(opts);
    expect(result).not.toBeNull();
    expect(result!.currentModeId).toBe("agent");
  });
});
