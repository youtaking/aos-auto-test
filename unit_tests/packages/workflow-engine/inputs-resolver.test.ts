import { describe, test, expect } from "bun:test";

// ── Pure function copies from packages/workflow-engine/src/parser/inputs-resolver.ts ──
// Only pure functions that don't depend on expression-parser are copied.

/**
 * Detects if a string is entirely wrapped in a single `${{ expr }}` template.
 * Returns the inner expression (trimmed) if matched; null otherwise.
 */
function matchSingleTemplate(raw: string): string | null {
  const trimmed = raw.trim();
  const m = trimmed.match(/^\$\{\{([\s\S]+)\}\}$/);
  if (!m) return null;
  const inner = m[1];
  if (inner.includes("${{") || inner.includes("}}")) return null;
  return inner.trim();
}

/**
 * Converts resolved inputs to shell environment variable mappings.
 * All values are coerced to strings.
 */
interface ResolvedInput {
  value: unknown;
  rawExpression: string;
}

function generateShellEnvVars(resolved: Record<string, ResolvedInput>): Record<string, string> {
  const env: Record<string, string> = {};
  for (const [key, { value }] of Object.entries(resolved)) {
    if (value === null || value === undefined) {
      env[key] = "";
    } else if (typeof value === "object") {
      env[key] = JSON.stringify(value);
    } else {
      env[key] = String(value);
    }
  }
  return env;
}

/**
 * Generates Python variable assignment code from resolved inputs.
 */
function generatePythonPreamble(resolved: Record<string, ResolvedInput>): string {
  const entries = Object.entries(resolved);
  if (entries.length === 0) return "";

  const lines: string[] = [];
  let needsJsonImport = false;

  for (const [varName, { value }] of entries) {
    if (value === null || value === undefined) {
      lines.push(`${varName} = None`);
    } else if (typeof value === "string") {
      lines.push(`${varName} = ${JSON.stringify(value)}`);
    } else if (typeof value === "number") {
      lines.push(`${varName} = ${value}`);
    } else if (typeof value === "boolean") {
      lines.push(`${varName} = ${value ? "True" : "False"}`);
    } else {
      needsJsonImport = true;
      const jsonStr = JSON.stringify(value);
      const escaped = jsonStr.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
      lines.push(`${varName} = json.loads('${escaped}')`);
    }
  }

  if (needsJsonImport) {
    lines.unshift("import json");
  }

  return lines.join("\n");
}

// ── Tests ──

describe("matchSingleTemplate", () => {
  test("matches simple single template", () => {
    expect(matchSingleTemplate("${{ params.x }}")).toBe("params.x");
  });

  test("matches with extra whitespace", () => {
    expect(matchSingleTemplate("  ${{ params.x }}  ")).toBe("params.x");
  });

  test("matches template with complex inner expression", () => {
    expect(matchSingleTemplate("${{ nodes.fetch.output.count }}")).toBe("nodes.fetch.output.count");
  });

  test("matches template with string concatenation inside", () => {
    expect(matchSingleTemplate("${{ 'prefix_' + params.x }}")).toBe("'prefix_' + params.x");
  });

  test("returns null for plain string without template", () => {
    expect(matchSingleTemplate("params.x")).toBeNull();
  });

  test("returns null for multiple templates (concatenation)", () => {
    expect(matchSingleTemplate("${{ params.x }}/${{ params.y }}")).toBeNull();
  });

  test("returns null for template with prefix text", () => {
    expect(matchSingleTemplate("prefix_${{ params.x }}")).toBeNull();
  });

  test("returns null for template with suffix text", () => {
    expect(matchSingleTemplate("${{ params.x }}_suffix")).toBeNull();
  });

  test("returns null for empty string", () => {
    expect(matchSingleTemplate("")).toBeNull();
  });

  test("returns null for just ${{ without closing", () => {
    expect(matchSingleTemplate("${{ params.x")).toBeNull();
  });

  test("matches multiline expression inside template", () => {
    const expr = "${{\n  params.x\n}}";
    expect(matchSingleTemplate(expr)).toBe("params.x");
  });

  test("returns null when inner contains nested ${{ }}", () => {
    expect(matchSingleTemplate("${{ ${{ inner }} }}")).toBeNull();
  });
});

describe("generateShellEnvVars", () => {
  test("converts string values", () => {
    const resolved: Record<string, ResolvedInput> = {
      NAME: { value: "hello", rawExpression: "'hello'" },
    };
    expect(generateShellEnvVars(resolved)).toEqual({ NAME: "hello" });
  });

  test("converts number values", () => {
    const resolved: Record<string, ResolvedInput> = {
      COUNT: { value: 42, rawExpression: "42" },
    };
    expect(generateShellEnvVars(resolved)).toEqual({ COUNT: "42" });
  });

  test("converts boolean values", () => {
    const resolved: Record<string, ResolvedInput> = {
      FLAG: { value: true, rawExpression: "true" },
    };
    expect(generateShellEnvVars(resolved)).toEqual({ FLAG: "true" });
  });

  test("converts null to empty string", () => {
    const resolved: Record<string, ResolvedInput> = {
      EMPTY: { value: null, rawExpression: "null" },
    };
    expect(generateShellEnvVars(resolved)).toEqual({ EMPTY: "" });
  });

  test("converts undefined to empty string", () => {
    const resolved: Record<string, ResolvedInput> = {
      MISSING: { value: undefined, rawExpression: "undefined" },
    };
    expect(generateShellEnvVars(resolved)).toEqual({ MISSING: "" });
  });

  test("converts objects to JSON strings", () => {
    const resolved: Record<string, ResolvedInput> = {
      CONFIG: { value: { a: 1, b: "two" }, rawExpression: "config" },
    };
    expect(generateShellEnvVars(resolved)).toEqual({ CONFIG: '{"a":1,"b":"two"}' });
  });

  test("converts arrays to JSON strings", () => {
    const resolved: Record<string, ResolvedInput> = {
      ITEMS: { value: [1, 2, 3], rawExpression: "items" },
    };
    expect(generateShellEnvVars(resolved)).toEqual({ ITEMS: "[1,2,3]" });
  });

  test("handles empty input", () => {
    expect(generateShellEnvVars({})).toEqual({});
  });

  test("handles multiple mixed types", () => {
    const resolved: Record<string, ResolvedInput> = {
      NAME: { value: "test", rawExpression: "'test'" },
      COUNT: { value: 10, rawExpression: "10" },
      FLAG: { value: false, rawExpression: "false" },
      DATA: { value: null, rawExpression: "null" },
    };
    expect(generateShellEnvVars(resolved)).toEqual({
      NAME: "test",
      COUNT: "10",
      FLAG: "false",
      DATA: "",
    });
  });
});

describe("generatePythonPreamble", () => {
  test("returns empty string for empty input", () => {
    expect(generatePythonPreamble({})).toBe("");
  });

  test("generates None for null values", () => {
    const resolved: Record<string, ResolvedInput> = {
      x: { value: null, rawExpression: "null" },
    };
    expect(generatePythonPreamble(resolved)).toBe("x = None");
  });

  test("generates None for undefined values", () => {
    const resolved: Record<string, ResolvedInput> = {
      x: { value: undefined, rawExpression: "undefined" },
    };
    expect(generatePythonPreamble(resolved)).toBe("x = None");
  });

  test("generates quoted string for string values", () => {
    const resolved: Record<string, ResolvedInput> = {
      name: { value: "hello", rawExpression: "'hello'" },
    };
    expect(generatePythonPreamble(resolved)).toBe('name = "hello"');
  });

  test("generates bare number for number values", () => {
    const resolved: Record<string, ResolvedInput> = {
      count: { value: 42, rawExpression: "42" },
    };
    expect(generatePythonPreamble(resolved)).toBe("count = 42");
  });

  test("generates True/False for boolean values", () => {
    const resolved: Record<string, ResolvedInput> = {
      flag: { value: true, rawExpression: "true" },
      off: { value: false, rawExpression: "false" },
    };
    const result = generatePythonPreamble(resolved);
    expect(result).toContain("flag = True");
    expect(result).toContain("off = False");
  });

  test("generates json.loads for object values with import", () => {
    const resolved: Record<string, ResolvedInput> = {
      config: { value: { a: 1 }, rawExpression: "config" },
    };
    const result = generatePythonPreamble(resolved);
    expect(result).toContain("import json");
    expect(result).toContain("config = json.loads(");
  });

  test("generates json.loads for array values with import", () => {
    const resolved: Record<string, ResolvedInput> = {
      items: { value: [1, 2, 3], rawExpression: "items" },
    };
    const result = generatePythonPreamble(resolved);
    expect(result).toContain("import json");
    expect(result).toContain("items = json.loads(");
  });

  test("import json appears only once for multiple objects", () => {
    const resolved: Record<string, ResolvedInput> = {
      a: { value: { x: 1 }, rawExpression: "a" },
      b: { value: [1], rawExpression: "b" },
    };
    const result = generatePythonPreamble(resolved);
    const importCount = (result.match(/import json/g) || []).length;
    expect(importCount).toBe(1);
  });

  test("import json is at the top of output", () => {
    const resolved: Record<string, ResolvedInput> = {
      x: { value: "hello", rawExpression: "'hello'" },
      y: { value: { z: 1 }, rawExpression: "y" },
    };
    const result = generatePythonPreamble(resolved);
    const lines = result.split("\n");
    expect(lines[0]).toBe("import json");
  });

  test("no import json when only simple types", () => {
    const resolved: Record<string, ResolvedInput> = {
      name: { value: "test", rawExpression: "'test'" },
      count: { value: 5, rawExpression: "5" },
    };
    const result = generatePythonPreamble(resolved);
    expect(result).not.toContain("import json");
  });
});

// ── resolveInputs dependencies (copied from expression-parser.ts) ──

class WorkflowError extends Error {
  readonly code: string;
  constructor(message: string, code: string, public readonly details?: Record<string, unknown>) {
    super(message);
    this.code = code;
    this.name = "WorkflowError";
  }
}

interface ExprEvalContext {
  nodes?: Record<string, unknown>;
  params?: Record<string, unknown>;
  secrets?: Record<string, unknown>;
}

type ExprASTNode =
  | { kind: "literal"; value: unknown }
  | { kind: "identifier"; name: string }
  | { kind: "member_access"; object: ExprASTNode; property: string }
  | { kind: "index_access"; object: ExprASTNode; index: ExprASTNode }
  | { kind: "unary"; op: string; operand: ExprASTNode }
  | { kind: "binary"; op: string; left: ExprASTNode; right: ExprASTNode }
  | { kind: "ternary"; condition: ExprASTNode; consequent: ExprASTNode; alternate: ExprASTNode };

const EXPR_MAX_LENGTH = 1024;
const EXPR_MAX_DEPTH = 10;
const EXPR_BLOCKED = new Set(["__proto__", "constructor", "prototype"]);
const EXPR_ROOTS = new Set(["nodes", "params", "secrets"]);

function exprIsObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

enum ExprTokenType { Ident, Number, String, Dot, LBracket, RBracket, LParen, RParen, Question, Colon, Bang, Op, EOF }
interface ExprToken { type: ExprTokenType; value: string }

class ExprLexer {
  private pos = 0;
  constructor(private readonly source: string) {}
  peek() { return this.pos < this.source.length ? this.source[this.pos] : "\0"; }
  advance() { return this.source[this.pos++]; }
  at(o: number) { const i = this.pos + o; return i < this.source.length ? this.source[i] : "\0"; }
  skipWS() { while (this.pos < this.source.length && /\s/.test(this.source[this.pos])) this.pos++; }
  next(): ExprToken {
    this.skipWS();
    const ch = this.peek();
    if (ch === "\0") return { type: ExprTokenType.EOF, value: "" };
    if (/[0-9]/.test(ch) || (ch === "-" && /[0-9]/.test(this.at(1)))) {
      const s = this.pos; if (ch === "-") this.advance();
      while (/[0-9]/.test(this.peek())) this.advance();
      if (this.peek() === ".") { this.advance(); while (/[0-9]/.test(this.peek())) this.advance(); }
      return { type: ExprTokenType.Number, value: this.source.slice(s, this.pos) };
    }
    if (ch === '"' || ch === "'") return this.readStr();
    if (/[a-zA-Z_$]/.test(ch)) {
      const s = this.pos; while (/[a-zA-Z0-9_$]/.test(this.peek())) this.advance();
      return { type: ExprTokenType.Ident, value: this.source.slice(s, this.pos) };
    }
    this.advance();
    switch (ch) {
      case ".": return { type: ExprTokenType.Dot, value: "." };
      case "[": return { type: ExprTokenType.LBracket, value: "[" };
      case "]": return { type: ExprTokenType.RBracket, value: "]" };
      case "(": return { type: ExprTokenType.LParen, value: "(" };
      case ")": return { type: ExprTokenType.RParen, value: ")" };
      case "?": return { type: ExprTokenType.Question, value: "?" };
      case ":": return { type: ExprTokenType.Colon, value: ":" };
      case "!": if (this.peek() === "=") { this.advance(); return { type: ExprTokenType.Op, value: "!=" }; } return { type: ExprTokenType.Bang, value: "!" };
      case "=": if (this.peek() === "=") { this.advance(); return { type: ExprTokenType.Op, value: "==" }; } throw new WorkflowError(`Unexpected character: '${ch}'`, "INVALID_EXPRESSION");
      case ">": if (this.peek() === "=") { this.advance(); return { type: ExprTokenType.Op, value: ">=" }; } return { type: ExprTokenType.Op, value: ">" };
      case "<": if (this.peek() === "=") { this.advance(); return { type: ExprTokenType.Op, value: "<=" }; } return { type: ExprTokenType.Op, value: "<" };
      case "&": if (this.peek() === "&") { this.advance(); return { type: ExprTokenType.Op, value: "&&" }; } throw new WorkflowError(`Unexpected character: '${ch}'`, "INVALID_EXPRESSION");
      case "|": if (this.peek() === "|") { this.advance(); return { type: ExprTokenType.Op, value: "||" }; } throw new WorkflowError(`Unexpected character: '${ch}'`, "INVALID_EXPRESSION");
      case "+": return { type: ExprTokenType.Op, value: "+" };
      default: throw new WorkflowError(`Unexpected character: '${ch}'`, "INVALID_EXPRESSION");
    }
  }
  private readStr(): ExprToken {
    const q = this.advance(); const s = this.pos;
    while (this.peek() !== q && this.peek() !== "\0") { if (this.peek() === "\\") this.advance(); this.advance(); }
    if (this.peek() === "\0") throw new WorkflowError("Unterminated string literal", "INVALID_EXPRESSION");
    this.advance();
    return { type: ExprTokenType.String, value: this.source.slice(s, this.pos - 1) };
  }
}

class ExprParser {
  private pos = 0;
  constructor(private readonly tokens: ExprToken[]) {}
  peek() { return this.tokens[this.pos] ?? { type: ExprTokenType.EOF, value: "" }; }
  advance() { const t = this.tokens[this.pos]; this.pos++; return t ?? { type: ExprTokenType.EOF, value: "" }; }
  expect(type: ExprTokenType, value?: string) {
    const t = this.peek();
    if (t.type !== type || (value !== undefined && t.value !== value)) throw new WorkflowError(`Expected ${value ?? ExprTokenType[type]} but got '${t.value}'`, "INVALID_EXPRESSION");
    return this.advance();
  }
  parse(): ExprASTNode {
    const n = this.parseTernary();
    if (this.peek().type !== ExprTokenType.EOF) throw new WorkflowError(`Unexpected token after expression: '${this.peek().value}'`, "INVALID_EXPRESSION");
    return n;
  }
  private parseTernary(): ExprASTNode {
    let c = this.parseOr();
    if (this.peek().type === ExprTokenType.Question) { this.advance(); const con = this.parseTernary(); this.expect(ExprTokenType.Colon); const alt = this.parseTernary(); c = { kind: "ternary", condition: c, consequent: con, alternate: alt }; }
    return c;
  }
  private parseOr(): ExprASTNode {
    let l = this.parseAnd();
    while (this.peek().type === ExprTokenType.Op && this.peek().value === "||") { this.advance(); l = { kind: "binary", op: "||", left: l, right: this.parseAnd() }; }
    return l;
  }
  private parseAnd(): ExprASTNode {
    let l = this.parseComparison();
    while (this.peek().type === ExprTokenType.Op && this.peek().value === "&&") { this.advance(); l = { kind: "binary", op: "&&", left: l, right: this.parseComparison() }; }
    return l;
  }
  private parseComparison(): ExprASTNode {
    let l = this.parseConcat();
    const t = this.peek();
    if (t.type === ExprTokenType.Op && ["==", "!=", ">", "<", ">=", "<="].includes(t.value)) { this.advance(); l = { kind: "binary", op: t.value, left: l, right: this.parseConcat() }; }
    return l;
  }
  private parseConcat(): ExprASTNode {
    let l = this.parseUnary();
    while (this.peek().type === ExprTokenType.Op && this.peek().value === "+") { this.advance(); l = { kind: "binary", op: "+", left: l, right: this.parseUnary() }; }
    return l;
  }
  private parseUnary(): ExprASTNode {
    if (this.peek().type === ExprTokenType.Bang) { this.advance(); return { kind: "unary", op: "!", operand: this.parseUnary() }; }
    return this.parsePostfix();
  }
  private parsePostfix(): ExprASTNode {
    let n = this.parsePrimary();
    for (;;) {
      if (this.peek().type === ExprTokenType.Dot) { this.advance(); const p = this.expect(ExprTokenType.Ident); n = { kind: "member_access", object: n, property: p.value }; }
      else if (this.peek().type === ExprTokenType.LBracket) { this.advance(); const idx = this.parseTernary(); this.expect(ExprTokenType.RBracket); n = { kind: "index_access", object: n, index: idx }; }
      else break;
    }
    return n;
  }
  private parsePrimary(): ExprASTNode {
    const t = this.peek();
    if (t.type === ExprTokenType.Number) { this.advance(); return { kind: "literal", value: Number(t.value) }; }
    if (t.type === ExprTokenType.String) { this.advance(); return { kind: "literal", value: t.value }; }
    if (t.type === ExprTokenType.Ident) {
      if (t.value === "null") { this.advance(); return { kind: "literal", value: null }; }
      if (t.value === "true") { this.advance(); return { kind: "literal", value: true }; }
      if (t.value === "false") { this.advance(); return { kind: "literal", value: false }; }
      this.advance(); return { kind: "identifier", name: t.value };
    }
    if (t.type === ExprTokenType.LParen) { this.advance(); const inner = this.parseTernary(); this.expect(ExprTokenType.RParen); return inner; }
    throw new WorkflowError(`Unexpected token: '${t.value}' (${ExprTokenType[t.type]})`, "INVALID_EXPRESSION");
  }
}

function exprParse(expr: string): ExprASTNode {
  if (expr.length > EXPR_MAX_LENGTH) throw new WorkflowError(`Expression exceeds max length ${EXPR_MAX_LENGTH}`, "EXPRESSION_TOO_LONG");
  const lexer = new ExprLexer(expr);
  const tokens: ExprToken[] = [];
  for (;;) { const t = lexer.next(); tokens.push(t); if (t.type === ExprTokenType.EOF) break; }
  return new ExprParser(tokens).parse();
}

function exprEval(ast: ExprASTNode, ctx: ExprEvalContext, depth = 0): unknown {
  if (depth > EXPR_MAX_DEPTH) throw new WorkflowError(`Expression access depth exceeds ${EXPR_MAX_DEPTH}`, "EXPRESSION_TOO_DEEP");
  switch (ast.kind) {
    case "literal": return ast.value;
    case "identifier": {
      if (!EXPR_ROOTS.has(ast.name)) throw new WorkflowError(`Undefined variable: '${ast.name}'`, "UNDEFINED_VARIABLE");
      if (ast.name === "nodes") return ctx.nodes ?? null;
      if (ast.name === "params") return ctx.params ?? null;
      return ctx.secrets ?? null;
    }
    case "member_access": {
      const obj = exprEval(ast.object, ctx, depth + 1);
      if (EXPR_BLOCKED.has(ast.property)) throw new WorkflowError(`Blocked property access: '${ast.property}'`, "UNDEFINED_VARIABLE");
      if (obj === null || obj === undefined) return null;
      if (exprIsObject(obj)) return obj[ast.property] ?? null;
      return null;
    }
    case "index_access": {
      const obj = exprEval(ast.object, ctx, depth + 1);
      const idx = exprEval(ast.index, ctx, depth + 1);
      if (obj === null || obj === undefined) return null;
      if (Array.isArray(obj)) { if (typeof idx === "number") return (idx >= 0 && idx < obj.length ? obj[idx] : null) ?? null; return null; }
      if (exprIsObject(obj) && typeof idx === "string") return obj[idx] ?? null;
      return null;
    }
    case "unary": { if (ast.op === "!") return !exprEval(ast.operand, ctx, depth + 1); throw new WorkflowError(`Unknown unary operator: '${ast.op}'`, "INVALID_EXPRESSION"); }
    case "binary": {
      if (ast.op === "&&") { const l = exprEval(ast.left, ctx, depth + 1); return l ? exprEval(ast.right, ctx, depth + 1) : l; }
      if (ast.op === "||") { const l = exprEval(ast.left, ctx, depth + 1); return l ? l : exprEval(ast.right, ctx, depth + 1); }
      const l = exprEval(ast.left, ctx, depth + 1);
      const r = exprEval(ast.right, ctx, depth + 1);
      switch (ast.op) {
        case "==": return l === r; case "!=": return l !== r;
        case ">": case "<": case ">=": case "<=":
          if (l === null || r === null) return false;
          switch (ast.op) { case ">": return (l as number) > (r as number); case "<": return (l as number) < (r as number); case ">=": return (l as number) >= (r as number); case "<=": return (l as number) <= (r as number); }
          break;
        case "+": if (typeof l === "string" || typeof r === "string") return String(l ?? "") + String(r ?? ""); return (l as number) + (r as number);
        default: throw new WorkflowError(`Unknown binary operator: '${ast.op}'`, "INVALID_EXPRESSION");
      }
    }
    case "ternary": return exprEval(ast.condition, ctx, depth + 1) ? exprEval(ast.consequent, ctx, depth + 1) : exprEval(ast.alternate, ctx, depth + 1);
    default: throw new WorkflowError("Unknown AST node kind", "INVALID_EXPRESSION");
  }
}

function exprStringify(val: unknown): string {
  if (val === null || val === undefined) return "";
  if (typeof val === "string") return val;
  if (typeof val === "number" || typeof val === "boolean") return String(val);
  if (typeof val === "object") {
    const o = val as Record<string, unknown>;
    if (typeof o.simplified === "string") return o.simplified;
    if (typeof o.stdout === "string") return o.stdout;
    return JSON.stringify(val);
  }
  return String(val);
}

function exprResolveTemplate(template: string, ctx: ExprEvalContext): string {
  const result: string[] = [];
  let lastEnd = 0;
  for (let i = 0; i < template.length; i++) {
    if (template[i] === "$" && template[i + 1] === "{" && template[i + 2] === "{") {
      result.push(template.slice(lastEnd, i));
      let depth = 1; let j = i + 3;
      for (; j < template.length; j++) {
        if (template[j] === "}" && template[j + 1] === "}") { depth--; if (depth === 0) break; j++; }
        if (template[j] === "{" && template[j + 1] === "{") { depth++; j++; }
      }
      if (depth !== 0) throw new WorkflowError("Unterminated ${{ expression", "INVALID_EXPRESSION");
      const expr = template.slice(i + 3, j).trim();
      const val = exprEval(exprParse(expr), ctx);
      result.push(val === null || val === undefined ? "" : exprStringify(val));
      lastEnd = j + 2; i = j + 1;
    }
  }
  result.push(template.slice(lastEnd));
  return result.join("");
}

// ── resolveInputs (copied from inputs-resolver.ts) ──

interface ResolvedInputFull {
  value: unknown;
  rawExpression: string;
}

function matchSingleTemplateLocal(raw: string): string | null {
  const trimmed = raw.trim();
  const m = trimmed.match(/^\$\{\{([\s\S]+)\}\}$/);
  if (!m) return null;
  const inner = m[1];
  if (inner.includes("${{") || inner.includes("}}")) return null;
  return inner.trim();
}

function resolveInputs(inputs: Record<string, string>, context: ExprEvalContext): Record<string, ResolvedInputFull> {
  const resolved: Record<string, ResolvedInputFull> = {};
  for (const [key, expr] of Object.entries(inputs)) {
    try {
      let value: unknown;
      const singleInner = matchSingleTemplateLocal(expr);
      if (singleInner !== null) {
        const ast = exprParse(singleInner);
        value = exprEval(ast, context);
      } else if (expr.includes("${{")) {
        value = exprResolveTemplate(expr, context);
      } else {
        try {
          const ast = exprParse(expr);
          value = exprEval(ast, context);
        } catch (parseErr) {
          console.warn(
            `[resolveInputs] input '${key}' is not a valid expression, treating as literal string: ${(parseErr as Error).message}`,
          );
          value = expr;
        }
      }
      resolved[key] = { value, rawExpression: expr };
    } catch (err) {
      if (err instanceof WorkflowError) throw err;
      throw new WorkflowError(
        `Failed to resolve input '${key}': ${(err as Error).message}`,
        "INVALID_EXPRESSION",
        { key, expression: expr },
      );
    }
  }
  return resolved;
}

// ── resolveInputs Tests ──

describe("resolveInputs", () => {
  test("single template preserves original type — number", () => {
    const result = resolveInputs(
      { count: "${{ params.count }}" },
      { params: { count: 42 } },
    );
    expect(result.count.value).toBe(42);
    expect(typeof result.count.value).toBe("number");
    expect(result.count.rawExpression).toBe("${{ params.count }}");
  });

  test("single template preserves boolean type", () => {
    const result = resolveInputs(
      { flag: "${{ params.flag }}" },
      { params: { flag: true } },
    );
    expect(result.flag.value).toBe(true);
    expect(typeof result.flag.value).toBe("boolean");
  });

  test("single template preserves object type", () => {
    const obj = { a: 1, b: "two" };
    const result = resolveInputs(
      { config: "${{ params.config }}" },
      { params: { config: obj } },
    );
    expect(result.config.value).toEqual(obj);
    expect(typeof result.config.value).toBe("object");
  });

  test("concatenation template result is always string", () => {
    const result = resolveInputs(
      { path: "${{ params.x }}/path" },
      { params: { x: "data" } },
    );
    expect(result.path.value).toBe("data/path");
    expect(typeof result.path.value).toBe("string");
  });

  test("concatenation template with number becomes string", () => {
    const result = resolveInputs(
      { label: "count_${{ params.n }}" },
      { params: { n: 10 } },
    );
    expect(result.label.value).toBe("count_10");
    expect(typeof result.label.value).toBe("string");
  });

  test("concatenation template with multiple expressions", () => {
    const result = resolveInputs(
      { path: "${{ params.dir }}/${{ params.file }}.fq.gz" },
      { params: { dir: "output", file: "sample1" } },
    );
    expect(result.path.value).toBe("output/sample1.fq.gz");
  });

  test("literal string without template syntax", () => {
    const result = resolveInputs(
      { title: "PE RNA-Seq Report" },
      { params: {} },
    );
    // "PE RNA-Seq Report" is not a valid expression (spaces, hyphens) so it falls through to literal string
    expect(result.title.value).toBe("PE RNA-Seq Report");
    expect(typeof result.title.value).toBe("string");
  });

  test("pure expression (no template) resolves with original type", () => {
    const result = resolveInputs(
      { count: "params.count" },
      { params: { count: 99 } },
    );
    expect(result.count.value).toBe(99);
    expect(typeof result.count.value).toBe("number");
  });

  test("pure expression with string concatenation operator", () => {
    const result = resolveInputs(
      { label: "'prefix_' + params.x" },
      { params: { x: "hello" } },
    );
    expect(result.label.value).toBe("prefix_hello");
  });

  test("WorkflowError is re-thrown as-is", () => {
    // Accessing an undefined root variable should trigger WorkflowError(UNDEFINED_VARIABLE)
    // which is then re-thrown directly (not wrapped)
    expect(() =>
      resolveInputs(
        { bad: "${{ unknownVar.field }}" },
        { params: {} },
      ),
    ).toThrow(WorkflowError);
  });

  test("WorkflowError preserves error code", () => {
    try {
      resolveInputs(
        { bad: "${{ unknownVar.field }}" },
        { params: {} },
      );
      throw new Error("Should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(WorkflowError);
      expect((err as WorkflowError).code).toBe("UNDEFINED_VARIABLE");
    }
  });

  test("multiple inputs resolved independently", () => {
    const result = resolveInputs(
      {
        name: "${{ params.name }}",
        count: "${{ params.count }}",
        path: "${{ params.dir }}/output",
        title: "My Report",
      },
      { params: { name: "Alice", count: 5, dir: "/data" } },
    );
    expect(result.name.value).toBe("Alice");
    expect(typeof result.name.value).toBe("string");
    expect(result.count.value).toBe(5);
    expect(typeof result.count.value).toBe("number");
    expect(result.path.value).toBe("/data/output");
    expect(typeof result.path.value).toBe("string");
    expect(result.title.value).toBe("My Report");
  });

  test("empty inputs returns empty object", () => {
    const result = resolveInputs({}, {});
    expect(result).toEqual({});
  });

  test("null params value preserved through single template", () => {
    const result = resolveInputs(
      { val: "${{ params.missing }}" },
      { params: {} },
    );
    // params.missing → member_access on null params returns null
    expect(result.val.value).toBeNull();
  });
});
