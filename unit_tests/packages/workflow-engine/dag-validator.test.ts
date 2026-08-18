import { describe, test, expect } from "bun:test";

// ========== Pure function copies from packages/workflow-engine/src/parser/dag-validator.ts ==========

// ---------- Types (inline) ----------

interface NodeDef {
  id: string;
  type: string;
  depends_on?: string[];
  condition?: string;
  timeout?: number;
  retry?: any;
  env?: Record<string, string>;
  outputs?: any;
  // Shell
  command?: string | string[];
  cwd?: string;
  inputs?: Record<string, string>;
  // Python
  code?: string;
  requirements?: string[];
  // Agent
  agent?: string;
  prompt?: string;
  output_messages?: number;
  // API
  url?: string;
  method?: string;
  headers?: Record<string, string>;
  body?: string;
  // Audit
  display_data?: unknown;
  expires_in?: number;
  // Workflow
  ref?: string;
  params?: Record<string, unknown>;
  ignore_errors?: boolean;
  // Loop
  max_iterations?: number;
  // Transform
  output?: Record<string, string>;
  // Custom
  tool?: string;
  slurm?: any;
  script?: any;
  foreach?: string;
  maxConcurrent?: number;
  continueOnError?: boolean;
  // End
  description?: string;
  // Allow any extra keys
  [key: string]: unknown;
}

interface WorkflowDef {
  schema_version: string;
  name: string;
  description?: string;
  params?: Record<string, any>;
  secrets?: string[];
  timeout?: number;
  nodes: NodeDef[];
  _startNodeId?: string;
  _baseDir?: string;
}

interface ValidationIssue {
  type: "error" | "warning";
  code: string;
  message: string;
  nodeId?: string;
}

interface ValidationResult {
  valid: boolean;
  issues: ValidationIssue[];
  def: WorkflowDef;
}

// ---------- Error ----------

class WorkflowError extends Error {
  readonly code: string;
  readonly details?: Record<string, unknown>;
  constructor(message: string, code: string, details?: Record<string, unknown>) {
    super(message);
    this.code = code;
    this.details = details;
    this.name = "WorkflowError";
  }
}

// ---------- Helper functions ----------

function scanTemplateDeps(node: NodeDef): Set<string> {
  const refs = new Set<string>();
  if (node.type === "loop") {
    const { condition, body, ...outer } = node;
    scanNodeStrings(outer, refs);
  } else {
    scanNodeStrings(node, refs);
  }
  return refs;
}

function scanNodeStrings(obj: unknown, refs: Set<string>): void {
  if (typeof obj === "string") {
    const templatePattern = /\$\{\{\s*([\s\S]*?)\s*\}\}/g;
    for (const match of obj.matchAll(templatePattern)) {
      const expr = match[1];
      extractNodeIdFromExpr(expr, refs);
    }
  } else if (Array.isArray(obj)) {
    for (const item of obj) {
      scanNodeStrings(item, refs);
    }
  } else if (obj !== null && typeof obj === "object") {
    for (const val of Object.values(obj)) {
      scanNodeStrings(val, refs);
    }
  }
}

function extractNodeIdFromExpr(expr: string, refs: Set<string>): void {
  let idx = 0;
  while (idx < expr.length) {
    const nodesIdx = expr.indexOf("nodes.", idx);
    if (nodesIdx === -1) break;
    const start = nodesIdx + 6;
    if (start < expr.length && /[a-zA-Z_$]/.test(expr[start])) {
      let end = start;
      while (end < expr.length && /[a-zA-Z0-9_$]/.test(expr[end])) end++;
      refs.add(expr.slice(start, end));
      idx = end;
    } else {
      idx = nodesIdx + 6;
    }
  }
}

// ---------- Main function ----------

function validateDAG(input: WorkflowDef): ValidationResult {
  const def = structuredClone(input);
  const issues: ValidationIssue[] = [];

  // 1. Node ID uniqueness
  const idSet = new Set<string>();
  for (const node of def.nodes) {
    if (idSet.has(node.id)) {
      throw new WorkflowError(
        `Duplicate node ID: '${node.id}'`,
        "DUPLICATE_NODE_ID",
        { nodeId: node.id },
      );
    }
    idSet.add(node.id);
  }

  // 4. Auto-scan ${{ }} to supplement depends_on
  const nodeMap = new Map<string, NodeDef>();
  for (const node of def.nodes) {
    nodeMap.set(node.id, node);
  }
  for (const node of def.nodes) {
    const autoDeps = scanTemplateDeps(node);
    for (const depId of autoDeps) {
      if (!node.depends_on?.includes(depId)) {
        if (!node.depends_on) node.depends_on = [];
        node.depends_on.push(depId);
        issues.push({
          type: "warning",
          code: "AUTO_DEPENDENCY_ADDED",
          message: `Auto-added '${depId}' to depends_on of '${node.id}' (detected in template expression)`,
          nodeId: node.id,
        });
      }
    }
  }

  // 3. Dependency existence
  for (const node of def.nodes) {
    if (node.depends_on) {
      for (const depId of node.depends_on) {
        if (!idSet.has(depId)) {
          issues.push({
            type: "error",
            code: "MISSING_DEPENDENCY",
            message: `Node '${node.id}' depends on '${depId}' which does not exist`,
            nodeId: node.id,
          });
        }
      }
    }
  }

  // 5. Variable reference validity
  for (const node of def.nodes) {
    const referenced = scanTemplateDeps(node);
    const deps = new Set(node.depends_on ?? []);
    for (const depId of referenced) {
      if (!deps.has(depId)) {
        issues.push({
          type: "error",
          code: "UNDEFINED_VARIABLE",
          message: `Node '${node.id}' references 'nodes.${depId}' without declaring it in depends_on`,
          nodeId: node.id,
        });
      }
    }
  }

  // 6. Inputs reference validation
  for (const node of def.nodes) {
    if (
      node.type !== "shell" &&
      node.type !== "python" &&
      node.type !== "transform" &&
      node.type !== "custom"
    )
      continue;
    const inputs = node.inputs;
    if (!inputs) continue;

    const deps = new Set(node.depends_on ?? []);
    for (const [, expr] of Object.entries(inputs)) {
      const refs = new Set<string>();
      extractNodeIdFromExpr(expr, refs);
      for (const refId of refs) {
        if (!deps.has(refId)) {
          issues.push({
            type: "error",
            code: "INPUTS_MISSING_DEPENDENCY",
            message: `Node '${node.id}' references 'nodes.${refId}' in inputs but does not declare it in depends_on`,
            nodeId: node.id,
          });
        }
      }
    }
  }

  // 2. Cycle detection (Kahn's algorithm)
  const inDegree = new Map<string, number>();
  const adjacency = new Map<string, string[]>();
  for (const node of def.nodes) {
    inDegree.set(node.id, 0);
    adjacency.set(node.id, []);
  }
  for (const node of def.nodes) {
    for (const depId of node.depends_on ?? []) {
      if (adjacency.has(depId)) {
        adjacency.get(depId)!.push(node.id);
        inDegree.set(node.id, (inDegree.get(node.id) ?? 0) + 1);
      }
    }
  }

  const queue: string[] = [];
  for (const [id, deg] of inDegree) {
    if (deg === 0) queue.push(id);
  }

  let processed = 0;
  while (queue.length > 0) {
    const current = queue.shift()!;
    processed++;
    for (const neighbor of adjacency.get(current) ?? []) {
      const newDeg = (inDegree.get(neighbor) ?? 1) - 1;
      inDegree.set(neighbor, newDeg);
      if (newDeg === 0) queue.push(neighbor);
    }
  }

  if (processed < def.nodes.length) {
    const cycleNodes = def.nodes
      .filter((n) => (inDegree.get(n.id) ?? 0) > 0)
      .map((n) => n.id);
    throw new WorkflowError(
      `Cycle detected in DAG involving nodes: ${cycleNodes.join(", ")}`,
      "CYCLE_DETECTED",
      { nodeIds: cycleNodes },
    );
  }

  return {
    valid: issues.filter((i) => i.type === "error").length === 0,
    issues,
    def,
  };
}

// ========== Tests ==========

describe("validateDAG", () => {
  test("validates a simple valid DAG", () => {
    const def: WorkflowDef = {
      schema_version: "1.0",
      name: "test",
      nodes: [
        { id: "a", type: "shell", command: "echo a" },
        { id: "b", type: "shell", command: "echo b", depends_on: ["a"] },
      ],
    };
    const result = validateDAG(def);
    expect(result.valid).toBe(true);
    expect(result.issues.filter((i) => i.type === "error")).toHaveLength(0);
  });

  test("validates an empty nodes array", () => {
    const def: WorkflowDef = {
      schema_version: "1.0",
      name: "empty",
      nodes: [],
    };
    const result = validateDAG(def);
    expect(result.valid).toBe(true);
  });

  test("validates a single node", () => {
    const def: WorkflowDef = {
      schema_version: "1.0",
      name: "single",
      nodes: [{ id: "only", type: "shell", command: "echo hi" }],
    };
    const result = validateDAG(def);
    expect(result.valid).toBe(true);
    expect(result.def.nodes.length).toBe(1);
  });

  test("validates diamond DAG", () => {
    const def: WorkflowDef = {
      schema_version: "1.0",
      name: "diamond",
      nodes: [
        { id: "start", type: "shell", command: "start" },
        { id: "left", type: "shell", command: "left", depends_on: ["start"] },
        { id: "right", type: "shell", command: "right", depends_on: ["start"] },
        { id: "end", type: "shell", command: "end", depends_on: ["left", "right"] },
      ],
    };
    const result = validateDAG(def);
    expect(result.valid).toBe(true);
  });

  test("throws on duplicate node ID", () => {
    const def: WorkflowDef = {
      schema_version: "1.0",
      name: "dup",
      nodes: [
        { id: "a", type: "shell", command: "echo 1" },
        { id: "a", type: "shell", command: "echo 2" },
      ],
    };
    expect(() => validateDAG(def)).toThrow("Duplicate node ID");
    try {
      validateDAG(def);
    } catch (e: any) {
      expect(e.code).toBe("DUPLICATE_NODE_ID");
    }
  });

  test("throws on cycle", () => {
    const def: WorkflowDef = {
      schema_version: "1.0",
      name: "cycle",
      nodes: [
        { id: "a", type: "shell", command: "a", depends_on: ["b"] },
        { id: "b", type: "shell", command: "b", depends_on: ["a"] },
      ],
    };
    expect(() => validateDAG(def)).toThrow("Cycle detected");
    try {
      validateDAG(def);
    } catch (e: any) {
      expect(e.code).toBe("CYCLE_DETECTED");
      expect(e.details?.nodeIds).toBeDefined();
    }
  });

  test("throws on three-node cycle", () => {
    const def: WorkflowDef = {
      schema_version: "1.0",
      name: "cycle3",
      nodes: [
        { id: "a", type: "shell", command: "a", depends_on: ["c"] },
        { id: "b", type: "shell", command: "b", depends_on: ["a"] },
        { id: "c", type: "shell", command: "c", depends_on: ["b"] },
      ],
    };
    expect(() => validateDAG(def)).toThrow("Cycle detected");
  });

  test("reports missing dependency as error issue", () => {
    const def: WorkflowDef = {
      schema_version: "1.0",
      name: "missing-dep",
      nodes: [
        { id: "a", type: "shell", command: "echo", depends_on: ["nonexistent"] },
      ],
    };
    const result = validateDAG(def);
    expect(result.valid).toBe(false);
    const missingDepIssues = result.issues.filter(
      (i) => i.code === "MISSING_DEPENDENCY",
    );
    expect(missingDepIssues.length).toBe(1);
    expect(missingDepIssues[0].type).toBe("error");
    expect(missingDepIssues[0].message).toContain("nonexistent");
  });

  test("auto-adds dependency from template expression", () => {
    const def: WorkflowDef = {
      schema_version: "1.0",
      name: "auto-dep",
      nodes: [
        { id: "step1", type: "shell", command: "echo hello" },
        {
          id: "step2",
          type: "shell",
          command: "${{ nodes.step1.output }}",
        },
      ],
    };
    const result = validateDAG(def);
    expect(result.valid).toBe(true);
    const autoDepWarnings = result.issues.filter(
      (i) => i.code === "AUTO_DEPENDENCY_ADDED",
    );
    expect(autoDepWarnings.length).toBe(1);
    expect(autoDepWarnings[0].message).toContain("step1");
    // Verify depends_on was auto-added in the output def
    const step2 = result.def.nodes.find((n) => n.id === "step2");
    expect(step2?.depends_on).toContain("step1");
  });

  test("does not duplicate existing dependency when auto-detected", () => {
    const def: WorkflowDef = {
      schema_version: "1.0",
      name: "no-dup-dep",
      nodes: [
        { id: "step1", type: "shell", command: "echo" },
        {
          id: "step2",
          type: "shell",
          command: "${{ nodes.step1.output }}",
          depends_on: ["step1"],
        },
      ],
    };
    const result = validateDAG(def);
    expect(result.valid).toBe(true);
    const autoDepWarnings = result.issues.filter(
      (i) => i.code === "AUTO_DEPENDENCY_ADDED",
    );
    expect(autoDepWarnings.length).toBe(0);
  });

  test("auto-adds multiple dependencies from template", () => {
    const def: WorkflowDef = {
      schema_version: "1.0",
      name: "multi-auto-dep",
      nodes: [
        { id: "a", type: "shell", command: "echo a" },
        { id: "b", type: "shell", command: "echo b" },
        {
          id: "c",
          type: "shell",
          command: "${{ nodes.a.output }} and ${{ nodes.b.output }}",
        },
      ],
    };
    const result = validateDAG(def);
    expect(result.valid).toBe(true);
    const autoDepWarnings = result.issues.filter(
      (i) => i.code === "AUTO_DEPENDENCY_ADDED",
    );
    expect(autoDepWarnings.length).toBe(2);
    const stepC = result.def.nodes.find((n) => n.id === "c");
    expect(stepC?.depends_on).toContain("a");
    expect(stepC?.depends_on).toContain("b");
  });

  test("validates inputs reference in shell node", () => {
    const def: WorkflowDef = {
      schema_version: "1.0",
      name: "inputs-check",
      nodes: [
        { id: "step1", type: "shell", command: "echo" },
        {
          id: "step2",
          type: "shell",
          command: "echo",
          depends_on: ["step1"],
          inputs: { data: "${{ nodes.step1.output }}" },
        },
      ],
    };
    const result = validateDAG(def);
    expect(result.valid).toBe(true);
    // step1 is in depends_on, so no INPUTS_MISSING_DEPENDENCY
    const inputIssues = result.issues.filter(
      (i) => i.code === "INPUTS_MISSING_DEPENDENCY",
    );
    expect(inputIssues.length).toBe(0);
  });

  test("auto-dependency 自动补全 inputs 缺失的依赖", () => {
    const def: WorkflowDef = {
      schema_version: "1.0",
      name: "inputs-missing",
      nodes: [
        { id: "step1", type: "shell", command: "echo" },
        {
          id: "step2",
          type: "shell",
          command: "echo",
          inputs: { data: "${{ nodes.step1.output }}" },
          // depends_on is missing — auto-dependency will add it from command scan,
          // but inputs scan happens separately
        },
      ],
    };
    const result = validateDAG(def);
    // auto-dependency should add step1 to depends_on, so inputs check should pass
    expect(result.valid).toBe(true);
  });

  test("returns deep-cloned def (does not mutate original)", () => {
    const original: WorkflowDef = {
      schema_version: "1.0",
      name: "immutable",
      nodes: [
        { id: "a", type: "shell", command: "echo" },
        {
          id: "b",
          type: "shell",
          command: "${{ nodes.a.output }}",
        },
      ],
    };
    const originalJson = JSON.stringify(original);
    const result = validateDAG(original);
    // Original should not be mutated
    expect(JSON.stringify(original)).toBe(originalJson);
    // Result def should have auto-added depends_on
    const bNode = result.def.nodes.find((n) => n.id === "b");
    expect(bNode?.depends_on).toContain("a");
  });

  test("loop node body 和 condition 都不扫描自动依赖", () => {
    const def: WorkflowDef = {
      schema_version: "1.0",
      name: "loop-test",
      nodes: [
        { id: "start", type: "shell", command: "echo" },
        {
          id: "looper",
          type: "loop",
          condition: "${{ nodes.start.output }}",
          max_iterations: 5,
          body: {
            nodes: [
              { id: "inner", type: "shell", command: "${{ nodes.nonexist.output }}" },
            ],
          },
          depends_on: ["start"],
        },
      ],
    };
    const result = validateDAG(def);
    // inner references nonexist, but it's inside loop body — should not affect outer DAG
    // The outer loop node only scans outer fields, not body/condition
    // But wait — condition references start, which is already in depends_on
    expect(result.valid).toBe(true);
  });

  test("validates complex valid workflow", () => {
    const def: WorkflowDef = {
      schema_version: "1.0",
      name: "complex",
      params: {
        input_file: { type: "string", required: true },
      },
      nodes: [
        { id: "parse", type: "shell", command: "cat ${{ params.input_file }}" },
        {
          id: "transform",
          type: "shell",
          command: "transform",
          depends_on: ["parse"],
          inputs: { data: "${{ nodes.parse.output }}" },
        },
        {
          id: "validate",
          type: "shell",
          command: "validate",
          depends_on: ["parse"],
        },
        {
          id: "merge",
          type: "shell",
          command: "merge",
          depends_on: ["transform", "validate"],
        },
        {
          id: "output",
          type: "end",
          depends_on: ["merge"],
          inputs: { result: "${{ nodes.merge.output }}" },
        },
      ],
    };
    const result = validateDAG(def);
    expect(result.valid).toBe(true);
    expect(result.def.nodes.length).toBe(5);
  });

  test("自引用节点检测为 CYCLE_DETECTED", () => {
    const def: WorkflowDef = {
      schema_version: "1.0",
      name: "self-ref",
      nodes: [
        { id: "self", type: "shell", command: "echo", depends_on: ["self"] },
      ],
    };
    expect(() => validateDAG(def)).toThrow("Cycle detected");
    try {
      validateDAG(def);
    } catch (e: any) {
      expect(e.code).toBe("CYCLE_DETECTED");
      expect(e.details?.nodeIds).toContain("self");
    }
  });

  test("INPUTS_MISSING_DEPENDENCY 错误码可达", () => {
    // 触发条件：inputs 中的 nodes.X 引用没有使用 ${{ }} 模板语法，
    // 所以 auto-dependency (step 4) 不会扫描到，但 inputs 校验 (step 6) 会发现
    const def: WorkflowDef = {
      schema_version: "1.0",
      name: "inputs-missing-reachable",
      nodes: [
        { id: "leak", type: "shell", command: "echo" },
        {
          id: "consumer",
          type: "shell",
          command: "echo",
          inputs: { data: "leaked: nodes.leak.output" },
          // depends_on 不包含 leak，且 inputs 值无 ${{ }}，auto-dep 无法自动补全
        },
      ],
    };
    const result = validateDAG(def);
    expect(result.valid).toBe(false);
    const inputIssues = result.issues.filter(
      (i) => i.code === "INPUTS_MISSING_DEPENDENCY",
    );
    expect(inputIssues.length).toBeGreaterThanOrEqual(1);
    expect(inputIssues[0].message).toContain("leak");
    expect(inputIssues[0].type).toBe("error");
  });
});

describe("scanTemplateDeps (via extractNodeIdFromExpr)", () => {
  // These are tested indirectly through validateDAG, but we can also test
  // the behavior through the public API

  test("extracts node references from complex expressions", () => {
    const def: WorkflowDef = {
      schema_version: "1.0",
      name: "expr-test",
      nodes: [
        { id: "a", type: "shell", command: "echo" },
        { id: "b", type: "shell", command: "echo" },
        {
          id: "c",
          type: "shell",
          command: "${{ nodes.a.output.data + nodes.b.output.data }}",
        },
      ],
    };
    const result = validateDAG(def);
    const autoDeps = result.issues.filter((i) => i.code === "AUTO_DEPENDENCY_ADDED");
    const depIds = autoDeps.map((d) => {
      const match = d.message.match(/Auto-added '(\w+)'/);
      return match?.[1];
    });
    expect(depIds).toContain("a");
    expect(depIds).toContain("b");
  });

  test("does not extract params or secrets as node deps", () => {
    const def: WorkflowDef = {
      schema_version: "1.0",
      name: "params-test",
      nodes: [
        {
          id: "step1",
          type: "shell",
          command: "${{ params.input }} ${{ secrets.KEY }}",
        },
      ],
    };
    const result = validateDAG(def);
    // Should not auto-add any node dependencies
    const autoDeps = result.issues.filter((i) => i.code === "AUTO_DEPENDENCY_ADDED");
    expect(autoDeps.length).toBe(0);
  });
});
