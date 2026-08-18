import { describe, test, expect } from "bun:test";

// --- Pure functions copied from source ---

const DEFAULT_AGENT_SYSTEM_PROMPT = [
  "你当前的 Agent 名称是「{{agentName}}」。",
  "任何情况下都不要提到底层引擎、运行时或实现名称。",
  "如果下面的 User Prompt 明确规定了你的身份或自我介绍，以其中的规定为准。",
  "如果下面的 User Prompt 没有规定身份，默认回答你是 FENIXAGENT。",
  "",
  "## User Prompt",
  "{{userPrompt}}",
].join("\n");

function composeAgentSystemPrompt(
  systemPromptTemplate: string,
  agentName: string,
  userPrompt?: string | null,
): string {
  const trimmedUserPrompt = userPrompt?.trim() ?? "";
  const basePrompt = systemPromptTemplate
    .replaceAll("{{agentName}}", agentName)
    .replaceAll("{{userPrompt}}", trimmedUserPrompt);

  if (systemPromptTemplate.includes("{{userPrompt}}")) {
    return basePrompt.trim();
  }
  if (!trimmedUserPrompt) {
    return basePrompt;
  }
  return `${basePrompt}\n\n## User Prompt\n${trimmedUserPrompt}`;
}

// --- Tests ---

describe("DEFAULT_AGENT_SYSTEM_PROMPT", () => {
  test("contains agentName placeholder", () => {
    expect(DEFAULT_AGENT_SYSTEM_PROMPT).toContain("{{agentName}}");
  });

  test("contains userPrompt placeholder", () => {
    expect(DEFAULT_AGENT_SYSTEM_PROMPT).toContain("{{userPrompt}}");
  });

  test("contains User Prompt section header", () => {
    expect(DEFAULT_AGENT_SYSTEM_PROMPT).toContain("## User Prompt");
  });
});

describe("composeAgentSystemPrompt", () => {
  test("renders default template with agent name and user prompt", () => {
    const result = composeAgentSystemPrompt(
      DEFAULT_AGENT_SYSTEM_PROMPT,
      "MyAgent",
      "Help users with questions",
    );
    expect(result).toContain("「MyAgent」");
    expect(result).toContain("Help users with questions");
    expect(result).not.toContain("{{agentName}}");
    expect(result).not.toContain("{{userPrompt}}");
  });

  test("replaces agentName in template", () => {
    const template = "Agent: {{agentName}}";
    const result = composeAgentSystemPrompt(template, "TestBot");
    expect(result).toBe("Agent: TestBot");
  });

  test("replaces multiple agentName occurrences", () => {
    const template = "{{agentName}} is named {{agentName}}";
    const result = composeAgentSystemPrompt(template, "Bot");
    expect(result).toBe("Bot is named Bot");
  });

  test("replaces userPrompt in template that has the placeholder", () => {
    const template = "Instructions:\n{{userPrompt}}";
    const result = composeAgentSystemPrompt(template, "Agent", "Do something");
    expect(result).toBe("Instructions:\nDo something");
  });

  test("template without userPrompt placeholder appends fallback section", () => {
    const template = "System instructions for {{agentName}}";
    const result = composeAgentSystemPrompt(template, "Bot", "Be helpful");
    expect(result).toBe("System instructions for Bot\n\n## User Prompt\nBe helpful");
  });

  test("template without userPrompt placeholder and empty userPrompt does not append", () => {
    const template = "System instructions for {{agentName}}";
    const result = composeAgentSystemPrompt(template, "Bot", "");
    expect(result).toBe("System instructions for Bot");
  });

  test("template without userPrompt placeholder and null userPrompt does not append", () => {
    const template = "System instructions for {{agentName}}";
    const result = composeAgentSystemPrompt(template, "Bot", null);
    expect(result).toBe("System instructions for Bot");
  });

  test("template without userPrompt placeholder and undefined userPrompt does not append", () => {
    const template = "System instructions for {{agentName}}";
    const result = composeAgentSystemPrompt(template, "Bot");
    expect(result).toBe("System instructions for Bot");
  });

  test("null userPrompt treated as empty string in template with placeholder", () => {
    const result = composeAgentSystemPrompt(
      DEFAULT_AGENT_SYSTEM_PROMPT,
      "Agent",
      null,
    );
    expect(result).toContain("「Agent」");
    // userPrompt placeholder replaced with empty string, then trimmed
    expect(result).not.toContain("{{userPrompt}}");
  });

  test("undefined userPrompt treated as empty string in template with placeholder", () => {
    const result = composeAgentSystemPrompt(
      DEFAULT_AGENT_SYSTEM_PROMPT,
      "Agent",
    );
    expect(result).toContain("「Agent」");
    expect(result).not.toContain("{{userPrompt}}");
  });

  test("whitespace-only userPrompt is trimmed to empty", () => {
    const template = "Prompt: {{userPrompt}}";
    const result = composeAgentSystemPrompt(template, "Bot", "   \n  \t  ");
    // trimmedUserPrompt is "", placeholder replaced with ""
    expect(result).toBe("Prompt:");
  });

  test("whitespace-only userPrompt with no placeholder does not append", () => {
    const template = "System for {{agentName}}";
    const result = composeAgentSystemPrompt(template, "Bot", "   ");
    // trimmedUserPrompt is "", so no fallback appended
    expect(result).toBe("System for Bot");
  });

  test("userPrompt with leading/trailing whitespace is trimmed", () => {
    const template = "No placeholder here: {{agentName}}";
    const result = composeAgentSystemPrompt(template, "Bot", "  hello world  ");
    expect(result).toBe("No placeholder here: Bot\n\n## User Prompt\nhello world");
  });

  test("default template result is trimmed (no trailing whitespace)", () => {
    const result = composeAgentSystemPrompt(
      DEFAULT_AGENT_SYSTEM_PROMPT,
      "Agent",
      "  ",
    );
    // Should not end with whitespace since the template includes {{userPrompt}} which becomes ""
    // and the whole result is trimmed
    expect(result).not.toMatch(/\s+$/);
  });
});
