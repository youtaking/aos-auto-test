import { describe, test, expect } from "bun:test";

// ========== Pure function copies from packages/workflow-engine/src/parser/expression-parser.ts ==========
// Full inline copy: Lexer + Parser + Evaluator + resolveTemplate

// ---------- Types ----------

interface EvalContext {
  nodes?: Record<string, unknown>;
  params?: Record<string, unknown>;
  secrets?: Record<string, unknown>;
}

type ASTNode =
  | { kind: "literal"; value: unknown }
  | { kind: "identifier"; name: string }
  | { kind: "member_access"; object: ASTNode; property: string }
  | { kind: "index_access"; object: ASTNode; index: ASTNode }
  | { kind: "unary"; op: string; operand: ASTNode }
  | { kind: "binary"; op: string; left: ASTNode; right: ASTNode }
  | { kind: "ternary"; condition: ASTNode; consequent: ASTNode; alternate: ASTNode };

// ---------- Error ----------

class WorkflowError extends Error {
  readonly code: string;
  constructor(message: string, code: string) {
    super(message);
    this.code = code;
    this.name = "WorkflowError";
  }
}

// ---------- Constants ----------

const MAX_EXPR_LENGTH = 1024;
const MAX_ACCESS_DEPTH = 10;
const BLOCKED_KEYS = new Set(["__proto__", "constructor", "prototype"]);
const ALLOWED_ROOTS = new Set(["nodes", "params", "secrets"]);

// ---------- Type guard ----------

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

// ---------- Lexer ----------

enum TokenType {
  Ident,
  Number,
  String,
  Dot,
  LBracket,
  RBracket,
  LParen,
  RParen,
  Question,
  Colon,
  Bang,
  Op,
  EOF,
}

interface Token {
  type: TokenType;
  value: string;
}

class Lexer {
  private pos = 0;

  constructor(private readonly source: string) {}

  peek(): string {
    return this.pos < this.source.length ? this.source[this.pos] : "\0";
  }

  advance(): string {
    return this.source[this.pos++];
  }

  at(offset: number): string {
    const i = this.pos + offset;
    return i < this.source.length ? this.source[i] : "\0";
  }

  skipWhitespace(): void {
    while (this.pos < this.source.length && /\s/.test(this.source[this.pos])) {
      this.pos++;
    }
  }

  next(): Token {
    this.skipWhitespace();
    const ch = this.peek();

    if (ch === "\0") return { type: TokenType.EOF, value: "" };

    // Number
    if (/[0-9]/.test(ch) || (ch === "-" && /[0-9]/.test(this.at(1)))) {
      const start = this.pos;
      if (ch === "-") this.advance();
      while (/[0-9]/.test(this.peek())) this.advance();
      if (this.peek() === ".") {
        this.advance();
        while (/[0-9]/.test(this.peek())) this.advance();
      }
      return { type: TokenType.Number, value: this.source.slice(start, this.pos) };
    }

    // String literal
    if (ch === '"' || ch === "'") {
      return this.readString();
    }

    // Identifier
    if (/[a-zA-Z_$]/.test(ch)) {
      const start = this.pos;
      while (/[a-zA-Z0-9_$]/.test(this.peek())) this.advance();
      return { type: TokenType.Ident, value: this.source.slice(start, this.pos) };
    }

    this.advance();

    switch (ch) {
      case ".":
        return { type: TokenType.Dot, value: "." };
      case "[":
        return { type: TokenType.LBracket, value: "[" };
      case "]":
        return { type: TokenType.RBracket, value: "]" };
      case "(":
        return { type: TokenType.LParen, value: "(" };
      case ")":
        return { type: TokenType.RParen, value: ")" };
      case "?":
        return { type: TokenType.Question, value: "?" };
      case ":":
        return { type: TokenType.Colon, value: ":" };
      case "!":
        if (this.peek() === "=") {
          this.advance();
          return { type: TokenType.Op, value: "!=" };
        }
        return { type: TokenType.Bang, value: "!" };
      case "=":
        if (this.peek() === "=") {
          this.advance();
          return { type: TokenType.Op, value: "==" };
        }
        throw new WorkflowError(
          `Unexpected character: '${ch}'`,
          "INVALID_EXPRESSION",
        );
      case ">":
        if (this.peek() === "=") {
          this.advance();
          return { type: TokenType.Op, value: ">=" };
        }
        return { type: TokenType.Op, value: ">" };
      case "<":
        if (this.peek() === "=") {
          this.advance();
          return { type: TokenType.Op, value: "<=" };
        }
        return { type: TokenType.Op, value: "<" };
      case "&":
        if (this.peek() === "&") {
          this.advance();
          return { type: TokenType.Op, value: "&&" };
        }
        throw new WorkflowError(
          `Unexpected character: '${ch}'`,
          "INVALID_EXPRESSION",
        );
      case "|":
        if (this.peek() === "|") {
          this.advance();
          return { type: TokenType.Op, value: "||" };
        }
        throw new WorkflowError(
          `Unexpected character: '${ch}'`,
          "INVALID_EXPRESSION",
        );
      case "+":
        return { type: TokenType.Op, value: "+" };
      default:
        throw new WorkflowError(
          `Unexpected character: '${ch}'`,
          "INVALID_EXPRESSION",
        );
    }
  }

  private readString(): Token {
    const quote = this.advance();
    const start = this.pos;
    while (this.peek() !== quote && this.peek() !== "\0") {
      if (this.peek() === "\\") this.advance();
      this.advance();
    }
    if (this.peek() === "\0") {
      throw new WorkflowError("Unterminated string literal", "INVALID_EXPRESSION");
    }
    this.advance(); // closing quote
    return { type: TokenType.String, value: this.source.slice(start, this.pos - 1) };
  }
}

// ---------- Parser ----------

class Parser {
  private pos = 0;

  constructor(private readonly tokens: Token[]) {}

  peek(): Token {
    return this.tokens[this.pos] ?? { type: TokenType.EOF, value: "" };
  }

  advance(): Token {
    const tok = this.tokens[this.pos];
    this.pos++;
    return tok ?? { type: TokenType.EOF, value: "" };
  }

  expect(type: TokenType, value?: string): Token {
    const tok = this.peek();
    if (tok.type !== type || (value !== undefined && tok.value !== value)) {
      throw new WorkflowError(
        `Expected ${value ?? TokenType[type]} but got '${tok.value}'`,
        "INVALID_EXPRESSION",
      );
    }
    return this.advance();
  }

  parse(): ASTNode {
    const node = this.parseTernary();
    if (this.peek().type !== TokenType.EOF) {
      throw new WorkflowError(
        `Unexpected token after expression: '${this.peek().value}'`,
        "INVALID_EXPRESSION",
      );
    }
    return node;
  }

  private parseTernary(): ASTNode {
    const cond = this.parseOr();
    if (this.peek().type === TokenType.Question) {
      this.advance();
      const consequent = this.parseTernary();
      this.expect(TokenType.Colon);
      const alternate = this.parseTernary();
      return { kind: "ternary", condition: cond, consequent, alternate };
    }
    return cond;
  }

  private parseOr(): ASTNode {
    let left = this.parseAnd();
    while (this.peek().type === TokenType.Op && this.peek().value === "||") {
      this.advance();
      const right = this.parseAnd();
      left = { kind: "binary", op: "||", left, right };
    }
    return left;
  }

  private parseAnd(): ASTNode {
    let left = this.parseComparison();
    while (this.peek().type === TokenType.Op && this.peek().value === "&&") {
      this.advance();
      const right = this.parseComparison();
      left = { kind: "binary", op: "&&", left, right };
    }
    return left;
  }

  private parseComparison(): ASTNode {
    let left = this.parseConcat();
    const tok = this.peek();
    if (
      tok.type === TokenType.Op &&
      ["==", "!=", ">", "<", ">=", "<="].includes(tok.value)
    ) {
      this.advance();
      const right = this.parseConcat();
      left = { kind: "binary", op: tok.value, left, right };
    }
    return left;
  }

  private parseConcat(): ASTNode {
    let left = this.parseUnary();
    while (this.peek().type === TokenType.Op && this.peek().value === "+") {
      this.advance();
      const right = this.parseUnary();
      left = { kind: "binary", op: "+", left, right };
    }
    return left;
  }

  private parseUnary(): ASTNode {
    const tok = this.peek();
    if (tok.type === TokenType.Bang) {
      this.advance();
      const operand = this.parseUnary();
      return { kind: "unary", op: "!", operand };
    }
    return this.parsePostfix();
  }

  private parsePostfix(): ASTNode {
    let node = this.parsePrimary();

    for (;;) {
      const tok = this.peek();
      if (tok.type === TokenType.Dot) {
        this.advance();
        const prop = this.expect(TokenType.Ident);
        node = { kind: "member_access", object: node, property: prop.value };
      } else if (tok.type === TokenType.LBracket) {
        this.advance();
        const index = this.parseTernary();
        this.expect(TokenType.RBracket);
        node = { kind: "index_access", object: node, index };
      } else {
        break;
      }
    }

    return node;
  }

  private parsePrimary(): ASTNode {
    const tok = this.peek();

    if (tok.type === TokenType.Number) {
      this.advance();
      const v = Number(tok.value);
      return { kind: "literal", value: v };
    }

    if (tok.type === TokenType.String) {
      this.advance();
      return { kind: "literal", value: tok.value };
    }

    if (tok.type === TokenType.Ident) {
      if (tok.value === "null") {
        this.advance();
        return { kind: "literal", value: null };
      }
      if (tok.value === "true") {
        this.advance();
        return { kind: "literal", value: true };
      }
      if (tok.value === "false") {
        this.advance();
        return { kind: "literal", value: false };
      }
      this.advance();
      return { kind: "identifier", name: tok.value };
    }

    if (tok.type === TokenType.LParen) {
      this.advance();
      const inner = this.parseTernary();
      this.expect(TokenType.RParen);
      return inner;
    }

    throw new WorkflowError(
      `Unexpected token: '${tok.value}' (${TokenType[tok.type]})`,
      "INVALID_EXPRESSION",
    );
  }
}

// ---------- Exported functions ----------

function parseExpression(expr: string): ASTNode {
  if (expr.length > MAX_EXPR_LENGTH) {
    throw new WorkflowError(
      `Expression exceeds max length ${MAX_EXPR_LENGTH}`,
      "EXPRESSION_TOO_LONG",
    );
  }
  const lexer = new Lexer(expr);
  const tokens: Token[] = [];
  for (;;) {
    const tok = lexer.next();
    tokens.push(tok);
    if (tok.type === TokenType.EOF) break;
  }
  const parser = new Parser(tokens);
  return parser.parse();
}

function evaluateExpression(ast: ASTNode, context: EvalContext, depth = 0): unknown {
  if (depth > MAX_ACCESS_DEPTH) {
    throw new WorkflowError(
      `Expression access depth exceeds ${MAX_ACCESS_DEPTH}`,
      "EXPRESSION_TOO_DEEP",
    );
  }

  switch (ast.kind) {
    case "literal":
      return ast.value;

    case "identifier": {
      const name = ast.name;
      if (!ALLOWED_ROOTS.has(name)) {
        throw new WorkflowError(
          `Undefined variable: '${name}'`,
          "UNDEFINED_VARIABLE",
        );
      }
      if (name === "nodes") return context.nodes ?? null;
      if (name === "params") return context.params ?? null;
      if (name === "secrets") return context.secrets ?? null;
      return null;
    }

    case "member_access": {
      const obj = evaluateExpression(ast.object, context, depth + 1);
      if (BLOCKED_KEYS.has(ast.property)) {
        throw new WorkflowError(
          `Blocked property access: '${ast.property}'`,
          "UNDEFINED_VARIABLE",
        );
      }
      if (obj === null || obj === undefined) return null;
      if (isObject(obj)) return obj[ast.property] ?? null;
      return null;
    }

    case "index_access": {
      const obj = evaluateExpression(ast.object, context, depth + 1);
      const idx = evaluateExpression(ast.index, context, depth + 1);
      if (obj === null || obj === undefined) return null;
      if (Array.isArray(obj)) {
        if (typeof idx === "number")
          return (idx >= 0 && idx < obj.length ? obj[idx] : null) ?? null;
        return null;
      }
      if (isObject(obj) && typeof idx === "string") return obj[idx] ?? null;
      return null;
    }

    case "unary": {
      if (ast.op === "!") {
        const val = evaluateExpression(ast.operand, context, depth + 1);
        return !val;
      }
      throw new WorkflowError(
        `Unknown unary operator: '${ast.op}'`,
        "INVALID_EXPRESSION",
      );
    }

    case "binary": {
      // Short-circuit evaluation
      if (ast.op === "&&") {
        const left = evaluateExpression(ast.left, context, depth + 1);
        return left ? evaluateExpression(ast.right, context, depth + 1) : left;
      }
      if (ast.op === "||") {
        const left = evaluateExpression(ast.left, context, depth + 1);
        return left ? left : evaluateExpression(ast.right, context, depth + 1);
      }

      const left = evaluateExpression(ast.left, context, depth + 1);
      const right = evaluateExpression(ast.right, context, depth + 1);

      switch (ast.op) {
        case "==":
          return left === right;
        case "!=":
          return left !== right;
        case ">":
        case "<":
        case ">=":
        case "<=":
          if (left === null || right === null) return false;
          switch (ast.op) {
            case ">":
              return (left as number) > (right as number);
            case "<":
              return (left as number) < (right as number);
            case ">=":
              return (left as number) >= (right as number);
            case "<=":
              return (left as number) <= (right as number);
          }
          break;
        case "+":
          if (typeof left === "string" || typeof right === "string") {
            return String(left ?? "") + String(right ?? "");
          }
          return (left as number) + (right as number);
        default:
          throw new WorkflowError(
            `Unknown binary operator: '${ast.op}'`,
            "INVALID_EXPRESSION",
          );
      }
    }

    case "ternary": {
      const cond = evaluateExpression(ast.condition, context, depth + 1);
      return cond
        ? evaluateExpression(ast.consequent, context, depth + 1)
        : evaluateExpression(ast.alternate, context, depth + 1);
    }

    default: {
      throw new WorkflowError(`Unknown AST node kind`, "INVALID_EXPRESSION");
    }
  }
}

function stringifyTemplateValue(val: unknown): string {
  if (val === null || val === undefined) return "";
  if (typeof val === "string") return val;
  if (typeof val === "number" || typeof val === "boolean") return String(val);
  if (typeof val === "object") {
    const obj = val as Record<string, unknown>;
    if (typeof obj.simplified === "string") return obj.simplified;
    if (typeof obj.stdout === "string") return obj.stdout;
    return JSON.stringify(val);
  }
  return String(val);
}

function resolveTemplate(template: string, context: EvalContext): string {
  const result: string[] = [];
  let lastEnd = 0;

  for (let i = 0; i < template.length; i++) {
    if (
      template[i] === "$" &&
      template[i + 1] === "{" &&
      template[i + 2] === "{"
    ) {
      result.push(template.slice(lastEnd, i));
      let depth = 1;
      let j = i + 3;
      for (; j < template.length; j++) {
        if (template[j] === "}" && template[j + 1] === "}") {
          depth--;
          if (depth === 0) break;
          j++;
        }
        if (template[j] === "{" && template[j + 1] === "{") {
          depth++;
          j++;
        }
      }
      if (depth !== 0) {
        throw new WorkflowError(
          "Unterminated ${{ expression",
          "INVALID_EXPRESSION",
        );
      }
      const expr = template.slice(i + 3, j).trim();
      const ast = parseExpression(expr);
      const val = evaluateExpression(ast, context);
      result.push(
        val === null || val === undefined ? "" : stringifyTemplateValue(val),
      );
      lastEnd = j + 2;
      i = j + 1;
    }
  }

  result.push(template.slice(lastEnd));
  return result.join("");
}

// ========== Tests ==========

describe("parseExpression", () => {
  test("parses number literal", () => {
    const ast = parseExpression("42");
    expect(ast).toEqual({ kind: "literal", value: 42 });
  });

  test("parses negative number", () => {
    const ast = parseExpression("-3.14");
    expect(ast).toEqual({ kind: "literal", value: -3.14 });
  });

  test("parses float number", () => {
    const ast = parseExpression("3.14");
    expect(ast).toEqual({ kind: "literal", value: 3.14 });
  });

  test("parses string literal with double quotes", () => {
    const ast = parseExpression('"hello"');
    expect(ast).toEqual({ kind: "literal", value: "hello" });
  });

  test("parses string literal with single quotes", () => {
    const ast = parseExpression("'world'");
    expect(ast).toEqual({ kind: "literal", value: "world" });
  });

  test("parses null literal", () => {
    const ast = parseExpression("null");
    expect(ast).toEqual({ kind: "literal", value: null });
  });

  test("parses true literal", () => {
    const ast = parseExpression("true");
    expect(ast).toEqual({ kind: "literal", value: true });
  });

  test("parses false literal", () => {
    const ast = parseExpression("false");
    expect(ast).toEqual({ kind: "literal", value: false });
  });

  test("parses identifier", () => {
    const ast = parseExpression("nodes");
    expect(ast).toEqual({ kind: "identifier", name: "nodes" });
  });

  test("parses member access", () => {
    const ast = parseExpression("nodes.output");
    expect(ast.kind).toBe("member_access");
    if (ast.kind === "member_access") {
      expect(ast.property).toBe("output");
      expect(ast.object).toEqual({ kind: "identifier", name: "nodes" });
    }
  });

  test("parses chained member access", () => {
    const ast = parseExpression("nodes.a.b.c");
    expect(ast.kind).toBe("member_access");
    if (ast.kind === "member_access") {
      expect(ast.property).toBe("c");
      expect(ast.object.kind).toBe("member_access");
    }
  });

  test("parses index access", () => {
    const ast = parseExpression('nodes["key"]');
    expect(ast.kind).toBe("index_access");
    if (ast.kind === "index_access") {
      expect(ast.object).toEqual({ kind: "identifier", name: "nodes" });
      expect(ast.index).toEqual({ kind: "literal", value: "key" });
    }
  });

  test("parses numeric index access", () => {
    const ast = parseExpression("nodes[0]");
    expect(ast.kind).toBe("index_access");
    if (ast.kind === "index_access") {
      expect(ast.index).toEqual({ kind: "literal", value: 0 });
    }
  });

  test("parses binary operators", () => {
    const ast = parseExpression("1 == 1");
    expect(ast.kind).toBe("binary");
    if (ast.kind === "binary") {
      expect(ast.op).toBe("==");
    }
  });

  test("parses unary !", () => {
    const ast = parseExpression("!true");
    expect(ast.kind).toBe("unary");
    if (ast.kind === "unary") {
      expect(ast.op).toBe("!");
      expect(ast.operand).toEqual({ kind: "literal", value: true });
    }
  });

  test("parses ternary expression", () => {
    const ast = parseExpression("true ? 1 : 2");
    expect(ast.kind).toBe("ternary");
    if (ast.kind === "ternary") {
      expect(ast.condition).toEqual({ kind: "literal", value: true });
      expect(ast.consequent).toEqual({ kind: "literal", value: 1 });
      expect(ast.alternate).toEqual({ kind: "literal", value: 2 });
    }
  });

  test("parses nested parenthesized expression", () => {
    const ast = parseExpression("(1 + 2)");
    expect(ast.kind).toBe("binary");
    if (ast.kind === "binary") {
      expect(ast.op).toBe("+");
    }
  });

  test("throws for expression exceeding max length", () => {
    const longExpr = "a".repeat(MAX_EXPR_LENGTH + 1);
    expect(() => parseExpression(longExpr)).toThrow("Expression exceeds max length");
  });

  test("throws for invalid syntax", () => {
    expect(() => parseExpression("!!!")).toThrow("Unexpected");
  });

  test("throws for unterminated string", () => {
    expect(() => parseExpression('"unterminated')).toThrow("Unterminated string literal");
  });

  test("parses && operator", () => {
    const ast = parseExpression("true && false");
    expect(ast.kind).toBe("binary");
    if (ast.kind === "binary") {
      expect(ast.op).toBe("&&");
    }
  });

  test("parses || operator", () => {
    const ast = parseExpression("true || false");
    expect(ast.kind).toBe("binary");
    if (ast.kind === "binary") {
      expect(ast.op).toBe("||");
    }
  });

  test("parses comparison operators", () => {
    for (const op of [">", "<", ">=", "<=", "==", "!="]) {
      const ast = parseExpression(`1 ${op} 2`);
      expect(ast.kind).toBe("binary");
      if (ast.kind === "binary") {
        expect(ast.op).toBe(op);
      }
    }
  });

  test("parses string concatenation with +", () => {
    const ast = parseExpression('"hello" + "world"');
    expect(ast.kind).toBe("binary");
    if (ast.kind === "binary") {
      expect(ast.op).toBe("+");
    }
  });
});

describe("evaluateExpression", () => {
  test("evaluates literal number", () => {
    const ast = parseExpression("42");
    expect(evaluateExpression(ast, {})).toBe(42);
  });

  test("evaluates literal string", () => {
    const ast = parseExpression('"hello"');
    expect(evaluateExpression(ast, {})).toBe("hello");
  });

  test("evaluates literal null", () => {
    const ast = parseExpression("null");
    expect(evaluateExpression(ast, {})).toBeNull();
  });

  test("evaluates literal true", () => {
    const ast = parseExpression("true");
    expect(evaluateExpression(ast, {})).toBe(true);
  });

  test("evaluates literal false", () => {
    const ast = parseExpression("false");
    expect(evaluateExpression(ast, {})).toBe(false);
  });

  test("resolves nodes identifier", () => {
    const ast = parseExpression("nodes");
    const ctx = { nodes: { step1: { output: "data" } } };
    expect(evaluateExpression(ast, ctx)).toEqual({ step1: { output: "data" } });
  });

  test("resolves params identifier", () => {
    const ast = parseExpression("params");
    const ctx = { params: { key: "value" } };
    expect(evaluateExpression(ast, ctx)).toEqual({ key: "value" });
  });

  test("resolves secrets identifier", () => {
    const ast = parseExpression("secrets");
    const ctx = { secrets: { API_KEY: "secret123" } };
    expect(evaluateExpression(ast, ctx)).toEqual({ API_KEY: "secret123" });
  });

  test("returns null for missing nodes", () => {
    const ast = parseExpression("nodes");
    expect(evaluateExpression(ast, {})).toBeNull();
  });

  test("returns null for missing params", () => {
    const ast = parseExpression("params");
    expect(evaluateExpression(ast, {})).toBeNull();
  });

  test("throws for undefined variable", () => {
    const ast = parseExpression("unknown");
    expect(() => evaluateExpression(ast, {})).toThrow("Undefined variable");
  });

  test("evaluates member access", () => {
    const ast = parseExpression("nodes.step1");
    const ctx = { nodes: { step1: { output: "data" } } };
    expect(evaluateExpression(ast, ctx)).toEqual({ output: "data" });
  });

  test("evaluates chained member access", () => {
    const ast = parseExpression("nodes.step1.output");
    const ctx = { nodes: { step1: { output: "result_value" } } };
    expect(evaluateExpression(ast, ctx)).toBe("result_value");
  });

  test("blocks __proto__ access", () => {
    const ast = parseExpression("params.__proto__");
    const ctx = { params: { key: "value" } };
    expect(() => evaluateExpression(ast, ctx)).toThrow("Blocked property access");
  });

  test("blocks constructor access", () => {
    const ast = parseExpression("params.constructor");
    const ctx = { params: { key: "value" } };
    expect(() => evaluateExpression(ast, ctx)).toThrow("Blocked property access");
  });

  test("blocks prototype access", () => {
    const ast = parseExpression("params.prototype");
    const ctx = { params: { key: "value" } };
    expect(() => evaluateExpression(ast, ctx)).toThrow("Blocked property access");
  });

  test("returns null for member access on null", () => {
    const ast = parseExpression("nodes.nonexistent");
    expect(evaluateExpression(ast, {})).toBeNull();
  });

  test("evaluates index access on array", () => {
    const ast = parseExpression("params.items[1]");
    const ctx = { params: { items: ["a", "b", "c"] } };
    expect(evaluateExpression(ast, ctx)).toBe("b");
  });

  test("evaluates index access on object", () => {
    const ast = parseExpression('params.map["key"]');
    const ctx = { params: { map: { key: "value" } } };
    expect(evaluateExpression(ast, ctx)).toBe("value");
  });

  test("returns null for out-of-bounds array index", () => {
    const ast = parseExpression("params.items[99]");
    const ctx = { params: { items: ["a"] } };
    expect(evaluateExpression(ast, ctx)).toBeNull();
  });

  test("returns null for index access on null", () => {
    const ast = parseExpression("nodes.missing[0]");
    expect(evaluateExpression(ast, {})).toBeNull();
  });

  test("evaluates == operator", () => {
    const ast = parseExpression("1 == 1");
    expect(evaluateExpression(ast, {})).toBe(true);
  });

  test("evaluates != operator", () => {
    const ast = parseExpression("1 != 2");
    expect(evaluateExpression(ast, {})).toBe(true);
  });

  test("evaluates > operator", () => {
    const ast = parseExpression("2 > 1");
    expect(evaluateExpression(ast, {})).toBe(true);
  });

  test("evaluates < operator", () => {
    const ast = parseExpression("1 < 2");
    expect(evaluateExpression(ast, {})).toBe(true);
  });

  test("evaluates >= operator", () => {
    expect(evaluateExpression(parseExpression("2 >= 2"), {})).toBe(true);
    expect(evaluateExpression(parseExpression("3 >= 2"), {})).toBe(true);
    expect(evaluateExpression(parseExpression("1 >= 2"), {})).toBe(false);
  });

  test("evaluates <= operator", () => {
    expect(evaluateExpression(parseExpression("2 <= 2"), {})).toBe(true);
    expect(evaluateExpression(parseExpression("1 <= 2"), {})).toBe(true);
    expect(evaluateExpression(parseExpression("3 <= 2"), {})).toBe(false);
  });

  test("comparison with null returns false", () => {
    const ast = parseExpression("params.x > 0");
    expect(evaluateExpression(ast, {})).toBe(false);
  });

  test("evaluates numeric addition", () => {
    const ast = parseExpression("1 + 2");
    expect(evaluateExpression(ast, {})).toBe(3);
  });

  test("evaluates string concatenation", () => {
    const ast = parseExpression('"hello" + " " + "world"');
    expect(evaluateExpression(ast, {})).toBe("hello world");
  });

  test("evaluates string + null concatenation", () => {
    const ast = parseExpression('"prefix" + params.missing');
    expect(evaluateExpression(ast, {})).toBe("prefix");
  });

  test("evaluates ! operator", () => {
    expect(evaluateExpression(parseExpression("!true"), {})).toBe(false);
    expect(evaluateExpression(parseExpression("!false"), {})).toBe(true);
    expect(evaluateExpression(parseExpression("!null"), {})).toBe(true);
  });

  test("evaluates && short-circuit", () => {
    // If left is falsy, right is not evaluated
    const ast = parseExpression("null && params.undefined_var");
    expect(evaluateExpression(ast, {})).toBeNull();
  });

  test("evaluates && with truthy left", () => {
    const ast = parseExpression("true && 42");
    expect(evaluateExpression(ast, {})).toBe(42);
  });

  test("evaluates || short-circuit", () => {
    // If left is truthy, right is not evaluated
    const ast = parseExpression("42 || params.undefined_var");
    expect(evaluateExpression(ast, {})).toBe(42);
  });

  test("evaluates || with falsy left", () => {
    const ast = parseExpression("null || 42");
    expect(evaluateExpression(ast, {})).toBe(42);
  });

  test("evaluates ternary true branch", () => {
    const ast = parseExpression("true ? 1 : 2");
    expect(evaluateExpression(ast, {})).toBe(1);
  });

  test("evaluates ternary false branch", () => {
    const ast = parseExpression("false ? 1 : 2");
    expect(evaluateExpression(ast, {})).toBe(2);
  });

  test("evaluates ternary with expression condition", () => {
    const ast = parseExpression("1 == 1 ? 'yes' : 'no'");
    expect(evaluateExpression(ast, {})).toBe("yes");
  });

  test("throws on depth limit exceeded", () => {
    // Create a deeply nested member access that exceeds MAX_ACCESS_DEPTH
    const ast = parseExpression("nodes.a.b.c.d.e.f.g.h.i.j.k");
    const ctx = {
      nodes: {
        a: { b: { c: { d: { e: { f: { g: { h: { i: { j: { k: "deep" } } } } } } } } } },
      },
    };
    expect(() => evaluateExpression(ast, ctx)).toThrow("Expression access depth exceeds");
  });

  test("evaluates complex nested expression", () => {
    const ast = parseExpression("nodes.step1.output == 'success' ? nodes.step2.output : 'failed'");
    const ctx = {
      nodes: {
        step1: { output: "success" },
        step2: { output: "result-data" },
      },
    };
    expect(evaluateExpression(ast, ctx)).toBe("result-data");
  });

  test("binary + 混合 number 和 string 触发字符串强制转换", () => {
    // 源码逻辑：if (typeof left === "string" || typeof right === "string") → String(left) + String(right)
    const ast1 = parseExpression('1 + "hello"');
    expect(evaluateExpression(ast1, {})).toBe("1hello");

    const ast2 = parseExpression('"hello" + 1');
    expect(evaluateExpression(ast2, {})).toBe("hello1");

    // number + string 也是字符串拼接
    const ast3 = parseExpression('42 + " items"');
    expect(evaluateExpression(ast3, {})).toBe("42 items");
  });

  test("负数组索引返回 null", () => {
    // 源码逻辑：idx >= 0 && idx < obj.length → false when idx < 0 → returns null
    const ast = parseExpression("params.items[-1]");
    const ctx = { params: { items: ["a", "b", "c"] } };
    expect(evaluateExpression(ast, ctx)).toBeNull();

    const ast2 = parseExpression("params.items[-100]");
    expect(evaluateExpression(ast2, ctx)).toBeNull();
  });
});

describe("resolveTemplate", () => {
  test("returns plain text unchanged", () => {
    const result = resolveTemplate("Hello, world!", {});
    expect(result).toBe("Hello, world!");
  });

  test("resolves single expression", () => {
    const result = resolveTemplate("${{ params.name }}", {
      params: { name: "Alice" },
    });
    expect(result).toBe("Alice");
  });

  test("resolves multiple expressions", () => {
    const result = resolveTemplate("Hello ${{ params.first }} ${{ params.last }}!", {
      params: { first: "John", last: "Doe" },
    });
    expect(result).toBe("Hello John Doe!");
  });

  test("resolves nested member access", () => {
    const result = resolveTemplate("Output: ${{ nodes.step1.output.result }}", {
      nodes: { step1: { output: { result: "done" } } },
    });
    expect(result).toBe("Output: done");
  });

  test("null becomes empty string", () => {
    const result = resolveTemplate("Value: ${{ nodes.missing }}end", {});
    expect(result).toBe("Value: end");
  });

  test("undefined becomes empty string", () => {
    const result = resolveTemplate("Before${{ params.nokey }}After", {
      params: {},
    });
    expect(result).toBe("BeforeAfter");
  });

  test("number becomes string", () => {
    const result = resolveTemplate("Count: ${{ params.count }}", {
      params: { count: 42 },
    });
    expect(result).toBe("Count: 42");
  });

  test("boolean becomes string", () => {
    const result = resolveTemplate("Flag: ${{ params.flag }}", {
      params: { flag: true },
    });
    expect(result).toBe("Flag: true");
  });

  test("object with simplified field uses simplified", () => {
    const result = resolveTemplate("${{ nodes.agent.output }}", {
      nodes: { agent: { output: { simplified: "Agent said hello", raw: "..." } } },
    });
    expect(result).toBe("Agent said hello");
  });

  test("object with stdout field uses stdout", () => {
    const result = resolveTemplate("${{ nodes.shell.output }}", {
      nodes: { shell: { output: { stdout: "file1.txt\nfile2.txt" } } },
    });
    expect(result).toBe("file1.txt\nfile2.txt");
  });

  test("object without simplified/stdout uses JSON.stringify", () => {
    const result = resolveTemplate("${{ nodes.step.output }}", {
      nodes: { step: { output: { key: "val" } } },
    });
    expect(result).toBe('{"key":"val"}');
  });

  test("throws for unterminated expression", () => {
    expect(() => resolveTemplate("${{ params.name", {})).toThrow(
      "Unterminated ${{ expression",
    );
  });

  test("resolves ternary in template", () => {
    const result = resolveTemplate(
      "${{ params.flag == true ? 'yes' : 'no' }}",
      { params: { flag: true } },
    );
    expect(result).toBe("yes");
  });

  test("resolves expression with whitespace", () => {
    const result = resolveTemplate("${{   params.x   }}", {
      params: { x: "trimmed" },
    });
    expect(result).toBe("trimmed");
  });

  test("handles template with no expressions", () => {
    expect(resolveTemplate("no expressions here", {})).toBe("no expressions here");
  });

  test("handles empty template", () => {
    expect(resolveTemplate("", {})).toBe("");
  });

  test("handles adjacent expressions", () => {
    const result = resolveTemplate("${{ params.a }}${{ params.b }}", {
      params: { a: "X", b: "Y" },
    });
    expect(result).toBe("XY");
  });

  test("handles string concatenation in template", () => {
    const result = resolveTemplate("${{ params.a + params.b }}", {
      params: { a: "hello", b: "world" },
    });
    expect(result).toBe("helloworld");
  });
});
