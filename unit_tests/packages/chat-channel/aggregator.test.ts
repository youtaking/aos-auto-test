import { describe, test, expect } from "bun:test";

// ========== Pure function copies from packages/chat-channel/src/state/aggregator.ts ==========

// -- Types (minimal stubs) --
interface NormalizedEvent {
  type: string;
  turnId?: string;
  content?: Record<string, unknown>;
  update: Record<string, unknown>;
}

type TurnStatus =
  | "accepting"
  | "running"
  | "awaiting_permission"
  | "waiting_user"
  | "cancelling"
  | "completed"
  | "failed"
  | "cancelled"
  | "interrupted";

interface PublicError {
  code: string;
  message: string;
}

interface QuestionItemProjection {
  question: string;
  header: string | null;
  options: Array<{ label: string; description: string | null }>;
}

// -- Constants --
const TURN_TERMINAL_STATUSES = new Set<TurnStatus>(["completed", "failed", "cancelled", "interrupted"]);

// -- Pure functions copied --

const USER_ENTRY = (turnId: string) => `${turnId}:user`;

function extractPublicError(update: Record<string, unknown>): PublicError | null {
  const raw = update.publicError ?? update.error;
  if (raw && typeof raw === "object") {
    const record = raw as Record<string, unknown>;
    const code = typeof record.code === "string" ? record.code : "agent_error";
    const message = typeof record.message === "string" ? record.message : "Agent request failed";
    return { code, message };
  }
  if (typeof raw === "string") return { code: "agent_error", message: raw };
  return null;
}

function canWriteToTurn(turnStatus: TurnStatus | null): boolean {
  if (!turnStatus || turnStatus === "cancelling") return false;
  return !TURN_TERMINAL_STATUSES.has(turnStatus);
}

function extractText(event: NormalizedEvent): string {
  const content = event.content;
  if (content) {
    const text = content.text;
    if (typeof text === "string") return text;
  }
  const updateText = event.update.text;
  return typeof updateText === "string" ? updateText : "";
}

function extractToolCallId(event: NormalizedEvent): string | null {
  const direct = event.update.toolCallId;
  if (typeof direct === "string" && direct.length > 0) return direct;
  const inner = event.content?.id;
  if (typeof inner === "string" && inner.length > 0) return inner;
  return null;
}

function extractQuestionItems(raw: unknown): QuestionItemProjection[] {
  if (!Array.isArray(raw)) return [];
  const items: QuestionItemProjection[] = [];
  for (const entry of raw) {
    if (typeof entry !== "object" || entry === null) continue;
    const record = entry as Record<string, unknown>;
    if (typeof record.question !== "string" || record.question.length === 0) continue;
    const options = Array.isArray(record.options)
      ? record.options
          .filter((o): o is Record<string, unknown> => typeof o === "object" && o !== null)
          .filter((o) => typeof o.label === "string" && o.label.length > 0)
          .map((o) => ({
            label: o.label as string,
            description: typeof o.description === "string" ? o.description : null,
          }))
      : [];
    items.push({
      question: record.question,
      header: typeof record.header === "string" && record.header.length > 0 ? record.header : null,
      options,
    });
  }
  return items;
}

// ========== Tests ==========

describe("USER_ENTRY", () => {
  test("creates user entry ID from turnId", () => {
    expect(USER_ENTRY("turn-123")).toBe("turn-123:user");
  });

  test("handles empty turnId", () => {
    expect(USER_ENTRY("")).toBe(":user");
  });

  test("handles turnId with special characters", () => {
    expect(USER_ENTRY("turn_replay_abc")).toBe("turn_replay_abc:user");
  });
});

describe("extractPublicError", () => {
  test("extracts error from publicError object with code and message", () => {
    const result = extractPublicError({ publicError: { code: "timeout", message: "Request timed out" } });
    expect(result).toEqual({ code: "timeout", message: "Request timed out" });
  });

  test("extracts error from error object with code and message", () => {
    const result = extractPublicError({ error: { code: "auth_failed", message: "Authentication failed" } });
    expect(result).toEqual({ code: "auth_failed", message: "Authentication failed" });
  });

  test("defaults code to agent_error when code is not a string", () => {
    const result = extractPublicError({ publicError: { code: 42, message: "Something failed" } });
    expect(result).toEqual({ code: "agent_error", message: "Something failed" });
  });

  test("defaults message to 'Agent request failed' when message is not a string", () => {
    const result = extractPublicError({ publicError: { code: "custom_error", message: 123 } });
    expect(result).toEqual({ code: "custom_error", message: "Agent request failed" });
  });

  test("defaults both when object has no valid fields", () => {
    const result = extractPublicError({ publicError: {} });
    expect(result).toEqual({ code: "agent_error", message: "Agent request failed" });
  });

  test("handles string error value", () => {
    const result = extractPublicError({ error: "Something went wrong" });
    expect(result).toEqual({ code: "agent_error", message: "Something went wrong" });
  });

  test("returns null when no error present", () => {
    expect(extractPublicError({})).toBeNull();
  });

  test("returns null when error is null", () => {
    expect(extractPublicError({ error: null })).toBeNull();
  });

  test("returns null when error is undefined", () => {
    expect(extractPublicError({ error: undefined })).toBeNull();
  });

  test("returns null when error is a number", () => {
    expect(extractPublicError({ error: 500 })).toBeNull();
  });

  test("returns null when error is boolean", () => {
    expect(extractPublicError({ error: true })).toBeNull();
  });

  test("publicError takes priority over error", () => {
    const result = extractPublicError({
      publicError: { code: "primary", message: "Primary error" },
      error: { code: "secondary", message: "Secondary error" },
    });
    expect(result).toEqual({ code: "primary", message: "Primary error" });
  });

  test("falls back to error when publicError is null", () => {
    const result = extractPublicError({
      publicError: null,
      error: { code: "fallback", message: "Fallback error" },
    });
    // publicError ?? error = error (since publicError is null)
    expect(result).toEqual({ code: "fallback", message: "Fallback error" });
  });
});

describe("canWriteToTurn", () => {
  test("returns false for null status", () => {
    expect(canWriteToTurn(null)).toBe(false);
  });

  test("returns false for cancelling status", () => {
    expect(canWriteToTurn("cancelling")).toBe(false);
  });

  test("returns false for completed status", () => {
    expect(canWriteToTurn("completed")).toBe(false);
  });

  test("returns false for failed status", () => {
    expect(canWriteToTurn("failed")).toBe(false);
  });

  test("returns false for cancelled status", () => {
    expect(canWriteToTurn("cancelled")).toBe(false);
  });

  test("returns false for interrupted status", () => {
    expect(canWriteToTurn("interrupted")).toBe(false);
  });

  test("returns true for accepting status", () => {
    expect(canWriteToTurn("accepting")).toBe(true);
  });

  test("returns true for running status", () => {
    expect(canWriteToTurn("running")).toBe(true);
  });

  test("returns true for awaiting_permission status", () => {
    expect(canWriteToTurn("awaiting_permission")).toBe(true);
  });

  test("returns true for waiting_user status", () => {
    expect(canWriteToTurn("waiting_user")).toBe(true);
  });

  test("canWriteToTurn 空字符串返回 false", () => {
    // "" is falsy → !turnStatus is true → returns false
    expect(canWriteToTurn("" as any)).toBe(false);
  });
});

describe("extractText", () => {
  test("extracts text from content.text", () => {
    const event: NormalizedEvent = {
      type: "message_delta",
      content: { text: "Hello world" },
      update: {},
    };
    expect(extractText(event)).toBe("Hello world");
  });

  test("falls back to update.text when content.text is missing", () => {
    const event: NormalizedEvent = {
      type: "message_delta",
      content: {},
      update: { text: "Fallback text" },
    };
    expect(extractText(event)).toBe("Fallback text");
  });

  test("falls back to update.text when content is undefined", () => {
    const event: NormalizedEvent = {
      type: "message_delta",
      update: { text: "No content" },
    };
    expect(extractText(event)).toBe("No content");
  });

  test("returns empty string when neither has text", () => {
    const event: NormalizedEvent = {
      type: "message_delta",
      content: {},
      update: {},
    };
    expect(extractText(event)).toBe("");
  });

  test("content.text takes priority over update.text", () => {
    const event: NormalizedEvent = {
      type: "message_delta",
      content: { text: "primary" },
      update: { text: "secondary" },
    };
    expect(extractText(event)).toBe("primary");
  });

  test("returns empty string when content.text is not a string", () => {
    const event: NormalizedEvent = {
      type: "message_delta",
      content: { text: 123 },
      update: {},
    };
    expect(extractText(event)).toBe("");
  });

  test("returns empty string when update.text is not a string", () => {
    const event: NormalizedEvent = {
      type: "message_delta",
      update: { text: true },
    };
    expect(extractText(event)).toBe("");
  });

  test("handles empty string text", () => {
    const event: NormalizedEvent = {
      type: "message_delta",
      content: { text: "" },
      update: { text: "fallback" },
    };
    // content.text is "" which is typeof string, so it returns ""
    expect(extractText(event)).toBe("");
  });
});

describe("extractToolCallId", () => {
  test("extracts toolCallId from update directly", () => {
    const event: NormalizedEvent = {
      type: "tool_call_started",
      update: { toolCallId: "tool-123" },
    };
    expect(extractToolCallId(event)).toBe("tool-123");
  });

  test("falls back to content.id", () => {
    const event: NormalizedEvent = {
      type: "tool_call_started",
      content: { id: "tool-456" },
      update: {},
    };
    expect(extractToolCallId(event)).toBe("tool-456");
  });

  test("update.toolCallId takes priority over content.id", () => {
    const event: NormalizedEvent = {
      type: "tool_call_started",
      content: { id: "inner-id" },
      update: { toolCallId: "direct-id" },
    };
    expect(extractToolCallId(event)).toBe("direct-id");
  });

  test("returns null when both are missing", () => {
    const event: NormalizedEvent = {
      type: "tool_call_started",
      update: {},
    };
    expect(extractToolCallId(event)).toBeNull();
  });

  test("returns null when toolCallId is empty string", () => {
    const event: NormalizedEvent = {
      type: "tool_call_started",
      update: { toolCallId: "" },
    };
    expect(extractToolCallId(event)).toBeNull();
  });

  test("falls back to content.id when update.toolCallId is empty", () => {
    const event: NormalizedEvent = {
      type: "tool_call_started",
      content: { id: "fallback-id" },
      update: { toolCallId: "" },
    };
    expect(extractToolCallId(event)).toBe("fallback-id");
  });

  test("returns null when content.id is empty string", () => {
    const event: NormalizedEvent = {
      type: "tool_call_started",
      content: { id: "" },
      update: {},
    };
    expect(extractToolCallId(event)).toBeNull();
  });

  test("returns null when toolCallId is not a string", () => {
    const event: NormalizedEvent = {
      type: "tool_call_started",
      update: { toolCallId: 42 },
    };
    expect(extractToolCallId(event)).toBeNull();
  });

  test("returns null when content is undefined and update has no toolCallId", () => {
    const event: NormalizedEvent = {
      type: "tool_call_started",
      update: { name: "some_tool" },
    };
    expect(extractToolCallId(event)).toBeNull();
  });
});

describe("extractQuestionItems", () => {
  test("returns empty array for non-array input", () => {
    expect(extractQuestionItems(null)).toEqual([]);
    expect(extractQuestionItems(undefined)).toEqual([]);
    expect(extractQuestionItems("string")).toEqual([]);
    expect(extractQuestionItems(42)).toEqual([]);
    expect(extractQuestionItems({})).toEqual([]);
  });

  test("returns empty array for empty array", () => {
    expect(extractQuestionItems([])).toEqual([]);
  });

  test("extracts valid question item", () => {
    const input = [{ question: "What color?", options: [{ label: "Red" }, { label: "Blue" }] }];
    const result = extractQuestionItems(input);
    expect(result).toEqual([
      {
        question: "What color?",
        header: null,
        options: [
          { label: "Red", description: null },
          { label: "Blue", description: null },
        ],
      },
    ]);
  });

  test("extracts header when present and non-empty", () => {
    const input = [{ question: "Pick one", header: "Theme", options: [] }];
    const result = extractQuestionItems(input);
    expect(result[0].header).toBe("Theme");
  });

  test("sets header to null when empty string", () => {
    const input = [{ question: "Pick one", header: "", options: [] }];
    const result = extractQuestionItems(input);
    expect(result[0].header).toBeNull();
  });

  test("sets header to null when not a string", () => {
    const input = [{ question: "Pick one", header: 123, options: [] }];
    const result = extractQuestionItems(input);
    expect(result[0].header).toBeNull();
  });

  test("extracts option description when present", () => {
    const input = [{ question: "Q?", options: [{ label: "A", description: "Option A details" }] }];
    const result = extractQuestionItems(input);
    expect(result[0].options[0].description).toBe("Option A details");
  });

  test("sets option description to null when not a string", () => {
    const input = [{ question: "Q?", options: [{ label: "A", description: 42 }] }];
    const result = extractQuestionItems(input);
    expect(result[0].options[0].description).toBeNull();
  });

  test("skips non-object entries", () => {
    const input = [null, 42, "string", undefined, true];
    expect(extractQuestionItems(input)).toEqual([]);
  });

  test("skips entries with non-string question", () => {
    const input = [{ question: 123 }, { question: null }, { question: true }];
    expect(extractQuestionItems(input)).toEqual([]);
  });

  test("skips entries with empty question string", () => {
    const input = [{ question: "" }];
    expect(extractQuestionItems(input)).toEqual([]);
  });

  test("filters out options with non-string label", () => {
    const input = [
      {
        question: "Q?",
        options: [{ label: 123 }, { label: "Valid" }, { label: "" }, { label: null }],
      },
    ];
    const result = extractQuestionItems(input);
    expect(result[0].options).toEqual([{ label: "Valid", description: null }]);
  });

  test("filters out non-object options", () => {
    const input = [{ question: "Q?", options: ["string", 42, null, { label: "OK" }] }];
    const result = extractQuestionItems(input);
    expect(result[0].options).toEqual([{ label: "OK", description: null }]);
  });

  test("returns empty options array when options is not an array", () => {
    const input = [{ question: "Q?", options: "not an array" }];
    const result = extractQuestionItems(input);
    expect(result[0].options).toEqual([]);
  });

  test("handles missing options field", () => {
    const input = [{ question: "Q?" }];
    const result = extractQuestionItems(input);
    expect(result[0].options).toEqual([]);
  });

  test("handles multiple valid items", () => {
    const input = [
      { question: "Q1?", header: "First", options: [{ label: "A" }] },
      { question: "Q2?", options: [{ label: "B", description: "desc" }] },
      { question: "", options: [] }, // skipped
      "invalid", // skipped
      { question: "Q3?", header: "Third", options: [] },
    ];
    const result = extractQuestionItems(input);
    expect(result.length).toBe(3);
    expect(result[0].question).toBe("Q1?");
    expect(result[1].question).toBe("Q2?");
    expect(result[2].question).toBe("Q3?");
  });
});
