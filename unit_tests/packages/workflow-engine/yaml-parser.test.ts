// yaml-parser.test.ts — YAML workflow 解析器测试
// 测试目标：parseWorkflowYaml 的校验逻辑（schema_version、name、nodes、各类节点必填字段）
// 业务意图：确保 workflow YAML 解析严格校验，非法输入准确报错
// 策略：因无法导入 yaml 包，提取验证逻辑为 validateAndBuildWorkflow(doc)，用 JS 对象模拟解析结果

import { describe, test, expect } from "bun:test";

// ========== Pure function copies from packages/workflow-engine/src/parser/yaml-parser.ts ==========

// ---------- Types (inline) ----------

interface ParamDef {
  type?: "string" | "number" | "boolean" | "object";
  default?: unknown;
  required?: boolean;
  group?: string;
}

type NodeType =
  | "shell"
  | "python"
  | "agent"
  | "api"
  | "audit"
  | "workflow"
  | "loop"
  | "transform"
  | "custom"
  | "end";

interface BaseNodeDef {
  id: string;
  type: NodeType;
  depends_on?: string[];
  condition?: string;
  timeout?: number;
  env?: Record<string, string>;
  outputs?: Record<string, { pattern: string; type: "file" | "file-list" | "dir" }>;
}

interface ShellNodeDef extends BaseNodeDef {
  type: "shell";
  command: string | string[];
  cwd?: string;
  inputs?: Record<string, string>;
}

interface PythonNodeDef extends BaseNodeDef {
  type: "python";
  code: string;
  requirements?: string[];
  cwd?: string;
  inputs?: Record<string, string>;
}

interface AgentNodeDef extends BaseNodeDef {
  type: "agent";
  prompt: string;
  agent: string;
  output_messages?: number;
}

interface ApiNodeDef extends BaseNodeDef {
  type: "api";
  url: string;
  method?: "GET" | "POST" | "PUT" | "DELETE";
  headers?: Record<string, string>;
  body?: string;
}

interface AuditNodeDef extends BaseNodeDef {
  type: "audit";
  display_data?: unknown;
  expires_in?: number;
}

interface SubWorkflowNodeDef extends BaseNodeDef {
  type: "workflow";
  ref: string;
  params?: Record<string, unknown>;
  ignore_errors?: boolean;
}

interface LoopBody {
  nodes: NodeDef[];
}

interface LoopNodeDef extends BaseNodeDef {
  type: "loop";
  condition: string;
  max_iterations: number;
  body: LoopBody;
}

interface TransformNodeDef extends BaseNodeDef {
  type: "transform";
  inputs?: Record<string, string>;
  output: Record<string, string>;
}

interface CustomNodeDef extends BaseNodeDef {
  type: "custom";
  tool: string;
  inputs?: Record<string, string>;
  slurm?: {
    partition?: string;
    cores?: number;
    nodes?: number;
    memory?: string;
    walltime?: string;
    modules?: string[];
    jobName?: string;
    extraSBATCH?: string[];
  };
  script?: {
    content: string;
    env?: Record<string, string>;
  };
  foreach?: string;
  maxConcurrent?: number;
  continueOnError?: boolean;
}

interface EndNodeDef {
  type: "end";
  id: string;
  depends_on?: string[];
  condition?: string;
  timeout?: number;
  inputs?: Record<string, string>;
  outputs?: Record<string, { pattern: string; type: "file" | "file-list" | "dir" }>;
  env?: Record<string, string>;
}

type NodeDef =
  | ShellNodeDef
  | PythonNodeDef
  | AgentNodeDef
  | ApiNodeDef
  | AuditNodeDef
  | SubWorkflowNodeDef
  | LoopNodeDef
  | TransformNodeDef
  | CustomNodeDef
  | EndNodeDef;

interface WorkflowDef {
  schema_version: string;
  name: string;
  description?: string;
  params?: Record<string, ParamDef>;
  secrets?: string[];
  timeout?: number;
  nodes: NodeDef[];
  _startNodeId?: string;
  _baseDir?: string;
}

// ---------- Error classes (inline) ----------

enum WorkflowErrorCode {
  INVALID_YAML = "INVALID_YAML",
}

class WorkflowError extends Error {
  readonly code: WorkflowErrorCode;
  readonly details?: Record<string, unknown>;
  constructor(message: string, code: WorkflowErrorCode, details?: Record<string, unknown>) {
    super(message);
    this.name = "WorkflowError";
    this.code = code;
    this.details = details;
  }
}

// ---------- Constants ----------

const VALID_NODE_TYPES: NodeType[] = [
  "shell", "python", "agent", "api", "audit", "workflow", "loop", "transform", "custom", "end",
];

// ---------- Helper functions (copied) ----------

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function parseOutputs(raw: unknown): Record<string, { pattern: string; type: "file" | "file-list" | "dir" }> {
  if (!isRecord(raw)) return {};
  const result: Record<string, { pattern: string; type: "file" | "file-list" | "dir" }> = {};
  for (const [key, val] of Object.entries(raw)) {
    if (!isRecord(val)) {
      throw new WorkflowError(
        `outputs.${key}: must be a mapping with 'pattern' and 'type'`,
        WorkflowErrorCode.INVALID_YAML,
      );
    }
    const pattern = typeof val.pattern === "string" ? val.pattern : "";
    const type =
      typeof val.type === "string" && ["file", "file-list", "dir"].includes(val.type as string)
        ? (val.type as "file" | "file-list" | "dir")
        : "file";
    result[key] = { pattern, type };
  }
  return result;
}

function parseSlurmConfig(raw: unknown): CustomNodeDef["slurm"] {
  if (!isRecord(raw)) return;
  const result: NonNullable<CustomNodeDef["slurm"]> = {};

  if (typeof raw.partition === "string") result.partition = raw.partition;
  if (typeof raw.cores === "number") {
    result.cores = raw.cores;
  } else if (typeof raw.cores === "string" && raw.cores.trim() !== "") {
    const parsed = Number.parseInt(raw.cores as string, 10);
    if (!Number.isNaN(parsed)) result.cores = parsed;
  }
  if (typeof raw.nodes === "number") result.nodes = raw.nodes;
  if (typeof raw.memory === "string") result.memory = raw.memory;
  if (typeof raw.walltime === "string") result.walltime = raw.walltime;
  if (Array.isArray(raw.modules)) {
    result.modules = raw.modules.filter((m): m is string => typeof m === "string");
  }
  if (typeof raw.jobName === "string") result.jobName = raw.jobName;
  if (Array.isArray(raw.extraSBATCH)) {
    result.extraSBATCH = raw.extraSBATCH.filter((m): m is string => typeof m === "string");
  }

  return Object.keys(result).length > 0 ? result : undefined;
}

function parseScriptConfig(raw: unknown, nodeId: string): CustomNodeDef["script"] {
  if (raw === undefined || raw === null) return;
  if (!isRecord(raw)) {
    throw new WorkflowError(
      `nodes (${nodeId}): 'script' must be a mapping with 'content' and optional 'env'`,
      WorkflowErrorCode.INVALID_YAML,
    );
  }

  if (typeof raw.content !== "string" || !(raw.content as string).trim()) {
    throw new WorkflowError(
      `nodes (${nodeId}): 'script.content' is required and must be a non-empty string`,
      WorkflowErrorCode.INVALID_YAML,
    );
  }
  const result: NonNullable<CustomNodeDef["script"]> = { content: raw.content as string };

  if (raw.env !== undefined && raw.env !== null) {
    if (!isRecord(raw.env)) {
      throw new WorkflowError(
        `nodes (${nodeId}): 'script.env' must be a mapping of string -> string`,
        WorkflowErrorCode.INVALID_YAML,
      );
    }
    const env: Record<string, string> = {};
    for (const [k, v] of Object.entries(raw.env)) {
      if (typeof v !== "string") {
        continue;
      }
      env[k] = v;
    }
    if (Object.keys(env).length > 0) result.env = env;
  }

  return result;
}

interface CustomNodeRegistry {
  get(name: string): { name: string; kind: string; produces: string[] } | undefined;
}

interface ParseOptions {
  customRegistry?: CustomNodeRegistry;
}

function parseNode(raw: unknown, index: number, opts?: ParseOptions): NodeDef {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new WorkflowError(`nodes[${index}] must be a mapping`, WorkflowErrorCode.INVALID_YAML);
  }

  const n = raw as Record<string, unknown>;

  if (typeof n.id !== "string" || !n.id.trim()) {
    throw new WorkflowError(`nodes[${index}]: missing or empty 'id'`, WorkflowErrorCode.INVALID_YAML);
  }

  if (typeof n.type !== "string" || !VALID_NODE_TYPES.includes(n.type as NodeType)) {
    throw new WorkflowError(
      `nodes[${index}] (${n.id}): invalid type '${n.type}', must be one of: ${VALID_NODE_TYPES.join(", ")}`,
      WorkflowErrorCode.INVALID_YAML,
    );
  }

  const type = n.type as NodeType;
  const base = {
    id: n.id as string,
    type,
    depends_on: Array.isArray(n.depends_on) ? (n.depends_on as string[]) : undefined,
    condition: typeof n.condition === "string" ? n.condition : undefined,
    timeout: typeof n.timeout === "number" ? n.timeout : undefined,
    env: isRecord(n.env) ? (n.env as Record<string, string>) : undefined,
    outputs: parseOutputs(n.outputs),
  };

  switch (type) {
    case "shell": {
      if (!("command" in n)) {
        throw new WorkflowError(
          `nodes[${index}] (${n.id}): shell node requires 'command'`,
          WorkflowErrorCode.INVALID_YAML,
        );
      }
      return {
        ...base,
        type: "shell",
        command: n.command as string | string[],
        cwd: typeof n.cwd === "string" ? n.cwd : undefined,
        inputs: isRecord(n.inputs) ? (n.inputs as Record<string, string>) : undefined,
      };
    }
    case "python": {
      if (!("code" in n)) {
        throw new WorkflowError(
          `nodes[${index}] (${n.id}): python node requires 'code'`,
          WorkflowErrorCode.INVALID_YAML,
        );
      }
      return {
        ...base,
        type: "python",
        code: n.code as string,
        requirements: Array.isArray(n.requirements) ? (n.requirements as string[]) : undefined,
        cwd: typeof n.cwd === "string" ? n.cwd : undefined,
        inputs: isRecord(n.inputs) ? (n.inputs as Record<string, string>) : undefined,
      };
    }
    case "agent": {
      if (!("prompt" in n)) {
        throw new WorkflowError(
          `nodes[${index}] (${n.id}): agent node requires 'prompt'`,
          WorkflowErrorCode.INVALID_YAML,
        );
      }
      if (!("agent" in n) || typeof n.agent !== "string" || !n.agent) {
        throw new WorkflowError(
          `nodes[${index}] (${n.id}): agent node requires 'agent' (environment name)`,
          WorkflowErrorCode.INVALID_YAML,
        );
      }
      return {
        ...base,
        type: "agent",
        prompt: n.prompt as string,
        agent: n.agent as string,
        output_messages: typeof n.output_messages === "number" ? n.output_messages : undefined,
      };
    }
    case "api": {
      if (!("url" in n)) {
        throw new WorkflowError(`nodes[${index}] (${n.id}): api node requires 'url'`, WorkflowErrorCode.INVALID_YAML);
      }
      return {
        ...base,
        type: "api",
        url: n.url as string,
        method: typeof n.method === "string" ? (n.method as "GET" | "POST" | "PUT" | "DELETE") : undefined,
        headers: isRecord(n.headers) ? (n.headers as Record<string, string>) : undefined,
        body: typeof n.body === "string" ? n.body : undefined,
      };
    }
    case "audit":
      return {
        ...base,
        type: "audit",
        display_data: n.display_data,
        expires_in: typeof n.expires_in === "number" ? n.expires_in : undefined,
      };
    case "workflow": {
      if (!("ref" in n)) {
        throw new WorkflowError(
          `nodes[${index}] (${n.id}): workflow node requires 'ref'`,
          WorkflowErrorCode.INVALID_YAML,
        );
      }
      return {
        ...base,
        type: "workflow",
        ref: n.ref as string,
        params: isRecord(n.params) ? (n.params as Record<string, unknown>) : undefined,
        ignore_errors: typeof n.ignore_errors === "boolean" ? n.ignore_errors : undefined,
      };
    }
    case "loop": {
      if (!("condition" in n)) {
        throw new WorkflowError(
          `nodes[${index}] (${n.id}): loop node requires 'condition'`,
          WorkflowErrorCode.INVALID_YAML,
        );
      }
      if (!("max_iterations" in n) || typeof n.max_iterations !== "number") {
        throw new WorkflowError(
          `nodes[${index}] (${n.id}): loop node requires 'max_iterations' (number)`,
          WorkflowErrorCode.INVALID_YAML,
        );
      }
      if (!("body" in n) || !isRecord(n.body) || !Array.isArray((n.body as Record<string, unknown>).nodes)) {
        throw new WorkflowError(
          `nodes[${index}] (${n.id}): loop node requires 'body.nodes' (array)`,
          WorkflowErrorCode.INVALID_YAML,
        );
      }
      const bodyNodes = (n.body as Record<string, unknown>).nodes as unknown[];
      return {
        ...base,
        type: "loop",
        condition: n.condition as string,
        max_iterations: n.max_iterations as number,
        body: {
          nodes: bodyNodes.map((bn, bi) => parseNode(bn, bi)),
        },
      };
    }
    case "transform": {
      if (!("output" in n) || !isRecord(n.output) || Object.keys(n.output as Record<string, unknown>).length === 0) {
        throw new WorkflowError(
          `nodes[${index}] (${n.id}): transform node requires non-empty 'output' mapping`,
          WorkflowErrorCode.INVALID_YAML,
        );
      }
      return {
        ...base,
        type: "transform",
        inputs: isRecord(n.inputs) ? (n.inputs as Record<string, string>) : undefined,
        output: n.output as Record<string, string>,
      };
    }
    case "custom": {
      if (!("tool" in n) || typeof n.tool !== "string" || !n.tool.trim()) {
        throw new WorkflowError(
          `nodes[${index}] (${n.id}): custom node requires 'tool'`,
          WorkflowErrorCode.INVALID_YAML,
        );
      }
      const registry = opts?.customRegistry;
      const toolDef = registry?.get(n.tool as string);
      if (registry && !toolDef) {
        throw new WorkflowError(
          `nodes[${index}] (${n.id}): custom tool '${n.tool}' not registered`,
          WorkflowErrorCode.INVALID_YAML,
        );
      }
      if (!n.outputs || !isRecord(n.outputs)) {
        throw new WorkflowError(
          `nodes[${index}] (${n.id}): custom node requires 'outputs' mapping`,
          WorkflowErrorCode.INVALID_YAML,
        );
      }
      if (toolDef) {
        const allowsAnyOutput = toolDef.produces.includes("*");
        if (!allowsAnyOutput) {
          const producesSet = new Set(toolDef.produces);
          for (const key of Object.keys(base.outputs ?? {})) {
            if (!producesSet.has(key)) {
              throw new WorkflowError(
                `nodes[${index}] (${n.id}): output '${key}' not declared in tool '${n.tool}' produces list [${toolDef.produces.join(", ")}]`,
                WorkflowErrorCode.INVALID_YAML,
              );
            }
          }
        }
      }
      const isSlurmTool = toolDef?.kind === "slurm";

      if (isSlurmTool) {
        if (n.script === undefined || n.script === null) {
          throw new WorkflowError(
            `nodes[${index}] (${n.id}): slurm tool '${n.tool}' requires 'script.content'`,
            WorkflowErrorCode.INVALID_YAML,
          );
        }
      } else if (n.script !== undefined && n.script !== null) {
        throw new WorkflowError(
          `nodes[${index}] (${n.id}): non-slurm tool '${n.tool}' does not support 'script' field`,
          WorkflowErrorCode.INVALID_YAML,
        );
      }
      return {
        ...base,
        type: "custom",
        tool: n.tool as string,
        inputs: isRecord(n.inputs) ? (n.inputs as Record<string, string>) : undefined,
        slurm: parseSlurmConfig(n.slurm),
        script: parseScriptConfig(n.script, n.id as string),
        foreach: typeof n.foreach === "string" ? n.foreach : undefined,
        maxConcurrent: typeof n.maxConcurrent === "number" ? n.maxConcurrent : undefined,
        continueOnError: typeof n.continueOnError === "boolean" ? n.continueOnError : undefined,
      };
    }
    case "end":
      return {
        ...base,
        type: "end",
        inputs: isRecord(n.inputs) ? (n.inputs as Record<string, string>) : undefined,
      } as EndNodeDef;
  }
}

/**
 * Extracted validation+build logic from parseWorkflowYaml.
 * Takes a pre-parsed JS object (simulating yaml.parse output).
 */
function validateAndBuildWorkflow(doc: unknown, baseDir?: string, opts?: ParseOptions): WorkflowDef {
  if (!doc || typeof doc !== "object" || Array.isArray(doc)) {
    throw new WorkflowError("YAML root must be a mapping", WorkflowErrorCode.INVALID_YAML);
  }

  const raw = doc as Record<string, unknown>;

  if ("kind" in raw && "metadata" in raw && "spec" in raw) {
    throw new WorkflowError(
      "Detected acpx-g format YAML — only schema_version format is supported",
      WorkflowErrorCode.INVALID_YAML,
    );
  }

  if (!("schema_version" in raw)) {
    throw new WorkflowError("Missing required field: 'schema_version'", WorkflowErrorCode.INVALID_YAML);
  }
  const schemaVersion = String(raw.schema_version);
  if (schemaVersion !== "1") {
    throw new WorkflowError(
      `Unsupported schema_version: '${schemaVersion}', expected '1'`,
      WorkflowErrorCode.INVALID_YAML,
    );
  }

  if (!("name" in raw) || typeof raw.name !== "string" || !raw.name.trim()) {
    throw new WorkflowError("Missing required field: 'name'", WorkflowErrorCode.INVALID_YAML);
  }

  if ("params" in raw && raw.params) {
    if (typeof raw.params !== "object" || Array.isArray(raw.params)) {
      throw new WorkflowError("'params' must be a mapping", WorkflowErrorCode.INVALID_YAML);
    }
  }

  if (!("nodes" in raw) || !Array.isArray(raw.nodes)) {
    throw new WorkflowError("Missing required field: 'nodes' (must be an array)", WorkflowErrorCode.INVALID_YAML);
  }

  const nodes: NodeDef[] = raw.nodes.map((n: unknown, i: number) => parseNode(n, i, opts));

  const endNodes = nodes.filter((n) => n.type === "end");
  if (endNodes.length > 1) {
    throw new Error(
      `Workflow 最多允许一个 end 节点，当前定义了 ${endNodes.length} 个：${endNodes.map((n) => n.id).join(", ")}`,
    );
  }

  const startNodes = nodes.filter((n) => !n.depends_on || n.depends_on.length === 0);

  return {
    schema_version: schemaVersion,
    name: raw.name as string,
    description: typeof raw.description === "string" ? raw.description : undefined,
    params: (raw.params as WorkflowDef["params"]) ?? undefined,
    secrets: Array.isArray(raw.secrets) ? (raw.secrets as string[]) : undefined,
    timeout: typeof raw.timeout === "number" ? raw.timeout : undefined,
    nodes,
    _startNodeId: startNodes.length === 1 ? startNodes[0].id : undefined,
    _baseDir: baseDir ?? process.cwd(),
  };
}

// ========== Tests ==========

// ── 根级校验 ──

describe("yaml-parser: 根级结构校验", () => {
  test("null 输入抛 INVALID_YAML", () => {
    expect(() => validateAndBuildWorkflow(null)).toThrow(WorkflowError);
  });

  test("数组输入抛 INVALID_YAML", () => {
    expect(() => validateAndBuildWorkflow([1, 2])).toThrow("YAML root must be a mapping");
  });

  test("字符串输入抛 INVALID_YAML", () => {
    expect(() => validateAndBuildWorkflow("hello")).toThrow("YAML root must be a mapping");
  });

  test("acpx-g 格式检测", () => {
    const doc = { kind: "Workflow", metadata: {}, spec: {} };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("acpx-g format");
  });

  test("缺少 schema_version 抛错", () => {
    expect(() => validateAndBuildWorkflow({ name: "test", nodes: [] })).toThrow("schema_version");
  });

  test("schema_version 不为 1 抛错", () => {
    expect(() => validateAndBuildWorkflow({ schema_version: "2", name: "test", nodes: [] })).toThrow(
      "Unsupported schema_version: '2'",
    );
  });

  test("schema_version 为数字 1 也能识别", () => {
    const doc = { schema_version: 1, name: "test", nodes: [{ id: "a", type: "shell", command: "echo hi" }] };
    const result = validateAndBuildWorkflow(doc);
    expect(result.schema_version).toBe("1");
  });

  test("缺少 name 抛错", () => {
    expect(() => validateAndBuildWorkflow({ schema_version: "1", nodes: [] })).toThrow("name");
  });

  test("name 为空字符串抛错", () => {
    expect(() => validateAndBuildWorkflow({ schema_version: "1", name: "  ", nodes: [] })).toThrow("name");
  });

  test("缺少 nodes 抛错", () => {
    expect(() => validateAndBuildWorkflow({ schema_version: "1", name: "test" })).toThrow("nodes");
  });

  test("nodes 非数组抛错", () => {
    expect(() => validateAndBuildWorkflow({ schema_version: "1", name: "test", nodes: "bad" })).toThrow("nodes");
  });

  test("params 为数组时抛错", () => {
    expect(() =>
      validateAndBuildWorkflow({ schema_version: "1", name: "test", params: [1], nodes: [] }),
    ).toThrow("params");
  });
});

// ── 正常解析 ──

describe("yaml-parser: 正常 workflow 解析", () => {
  test("最小有效 workflow", () => {
    const doc = {
      schema_version: "1",
      name: "my-workflow",
      nodes: [{ id: "step1", type: "shell", command: "echo hello" }],
    };
    const result = validateAndBuildWorkflow(doc, "/tmp/workflows");
    expect(result.name).toBe("my-workflow");
    expect(result.schema_version).toBe("1");
    expect(result.nodes).toHaveLength(1);
    expect(result.nodes[0].id).toBe("step1");
    expect(result.nodes[0].type).toBe("shell");
    expect(result._baseDir).toBe("/tmp/workflows");
  });

  test("可选字段：description, secrets, timeout", () => {
    const doc = {
      schema_version: "1",
      name: "full",
      description: "A test workflow",
      secrets: ["API_KEY"],
      timeout: 300,
      nodes: [{ id: "s1", type: "shell", command: "ls" }],
    };
    const result = validateAndBuildWorkflow(doc);
    expect(result.description).toBe("A test workflow");
    expect(result.secrets).toEqual(["API_KEY"]);
    expect(result.timeout).toBe(300);
  });

  test("params 映射正确传递", () => {
    const doc = {
      schema_version: "1",
      name: "param-test",
      params: { input_file: { type: "string", required: true } },
      nodes: [{ id: "s1", type: "shell", command: "echo $input_file" }],
    };
    const result = validateAndBuildWorkflow(doc);
    expect(result.params).toEqual({ input_file: { type: "string", required: true } });
  });

  test("唯一无依赖节点设为 _startNodeId", () => {
    const doc = {
      schema_version: "1",
      name: "start-test",
      nodes: [
        { id: "first", type: "shell", command: "echo 1" },
        { id: "second", type: "shell", command: "echo 2", depends_on: ["first"] },
      ],
    };
    const result = validateAndBuildWorkflow(doc);
    expect(result._startNodeId).toBe("first");
  });

  test("多个无依赖节点时 _startNodeId 为 undefined", () => {
    const doc = {
      schema_version: "1",
      name: "multi-start",
      nodes: [
        { id: "a", type: "shell", command: "echo a" },
        { id: "b", type: "shell", command: "echo b" },
      ],
    };
    const result = validateAndBuildWorkflow(doc);
    expect(result._startNodeId).toBeUndefined();
  });
});

// ── Shell 节点 ──

describe("yaml-parser: shell 节点", () => {
  test("缺少 command 抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "s1", type: "shell" }],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("shell node requires 'command'");
  });

  test("command 为字符串数组也接受", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "s1", type: "shell", command: ["echo", "hello"] }],
    };
    const result = validateAndBuildWorkflow(doc);
    expect((result.nodes[0] as ShellNodeDef).command).toEqual(["echo", "hello"]);
  });

  test("可选字段 cwd 和 inputs", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "s1", type: "shell", command: "ls", cwd: "/tmp", inputs: { FILE: "nodes.a.output.file" } }],
    };
    const result = validateAndBuildWorkflow(doc);
    const node = result.nodes[0] as ShellNodeDef;
    expect(node.cwd).toBe("/tmp");
    expect(node.inputs).toEqual({ FILE: "nodes.a.output.file" });
  });
});

// ── Python 节点 ──

describe("yaml-parser: python 节点", () => {
  test("缺少 code 抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "p1", type: "python" }],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("python node requires 'code'");
  });

  test("正常解析含 requirements", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "p1", type: "python", code: "print('hi')", requirements: ["numpy"] }],
    };
    const result = validateAndBuildWorkflow(doc);
    const node = result.nodes[0] as PythonNodeDef;
    expect(node.code).toBe("print('hi')");
    expect(node.requirements).toEqual(["numpy"]);
  });
});

// ── Agent 节点 ──

describe("yaml-parser: agent 节点", () => {
  test("缺少 prompt 抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "a1", type: "agent", agent: "env-1" }],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("agent node requires 'prompt'");
  });

  test("缺少 agent 抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "a1", type: "agent", prompt: "do something" }],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("agent node requires 'agent'");
  });

  test("agent 为空字符串抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "a1", type: "agent", prompt: "do", agent: "" }],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("agent node requires 'agent'");
  });

  test("output_messages 数字正确传递", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "a1", type: "agent", prompt: "do", agent: "env-1", output_messages: 5 }],
    };
    const result = validateAndBuildWorkflow(doc);
    const node = result.nodes[0] as AgentNodeDef;
    expect(node.output_messages).toBe(5);
  });
});

// ── API 节点 ──

describe("yaml-parser: api 节点", () => {
  test("缺少 url 抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "api1", type: "api" }],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("api node requires 'url'");
  });

  test("正常解析含 method/headers/body", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{
        id: "api1", type: "api", url: "https://example.com",
        method: "POST", headers: { "Content-Type": "application/json" }, body: '{"key":"val"}',
      }],
    };
    const result = validateAndBuildWorkflow(doc);
    const node = result.nodes[0] as ApiNodeDef;
    expect(node.url).toBe("https://example.com");
    expect(node.method).toBe("POST");
    expect(node.headers).toEqual({ "Content-Type": "application/json" });
    expect(node.body).toBe('{"key":"val"}');
  });
});

// ── Audit 节点 ──

describe("yaml-parser: audit 节点", () => {
  test("audit 节点无必填字段", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "aud1", type: "audit" }],
    };
    const result = validateAndBuildWorkflow(doc);
    expect(result.nodes[0].type).toBe("audit");
  });

  test("可选 expires_in 和 display_data", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "aud1", type: "audit", expires_in: 3600, display_data: { summary: "review" } }],
    };
    const result = validateAndBuildWorkflow(doc);
    const node = result.nodes[0] as AuditNodeDef;
    expect(node.expires_in).toBe(3600);
    expect(node.display_data).toEqual({ summary: "review" });
  });
});

// ── Workflow 节点 ──

describe("yaml-parser: workflow 子工作流节点", () => {
  test("缺少 ref 抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "sub1", type: "workflow" }],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("workflow node requires 'ref'");
  });

  test("正常解析含 params 和 ignore_errors", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "sub1", type: "workflow", ref: "./other.yaml", params: { x: 1 }, ignore_errors: true }],
    };
    const result = validateAndBuildWorkflow(doc);
    const node = result.nodes[0] as SubWorkflowNodeDef;
    expect(node.ref).toBe("./other.yaml");
    expect(node.params).toEqual({ x: 1 });
    expect(node.ignore_errors).toBe(true);
  });
});

// ── Loop 节点 ──

describe("yaml-parser: loop 节点", () => {
  test("缺少 condition 抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "l1", type: "loop", max_iterations: 10, body: { nodes: [] } }],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("loop node requires 'condition'");
  });

  test("缺少 max_iterations 抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "l1", type: "loop", condition: "i < 5", body: { nodes: [] } }],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("loop node requires 'max_iterations'");
  });

  test("max_iterations 非数字抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "l1", type: "loop", condition: "i < 5", max_iterations: "10", body: { nodes: [] } }],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("loop node requires 'max_iterations' (number)");
  });

  test("缺少 body.nodes 抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "l1", type: "loop", condition: "i < 5", max_iterations: 10, body: {} }],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("loop node requires 'body.nodes'");
  });

  test("正常解析含嵌套 body nodes", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{
        id: "l1", type: "loop", condition: "i < 5", max_iterations: 10,
        body: { nodes: [{ id: "inner1", type: "shell", command: "echo loop" }] },
      }],
    };
    const result = validateAndBuildWorkflow(doc);
    const node = result.nodes[0] as LoopNodeDef;
    expect(node.body.nodes).toHaveLength(1);
    expect(node.body.nodes[0].id).toBe("inner1");
  });

  test("loop body 包含非法节点类型时传播错误", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{
        id: "l1", type: "loop", condition: "i < 5", max_iterations: 10,
        body: {
          nodes: [{ id: "bad-inner", type: "bogus_type" }],
        },
      }],
    };
    // parseNode 递归解析 body.nodes，遇到非法类型抛出 INVALID_YAML
    expect(() => validateAndBuildWorkflow(doc)).toThrow("invalid type 'bogus_type'");
    try {
      validateAndBuildWorkflow(doc);
      expect.unreachable("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(WorkflowError);
      expect((err as WorkflowError).code).toBe("INVALID_YAML");
      expect((err as WorkflowError).message).toContain("bad-inner");
    }
  });
});

// ── Transform 节点 ──

describe("yaml-parser: transform 节点", () => {
  test("缺少 output 抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "t1", type: "transform" }],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("transform node requires non-empty 'output'");
  });

  test("output 为空对象抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "t1", type: "transform", output: {} }],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("transform node requires non-empty 'output'");
  });

  test("正常解析 output 映射", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "t1", type: "transform", output: { result: "inputs.x + 1" } }],
    };
    const result = validateAndBuildWorkflow(doc);
    const node = result.nodes[0] as TransformNodeDef;
    expect(node.output).toEqual({ result: "inputs.x + 1" });
  });
});

// ── End 节点 ──

describe("yaml-parser: end 节点", () => {
  test("end 节点正常解析", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [
        { id: "s1", type: "shell", command: "echo 1" },
        { id: "done", type: "end", depends_on: ["s1"], inputs: { result: "nodes.s1.stdout" } },
      ],
    };
    const result = validateAndBuildWorkflow(doc);
    const endNode = result.nodes[1] as EndNodeDef;
    expect(endNode.type).toBe("end");
    expect(endNode.inputs).toEqual({ result: "nodes.s1.stdout" });
  });

  test("多个 end 节点抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [
        { id: "e1", type: "end" },
        { id: "e2", type: "end" },
      ],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("最多允许一个 end 节点");
  });
});

// ── 通用节点校验 ──

describe("yaml-parser: 节点通用校验", () => {
  test("节点非对象抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: ["not an object"],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("nodes[0] must be a mapping");
  });

  test("节点 id 缺失抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ type: "shell", command: "echo" }],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("missing or empty 'id'");
  });

  test("节点 id 为空字符串抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "", type: "shell", command: "echo" }],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("missing or empty 'id'");
  });

  test("无效节点类型抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "x", type: "unknown_type" }],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("invalid type 'unknown_type'");
  });

  test("depends_on 正确传递", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [
        { id: "a", type: "shell", command: "echo a" },
        { id: "b", type: "shell", command: "echo b", depends_on: ["a"] },
      ],
    };
    const result = validateAndBuildWorkflow(doc);
    expect(result.nodes[1].depends_on).toEqual(["a"]);
  });

  test("condition 和 timeout 正确传递", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "a", type: "shell", command: "echo", condition: "params.run == true", timeout: 60 }],
    };
    const result = validateAndBuildWorkflow(doc);
    expect(result.nodes[0].condition).toBe("params.run == true");
    expect(result.nodes[0].timeout).toBe(60);
  });

  test("env 正确传递", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "a", type: "shell", command: "echo", env: { MY_VAR: "value" } }],
    };
    const result = validateAndBuildWorkflow(doc);
    expect(result.nodes[0].env).toEqual({ MY_VAR: "value" });
  });
});

// ── parseOutputs ──

describe("yaml-parser: parseOutputs", () => {
  test("非 record 返回空对象", () => {
    expect(parseOutputs(null)).toEqual({});
    expect(parseOutputs(undefined)).toEqual({});
    expect(parseOutputs("string")).toEqual({});
    expect(parseOutputs([1, 2])).toEqual({});
  });

  test("正常解析 outputs", () => {
    const raw = {
      log: { pattern: "*.log", type: "file" },
      artifacts: { pattern: "dist/**", type: "dir" },
    };
    const result = parseOutputs(raw);
    expect(result.log).toEqual({ pattern: "*.log", type: "file" });
    expect(result.artifacts).toEqual({ pattern: "dist/**", type: "dir" });
  });

  test("type 默认 fallback 为 file", () => {
    const raw = { out: { pattern: "*.txt", type: "unknown" } };
    const result = parseOutputs(raw);
    expect(result.out.type).toBe("file");
  });

  test("pattern 缺失默认为空字符串", () => {
    const raw = { out: { type: "file" } };
    const result = parseOutputs(raw);
    expect(result.out.pattern).toBe("");
  });

  test("value 非 record 抛错", () => {
    expect(() => parseOutputs({ bad: "not a mapping" })).toThrow("outputs.bad: must be a mapping");
  });

  test("file-list 类型正确识别", () => {
    const raw = { files: { pattern: "*.csv", type: "file-list" } };
    const result = parseOutputs(raw);
    expect(result.files.type).toBe("file-list");
  });
});

// ── parseSlurmConfig ──

describe("yaml-parser: parseSlurmConfig", () => {
  test("非 record 返回 undefined", () => {
    expect(parseSlurmConfig(null)).toBeUndefined();
    expect(parseSlurmConfig(undefined)).toBeUndefined();
    expect(parseSlurmConfig("string")).toBeUndefined();
  });

  test("空对象返回 undefined", () => {
    expect(parseSlurmConfig({})).toBeUndefined();
  });

  test("正常解析所有字段", () => {
    const raw = {
      partition: "gpu",
      cores: 8,
      nodes: 2,
      memory: "16G",
      walltime: "01:00:00",
      modules: ["cuda", "python3"],
      jobName: "my-job",
      extraSBATCH: ["--gres=gpu:1"],
    };
    const result = parseSlurmConfig(raw);
    expect(result).toEqual(raw);
  });

  test("cores 为字符串数字时宽容解析", () => {
    const result = parseSlurmConfig({ cores: "4" });
    expect(result?.cores).toBe(4);
  });

  test("cores 为非数字字符串时忽略", () => {
    const result = parseSlurmConfig({ cores: "abc" });
    expect(result).toBeUndefined();
  });

  test("modules 中非字符串元素被过滤", () => {
    const result = parseSlurmConfig({ modules: ["cuda", 123, "python"] });
    expect(result?.modules).toEqual(["cuda", "python"]);
  });

  test("类型不匹配的字段被忽略", () => {
    const result = parseSlurmConfig({ partition: 123, cores: "not-a-num", memory: true });
    expect(result).toBeUndefined();
  });
});

// ── parseScriptConfig ──

describe("yaml-parser: parseScriptConfig", () => {
  test("undefined/null 返回 undefined", () => {
    expect(parseScriptConfig(undefined, "n1")).toBeUndefined();
    expect(parseScriptConfig(null, "n1")).toBeUndefined();
  });

  test("非 record 抛错", () => {
    expect(() => parseScriptConfig("not-a-map", "n1")).toThrow("'script' must be a mapping");
  });

  test("content 缺失抛错", () => {
    expect(() => parseScriptConfig({ env: { A: "1" } }, "n1")).toThrow("'script.content' is required");
  });

  test("content 为空字符串抛错", () => {
    expect(() => parseScriptConfig({ content: "  " }, "n1")).toThrow("'script.content' is required");
  });

  test("正常解析 content + env", () => {
    const result = parseScriptConfig({ content: "echo hello", env: { FOO: "bar" } }, "n1");
    expect(result).toEqual({ content: "echo hello", env: { FOO: "bar" } });
  });

  test("env 中非字符串值被跳过", () => {
    const result = parseScriptConfig({ content: "echo", env: { A: "ok", B: 123, C: "fine" } }, "n1");
    expect(result?.env).toEqual({ A: "ok", C: "fine" });
  });

  test("env 非 record 抛错", () => {
    expect(() => parseScriptConfig({ content: "echo", env: "bad" }, "n1")).toThrow("'script.env' must be a mapping");
  });
});

// ── Custom 节点 ──

describe("yaml-parser: custom 节点", () => {
  test("缺少 tool 抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "c1", type: "custom", outputs: { result: { pattern: "*.txt", type: "file" } } }],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("custom node requires 'tool'");
  });

  test("tool 为空字符串抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "c1", type: "custom", tool: "  ", outputs: { result: { pattern: "*.txt", type: "file" } } }],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("custom node requires 'tool'");
  });

  test("缺少 outputs 抛错", () => {
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "c1", type: "custom", tool: "my-tool" }],
    };
    expect(() => validateAndBuildWorkflow(doc)).toThrow("custom node requires 'outputs' mapping");
  });

  test("registry 存在但 tool 未注册抛错", () => {
    const registry: CustomNodeRegistry = {
      get: () => undefined,
    };
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{ id: "c1", type: "custom", tool: "unknown-tool", outputs: { r: { pattern: "*", type: "file" } } }],
    };
    expect(() => validateAndBuildWorkflow(doc, undefined, { customRegistry: registry })).toThrow(
      "custom tool 'unknown-tool' not registered",
    );
  });

  test("registry 校验 outputs key 不在 produces 列表中抛错", () => {
    const registry: CustomNodeRegistry = {
      get: (name: string) => name === "my-tool" ? { name: "my-tool", kind: "default", produces: ["result"] } : undefined,
    };
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{
        id: "c1", type: "custom", tool: "my-tool",
        outputs: {
          result: { pattern: "*.txt", type: "file" },
          extra: { pattern: "*.log", type: "file" },
        },
      }],
    };
    expect(() => validateAndBuildWorkflow(doc, undefined, { customRegistry: registry })).toThrow(
      "output 'extra' not declared in tool 'my-tool' produces list",
    );
  });

  test("produces 含 * 时跳过 outputs 校验", () => {
    const registry: CustomNodeRegistry = {
      get: (name: string) => name === "wild-tool" ? { name: "wild-tool", kind: "default", produces: ["*"] } : undefined,
    };
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{
        id: "c1", type: "custom", tool: "wild-tool",
        outputs: { anything: { pattern: "*", type: "file" } },
      }],
    };
    const result = validateAndBuildWorkflow(doc, undefined, { customRegistry: registry });
    expect(result.nodes[0].type).toBe("custom");
  });

  test("slurm tool 缺少 script 抛错", () => {
    const registry: CustomNodeRegistry = {
      get: (name: string) => name === "slurm-tool" ? { name: "slurm-tool", kind: "slurm", produces: ["output"] } : undefined,
    };
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{
        id: "c1", type: "custom", tool: "slurm-tool",
        outputs: { output: { pattern: "*.out", type: "file" } },
      }],
    };
    expect(() => validateAndBuildWorkflow(doc, undefined, { customRegistry: registry })).toThrow(
      "slurm tool 'slurm-tool' requires 'script.content'",
    );
  });

  test("slurm tool 含 script 正常解析", () => {
    const registry: CustomNodeRegistry = {
      get: (name: string) => name === "slurm-tool" ? { name: "slurm-tool", kind: "slurm", produces: ["output"] } : undefined,
    };
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{
        id: "c1", type: "custom", tool: "slurm-tool",
        outputs: { output: { pattern: "*.out", type: "file" } },
        script: { content: "srun echo hello" },
        slurm: { partition: "gpu", cores: 4 },
      }],
    };
    const result = validateAndBuildWorkflow(doc, undefined, { customRegistry: registry });
    const node = result.nodes[0] as CustomNodeDef;
    expect(node.script?.content).toBe("srun echo hello");
    expect(node.slurm?.partition).toBe("gpu");
    expect(node.slurm?.cores).toBe(4);
  });

  test("非 slurm tool 含 script 抛错", () => {
    const registry: CustomNodeRegistry = {
      get: (name: string) => name === "normal-tool" ? { name: "normal-tool", kind: "default", produces: ["*"] } : undefined,
    };
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{
        id: "c1", type: "custom", tool: "normal-tool",
        outputs: { r: { pattern: "*", type: "file" } },
        script: { content: "echo bad" },
      }],
    };
    expect(() => validateAndBuildWorkflow(doc, undefined, { customRegistry: registry })).toThrow(
      "non-slurm tool 'normal-tool' does not support 'script' field",
    );
  });

  test("custom 节点可选字段 foreach/maxConcurrent/continueOnError", () => {
    const registry: CustomNodeRegistry = {
      get: (name: string) => name === "iter-tool" ? { name: "iter-tool", kind: "default", produces: ["*"] } : undefined,
    };
    const doc = {
      schema_version: "1", name: "test",
      nodes: [{
        id: "c1", type: "custom", tool: "iter-tool",
        outputs: { r: { pattern: "*", type: "file" } },
        foreach: "params.items",
        maxConcurrent: 3,
        continueOnError: true,
      }],
    };
    const result = validateAndBuildWorkflow(doc, undefined, { customRegistry: registry });
    const node = result.nodes[0] as CustomNodeDef;
    expect(node.foreach).toBe("params.items");
    expect(node.maxConcurrent).toBe(3);
    expect(node.continueOnError).toBe(true);
  });
});

// ── WorkflowError 属性 ──

describe("yaml-parser: WorkflowError 属性校验", () => {
  test("错误码为 INVALID_YAML", () => {
    try {
      validateAndBuildWorkflow(null);
      expect.unreachable("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(WorkflowError);
      expect((err as WorkflowError).code).toBe("INVALID_YAML");
    }
  });

  test("错误消息包含诊断信息", () => {
    try {
      validateAndBuildWorkflow({ schema_version: "3", name: "test", nodes: [] });
      expect.unreachable("should have thrown");
    } catch (err) {
      expect((err as WorkflowError).message).toContain("Unsupported schema_version: '3'");
    }
  });
});
