import { describe, test, expect } from "bun:test";

// ========== Pure function copies from packages/acp-link/src/elicitation.ts ==========

function parseElicitationSchema(
  schema: unknown,
): Array<{
  question: string;
  header: string | null;
  options: Array<{ label: string; description: string | null }>;
}> {
  if (!schema || typeof schema !== "object") return [];
  const properties = (schema as Record<string, unknown>).properties;
  if (!properties || typeof properties !== "object") return [];
  return Object.entries(properties as Record<string, Record<string, unknown>>)
    .map(([, prop]) => {
      const p = prop as Record<string, unknown>;
      let optionsRaw: unknown[] = [];
      if (Array.isArray(p.oneOf)) {
        optionsRaw = p.oneOf;
      } else if (Array.isArray(p.items)) {
        optionsRaw = p.items;
      } else if (
        p.items &&
        typeof p.items === "object" &&
        Array.isArray((p.items as Record<string, unknown>).anyOf)
      ) {
        optionsRaw = (p.items as Record<string, unknown>).anyOf as unknown[];
      }
      const options = (optionsRaw as Record<string, unknown>[])
        .map((o) => ({
          label:
            typeof o.const === "string" && o.const.length > 0
              ? o.const
              : typeof o.title === "string"
                ? o.title
                : "",
          description: typeof o.description === "string" ? o.description : null,
        }))
        .filter((o) => o.label.length > 0);
      return {
        question: typeof p.description === "string" ? p.description : "",
        header: typeof p.title === "string" && p.title.length > 0 ? p.title : null,
        options,
      };
    })
    .filter((q) => q.question.length > 0);
}

function extractPropertyKeys(schema: unknown): string[] {
  if (!schema || typeof schema !== "object") return [];
  const properties = (schema as Record<string, unknown>).properties;
  if (!properties || typeof properties !== "object") return [];
  return Object.keys(properties as Record<string, unknown>);
}

function buildElicitationContent(
  extra: Record<string, unknown> | undefined,
  propertyKeys: string[],
): Record<string, unknown> {
  const answers = extra?.answers;
  if (Array.isArray(answers)) {
    const content: Record<string, unknown> = {};
    for (let i = 0; i < propertyKeys.length; i++) {
      const label = answers[i];
      if (typeof label === "string" && label.length > 0) {
        content[propertyKeys[i] as string] = label;
      }
    }
    return content;
  }
  const outcome = extra?.outcome as Record<string, unknown> | undefined;
  if (outcome && typeof outcome.optionId === "string" && outcome.optionId.length > 0) {
    return propertyKeys.length > 0 ? { [propertyKeys[0] as string]: outcome.optionId } : {};
  }
  return {};
}

// ========== Tests ==========

describe("parseElicitationSchema", () => {
  test("returns empty array for null", () => {
    expect(parseElicitationSchema(null)).toEqual([]);
  });

  test("returns empty array for non-object", () => {
    expect(parseElicitationSchema("string")).toEqual([]);
    expect(parseElicitationSchema(42)).toEqual([]);
    expect(parseElicitationSchema(undefined)).toEqual([]);
  });

  test("returns empty array when no properties field", () => {
    expect(parseElicitationSchema({})).toEqual([]);
    expect(parseElicitationSchema({ type: "object" })).toEqual([]);
  });

  test("returns empty array when properties is not an object", () => {
    expect(parseElicitationSchema({ properties: "invalid" })).toEqual([]);
    expect(parseElicitationSchema({ properties: null })).toEqual([]);
  });

  test("parses oneOf options", () => {
    const schema = {
      properties: {
        choice: {
          description: "Pick one",
          title: "Choice",
          oneOf: [
            { const: "option_a", description: "First option" },
            { const: "option_b", description: "Second option" },
          ],
        },
      },
    };
    const result = parseElicitationSchema(schema);
    expect(result.length).toBe(1);
    expect(result[0].question).toBe("Pick one");
    expect(result[0].header).toBe("Choice");
    expect(result[0].options).toEqual([
      { label: "option_a", description: "First option" },
      { label: "option_b", description: "Second option" },
    ]);
  });

  test("parses items array options", () => {
    const schema = {
      properties: {
        tags: {
          description: "Select tags",
          items: [
            { const: "tag1", title: "Tag 1" },
            { const: "tag2" },
          ],
        },
      },
    };
    const result = parseElicitationSchema(schema);
    expect(result.length).toBe(1);
    expect(result[0].options).toEqual([
      { label: "tag1", description: null },
      { label: "tag2", description: null },
    ]);
  });

  test("parses items.anyOf options", () => {
    const schema = {
      properties: {
        color: {
          description: "Pick color",
          items: {
            anyOf: [
              { const: "red", description: "Red color" },
              { const: "blue", description: "Blue color" },
            ],
          },
        },
      },
    };
    const result = parseElicitationSchema(schema);
    expect(result.length).toBe(1);
    expect(result[0].options).toEqual([
      { label: "red", description: "Red color" },
      { label: "blue", description: "Blue color" },
    ]);
  });

  test("filters out options with empty labels", () => {
    const schema = {
      properties: {
        q: {
          description: "Question",
          oneOf: [
            { const: "", title: "Fallback" },
            { const: "valid" },
            { description: "no const or title" },
          ],
        },
      },
    };
    const result = parseElicitationSchema(schema);
    expect(result[0].options).toEqual([
      { label: "Fallback", description: null },
      { label: "valid", description: null },
    ]);
  });

  test("filters out properties with no description (empty question)", () => {
    const schema = {
      properties: {
        noDesc: {
          oneOf: [{ const: "a" }],
        },
        withDesc: {
          description: "Has description",
          oneOf: [{ const: "b" }],
        },
      },
    };
    const result = parseElicitationSchema(schema);
    expect(result.length).toBe(1);
    expect(result[0].question).toBe("Has description");
  });

  test("header is null when title is missing or empty", () => {
    const schema = {
      properties: {
        noTitle: {
          description: "No title question",
          oneOf: [{ const: "a" }],
        },
        emptyTitle: {
          description: "Empty title question",
          title: "",
          oneOf: [{ const: "b" }],
        },
      },
    };
    const result = parseElicitationSchema(schema);
    expect(result[0].header).toBeNull();
    expect(result[1].header).toBeNull();
  });

  test("uses title as label fallback when const is empty", () => {
    const schema = {
      properties: {
        q: {
          description: "Question",
          oneOf: [{ const: "", title: "Title Fallback" }],
        },
      },
    };
    const result = parseElicitationSchema(schema);
    expect(result[0].options[0].label).toBe("Title Fallback");
  });

  test("handles multiple properties", () => {
    const schema = {
      properties: {
        q1: {
          description: "Question 1",
          oneOf: [{ const: "a" }],
        },
        q2: {
          description: "Question 2",
          oneOf: [{ const: "b" }],
        },
      },
    };
    const result = parseElicitationSchema(schema);
    expect(result.length).toBe(2);
    expect(result[0].question).toBe("Question 1");
    expect(result[1].question).toBe("Question 2");
  });
});

describe("extractPropertyKeys", () => {
  test("extracts keys from schema properties", () => {
    const schema = {
      properties: {
        name: { type: "string" },
        age: { type: "number" },
        email: { type: "string" },
      },
    };
    expect(extractPropertyKeys(schema)).toEqual(["name", "age", "email"]);
  });

  test("returns empty array for null", () => {
    expect(extractPropertyKeys(null)).toEqual([]);
  });

  test("returns empty array for undefined", () => {
    expect(extractPropertyKeys(undefined)).toEqual([]);
  });

  test("returns empty array for non-object", () => {
    expect(extractPropertyKeys("string")).toEqual([]);
    expect(extractPropertyKeys(42)).toEqual([]);
  });

  test("returns empty array when no properties field", () => {
    expect(extractPropertyKeys({})).toEqual([]);
    expect(extractPropertyKeys({ type: "object" })).toEqual([]);
  });

  test("returns empty array when properties is not an object", () => {
    expect(extractPropertyKeys({ properties: "bad" })).toEqual([]);
    expect(extractPropertyKeys({ properties: null })).toEqual([]);
  });

  test("returns empty array for empty properties", () => {
    expect(extractPropertyKeys({ properties: {} })).toEqual([]);
  });
});

describe("buildElicitationContent", () => {
  test("builds content from answers array", () => {
    const extra = { answers: ["Yes", "No"] };
    const keys = ["agree", "subscribe"];
    expect(buildElicitationContent(extra, keys)).toEqual({
      agree: "Yes",
      subscribe: "No",
    });
  });

  test("skips empty string answers", () => {
    const extra = { answers: ["Yes", ""] };
    const keys = ["agree", "subscribe"];
    expect(buildElicitationContent(extra, keys)).toEqual({
      agree: "Yes",
    });
  });

  test("skips non-string answers", () => {
    const extra = { answers: ["Yes", 42, null] };
    const keys = ["a", "b", "c"];
    expect(buildElicitationContent(extra, keys)).toEqual({
      a: "Yes",
    });
  });

  test("handles more keys than answers", () => {
    const extra = { answers: ["only-one"] };
    const keys = ["first", "second"];
    expect(buildElicitationContent(extra, keys)).toEqual({
      first: "only-one",
    });
  });

  test("handles more answers than keys", () => {
    const extra = { answers: ["a", "b", "c"] };
    const keys = ["first"];
    expect(buildElicitationContent(extra, keys)).toEqual({
      first: "a",
    });
  });

  test("builds content from outcome (legacy format)", () => {
    const extra = { outcome: { optionId: "selected_option" } };
    const keys = ["choice"];
    expect(buildElicitationContent(extra, keys)).toEqual({
      choice: "selected_option",
    });
  });

  test("outcome with empty optionId returns empty object", () => {
    const extra = { outcome: { optionId: "" } };
    const keys = ["choice"];
    expect(buildElicitationContent(extra, keys)).toEqual({});
  });

  test("outcome with no property keys returns empty object", () => {
    const extra = { outcome: { optionId: "opt" } };
    expect(buildElicitationContent(extra, [])).toEqual({});
  });

  test("returns empty object for undefined extra", () => {
    expect(buildElicitationContent(undefined, ["key"])).toEqual({});
  });

  test("returns empty object for extra with no answers or outcome", () => {
    expect(buildElicitationContent({}, ["key"])).toEqual({});
  });

  test("returns empty object for empty property keys with answers", () => {
    const extra = { answers: ["val"] };
    expect(buildElicitationContent(extra, [])).toEqual({});
  });
});

// ========== createElicitationHandler (copied from elicitation.ts) ==========

interface InteractiveQuestionPayloadLocal {
  sessionId: string;
  questionId: string;
  toolId: string;
  toolName: string;
  questions: Array<{
    question: string;
    header: string | null;
    options: Array<{ label: string; description: string | null }>;
  }>;
  description: string;
}

interface PendingElicitationLocal {
  resolve: (content: Record<string, unknown>) => void;
  timeout: ReturnType<typeof setTimeout>;
  propertyKeys: string[];
}

interface ElicitationHandlerLocal {
  handle: (params: Record<string, unknown>) => Promise<{ action: "accept"; content: Record<string, unknown> }>;
  resolve: (requestId: string, extra: Record<string, unknown> | undefined) => boolean;
  cancelAll: () => void;
}

function createElicitationHandler(
  send: (payload: InteractiveQuestionPayloadLocal) => void,
  timeoutMs: number = 60_000,
): ElicitationHandlerLocal {
  const pending = new Map<string, PendingElicitationLocal>();

  return {
    async handle(params: Record<string, unknown>) {
      const sessionId = (params?.sessionId as string) ?? "";
      const questions = parseElicitationSchema(params?.requestedSchema);
      const propertyKeys = extractPropertyKeys(params?.requestedSchema);
      const questionId = `iqa_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

      const answer = await new Promise<Record<string, unknown>>((resolve) => {
        const timeout = setTimeout(() => {
          pending.delete(questionId);
          resolve({});
        }, timeoutMs);
        pending.set(questionId, { resolve, timeout, propertyKeys });
        send({
          sessionId,
          questionId,
          toolId: "elicitation",
          toolName: "AskUserQuestion",
          questions,
          description: typeof params?.message === "string" ? params.message : "Please answer the following questions",
        });
      });

      return { action: "accept" as const, content: answer };
    },

    resolve(requestId, extra) {
      const item = pending.get(requestId);
      if (!item) return false;
      clearTimeout(item.timeout);
      pending.delete(requestId);
      item.resolve(buildElicitationContent(extra, item.propertyKeys));
      return true;
    },

    cancelAll() {
      for (const [, item] of pending) {
        clearTimeout(item.timeout);
        item.resolve({});
      }
      pending.clear();
    },
  };
}

// ========== createElicitationHandler Tests ==========

describe("createElicitationHandler", () => {
  test("handle sends interactive_question frame and resolves with accept on answer", async () => {
    const sentPayloads: InteractiveQuestionPayloadLocal[] = [];
    const handler = createElicitationHandler((payload) => {
      sentPayloads.push(payload);
    });

    const schema = {
      properties: {
        choice: {
          description: "Pick one",
          title: "Choice",
          oneOf: [
            { const: "option_a" },
            { const: "option_b" },
          ],
        },
      },
    };

    const handlePromise = handler.handle({
      sessionId: "sess-1",
      message: "Please choose",
      requestedSchema: schema,
    });

    // Wait a tick for the send to happen
    await new Promise((r) => setTimeout(r, 10));

    expect(sentPayloads.length).toBe(1);
    expect(sentPayloads[0].sessionId).toBe("sess-1");
    expect(sentPayloads[0].toolId).toBe("elicitation");
    expect(sentPayloads[0].toolName).toBe("AskUserQuestion");
    expect(sentPayloads[0].description).toBe("Please choose");
    expect(sentPayloads[0].questions.length).toBe(1);

    const questionId = sentPayloads[0].questionId;

    // Resolve with answer
    const resolved = handler.resolve(questionId, { answers: ["option_a"] });
    expect(resolved).toBe(true);

    const result = await handlePromise;
    expect(result.action).toBe("accept");
    expect(result.content).toEqual({ choice: "option_a" });
  });

  test("handle resolves with empty answer on timeout", async () => {
    const handler = createElicitationHandler(
      () => {},
      50, // 50ms timeout for fast testing
    );

    const schema = {
      properties: {
        q1: {
          description: "Question 1",
          oneOf: [{ const: "a" }],
        },
      },
    };

    const result = await handler.handle({
      sessionId: "sess-2",
      requestedSchema: schema,
    });

    // After timeout, should resolve with empty content
    expect(result.action).toBe("accept");
    expect(result.content).toEqual({});
  });

  test("cancelAll resolves all pending with empty answers", async () => {
    const handler = createElicitationHandler(
      () => {},
      10_000, // Long timeout to ensure cancelAll fires before timeout
    );

    const schema = {
      properties: {
        q1: { description: "Q1", oneOf: [{ const: "a" }] },
      },
    };

    // Create two pending handles
    const p1 = handler.handle({ sessionId: "s1", requestedSchema: schema });
    const p2 = handler.handle({ sessionId: "s2", requestedSchema: schema });

    // Wait a tick for setup
    await new Promise((r) => setTimeout(r, 10));

    handler.cancelAll();

    const [r1, r2] = await Promise.all([p1, p2]);
    expect(r1.action).toBe("accept");
    expect(r1.content).toEqual({});
    expect(r2.action).toBe("accept");
    expect(r2.content).toEqual({});
  });

  test("resolve returns false for unknown requestId", () => {
    const handler = createElicitationHandler(() => {});
    const result = handler.resolve("nonexistent-id", { answers: ["x"] });
    expect(result).toBe(false);
  });

  test("handle uses default description when message is not a string", async () => {
    const sentPayloads: InteractiveQuestionPayloadLocal[] = [];
    const handler = createElicitationHandler((payload) => {
      sentPayloads.push(payload);
    });

    const schema = {
      properties: {
        q1: { description: "Q1", oneOf: [{ const: "a" }] },
      },
    };

    const handlePromise = handler.handle({ sessionId: "s1", requestedSchema: schema });

    await new Promise((r) => setTimeout(r, 10));

    expect(sentPayloads[0].description).toBe("Please answer the following questions");

    // Clean up by resolving
    handler.resolve(sentPayloads[0].questionId, { answers: ["a"] });
    await handlePromise;
  });
});
