import { describe, test, expect } from "bun:test";

// ========== Pure function copies from packages/workflow-engine/src/scheduler/topological-sort.ts ==========

interface NodeDef {
  id: string;
  type: string;
  depends_on?: string[];
}

class WorkflowError extends Error {
  readonly code: string;
  constructor(message: string, code: string, extra?: any) {
    super(message);
    this.code = code;
    this.name = "WorkflowError";
  }
}

function topologicalSort(nodes: NodeDef[]): string[] {
  const idSet = new Set(nodes.map((n) => n.id));
  const inDegree = new Map<string, number>();
  const adjacency = new Map<string, string[]>();
  for (const node of nodes) {
    inDegree.set(node.id, 0);
    adjacency.set(node.id, []);
  }
  for (const node of nodes) {
    for (const dep of node.depends_on ?? []) {
      if (!idSet.has(dep))
        throw new WorkflowError(
          `Node '${node.id}' depends on unknown node '${dep}'`,
          "MISSING_DEPENDENCY",
        );
      adjacency.get(dep)!.push(node.id);
      inDegree.set(node.id, (inDegree.get(node.id) ?? 0) + 1);
    }
  }
  const queue: string[] = [];
  for (const [id, degree] of inDegree) {
    if (degree === 0) queue.push(id);
  }
  const result: string[] = [];
  while (queue.length > 0) {
    const id = queue.shift()!;
    result.push(id);
    for (const neighbor of adjacency.get(id) ?? []) {
      const newDegree = (inDegree.get(neighbor) ?? 1) - 1;
      inDegree.set(neighbor, newDegree);
      if (newDegree === 0) queue.push(neighbor);
    }
  }
  if (result.length !== nodes.length)
    throw new WorkflowError("Cycle detected in DAG", "CYCLE_DETECTED");
  return result;
}

function identifyParallelGroups(nodes: NodeDef[]): string[][] {
  const idSet = new Set(nodes.map((n) => n.id));
  const inDegree = new Map<string, number>();
  const adjacency = new Map<string, string[]>();
  for (const node of nodes) {
    inDegree.set(node.id, 0);
    adjacency.set(node.id, []);
  }
  for (const node of nodes) {
    for (const dep of node.depends_on ?? []) {
      if (!idSet.has(dep))
        throw new WorkflowError(
          `Node '${node.id}' depends on unknown node '${dep}'`,
          "MISSING_DEPENDENCY",
        );
      adjacency.get(dep)!.push(node.id);
      inDegree.set(node.id, (inDegree.get(node.id) ?? 0) + 1);
    }
  }
  let currentLevel: string[] = [];
  for (const [id, degree] of inDegree) {
    if (degree === 0) currentLevel.push(id);
  }
  const groups: string[][] = [];
  while (currentLevel.length > 0) {
    groups.push(currentLevel);
    const nextLevel: string[] = [];
    for (const id of currentLevel) {
      for (const neighbor of adjacency.get(id) ?? []) {
        const newDegree = (inDegree.get(neighbor) ?? 1) - 1;
        inDegree.set(neighbor, newDegree);
        if (newDegree === 0) nextLevel.push(neighbor);
      }
    }
    currentLevel = nextLevel;
  }
  if (groups.flat().length !== nodes.length)
    throw new WorkflowError("Cycle detected in DAG", "CYCLE_DETECTED");
  return groups;
}

function buildReverseAdjacency(nodes: NodeDef[]): Map<string, string[]> {
  const reverseAdj = new Map<string, string[]>();
  for (const node of nodes) {
    reverseAdj.set(node.id, []);
  }
  for (const node of nodes) {
    for (const dep of node.depends_on ?? []) {
      if (!reverseAdj.has(dep)) reverseAdj.set(dep, []);
      reverseAdj.get(dep)!.push(node.id);
    }
  }
  return reverseAdj;
}

// ========== Tests ==========

describe("topologicalSort", () => {
  test("returns empty array for empty input", () => {
    expect(topologicalSort([])).toEqual([]);
  });

  test("returns single node", () => {
    const result = topologicalSort([{ id: "a", type: "shell" }]);
    expect(result).toEqual(["a"]);
  });

  test("sorts linear chain correctly", () => {
    const nodes: NodeDef[] = [
      { id: "c", type: "shell", depends_on: ["b"] },
      { id: "b", type: "shell", depends_on: ["a"] },
      { id: "a", type: "shell" },
    ];
    const result = topologicalSort(nodes);
    expect(result).toEqual(["a", "b", "c"]);
  });

  test("sorts diamond shape correctly", () => {
    //     a
    //    / \
    //   b   c
    //    \ /
    //     d
    const nodes: NodeDef[] = [
      { id: "a", type: "shell" },
      { id: "b", type: "shell", depends_on: ["a"] },
      { id: "c", type: "shell", depends_on: ["a"] },
      { id: "d", type: "shell", depends_on: ["b", "c"] },
    ];
    const result = topologicalSort(nodes);
    expect(result.length).toBe(4);
    // a must come before b and c
    expect(result.indexOf("a")).toBeLessThan(result.indexOf("b"));
    expect(result.indexOf("a")).toBeLessThan(result.indexOf("c"));
    // b and c must come before d
    expect(result.indexOf("b")).toBeLessThan(result.indexOf("d"));
    expect(result.indexOf("c")).toBeLessThan(result.indexOf("d"));
  });

  test("handles independent nodes (all parallel)", () => {
    const nodes: NodeDef[] = [
      { id: "a", type: "shell" },
      { id: "b", type: "shell" },
      { id: "c", type: "shell" },
    ];
    const result = topologicalSort(nodes);
    expect(result.length).toBe(3);
    expect(result).toContain("a");
    expect(result).toContain("b");
    expect(result).toContain("c");
  });

  test("throws on cycle", () => {
    const nodes: NodeDef[] = [
      { id: "a", type: "shell", depends_on: ["b"] },
      { id: "b", type: "shell", depends_on: ["a"] },
    ];
    expect(() => topologicalSort(nodes)).toThrow("Cycle detected in DAG");
  });

  test("throws on self-cycle", () => {
    const nodes: NodeDef[] = [
      { id: "a", type: "shell", depends_on: ["a"] },
    ];
    expect(() => topologicalSort(nodes)).toThrow();
  });

  test("throws on missing dependency", () => {
    const nodes: NodeDef[] = [
      { id: "a", type: "shell", depends_on: ["nonexistent"] },
    ];
    expect(() => topologicalSort(nodes)).toThrow("depends on unknown node");
  });

  test("handles complex DAG", () => {
    // a -> b -> d
    // a -> c -> d
    // d -> e
    const nodes: NodeDef[] = [
      { id: "a", type: "shell" },
      { id: "b", type: "shell", depends_on: ["a"] },
      { id: "c", type: "shell", depends_on: ["a"] },
      { id: "d", type: "shell", depends_on: ["b", "c"] },
      { id: "e", type: "shell", depends_on: ["d"] },
    ];
    const result = topologicalSort(nodes);
    expect(result.length).toBe(5);
    expect(result[0]).toBe("a");
    expect(result[4]).toBe("e");
    expect(result.indexOf("d")).toBeLessThan(result.indexOf("e"));
  });
});

describe("identifyParallelGroups", () => {
  test("returns empty array for empty input", () => {
    expect(identifyParallelGroups([])).toEqual([]);
  });

  test("single node in its own group", () => {
    const result = identifyParallelGroups([{ id: "a", type: "shell" }]);
    expect(result).toEqual([["a"]]);
  });

  test("independent nodes are in the same group", () => {
    const nodes: NodeDef[] = [
      { id: "a", type: "shell" },
      { id: "b", type: "shell" },
      { id: "c", type: "shell" },
    ];
    const result = identifyParallelGroups(nodes);
    expect(result.length).toBe(1);
    expect(result[0].sort()).toEqual(["a", "b", "c"]);
  });

  test("sequential nodes are in different groups", () => {
    const nodes: NodeDef[] = [
      { id: "a", type: "shell" },
      { id: "b", type: "shell", depends_on: ["a"] },
      { id: "c", type: "shell", depends_on: ["b"] },
    ];
    const result = identifyParallelGroups(nodes);
    expect(result.length).toBe(3);
    expect(result[0]).toEqual(["a"]);
    expect(result[1]).toEqual(["b"]);
    expect(result[2]).toEqual(["c"]);
  });

  test("diamond shape groups correctly", () => {
    //     a
    //    / \
    //   b   c
    //    \ /
    //     d
    const nodes: NodeDef[] = [
      { id: "a", type: "shell" },
      { id: "b", type: "shell", depends_on: ["a"] },
      { id: "c", type: "shell", depends_on: ["a"] },
      { id: "d", type: "shell", depends_on: ["b", "c"] },
    ];
    const result = identifyParallelGroups(nodes);
    expect(result.length).toBe(3);
    expect(result[0]).toEqual(["a"]);
    expect(result[1].sort()).toEqual(["b", "c"]);
    expect(result[2]).toEqual(["d"]);
  });

  test("throws on cycle", () => {
    const nodes: NodeDef[] = [
      { id: "a", type: "shell", depends_on: ["b"] },
      { id: "b", type: "shell", depends_on: ["a"] },
    ];
    expect(() => identifyParallelGroups(nodes)).toThrow("Cycle detected in DAG");
  });

  test("throws on missing dependency", () => {
    const nodes: NodeDef[] = [
      { id: "a", type: "shell", depends_on: ["ghost"] },
    ];
    expect(() => identifyParallelGroups(nodes)).toThrow("depends on unknown node");
  });

  test("complex multi-level parallelism", () => {
    // a, b (parallel) -> c, d (parallel) -> e
    const nodes: NodeDef[] = [
      { id: "a", type: "shell" },
      { id: "b", type: "shell" },
      { id: "c", type: "shell", depends_on: ["a", "b"] },
      { id: "d", type: "shell", depends_on: ["a", "b"] },
      { id: "e", type: "shell", depends_on: ["c", "d"] },
    ];
    const result = identifyParallelGroups(nodes);
    expect(result.length).toBe(3);
    expect(result[0].sort()).toEqual(["a", "b"]);
    expect(result[1].sort()).toEqual(["c", "d"]);
    expect(result[2]).toEqual(["e"]);
  });
});

describe("buildReverseAdjacency", () => {
  test("returns empty map for empty input", () => {
    const result = buildReverseAdjacency([]);
    expect(result.size).toBe(0);
  });

  test("single node with no dependencies", () => {
    const result = buildReverseAdjacency([{ id: "a", type: "shell" }]);
    expect(result.get("a")).toEqual([]);
  });

  test("maps downstream correctly", () => {
    // a -> b -> c
    const nodes: NodeDef[] = [
      { id: "a", type: "shell" },
      { id: "b", type: "shell", depends_on: ["a"] },
      { id: "c", type: "shell", depends_on: ["b"] },
    ];
    const result = buildReverseAdjacency(nodes);
    expect(result.get("a")).toEqual(["b"]);
    expect(result.get("b")).toEqual(["c"]);
    expect(result.get("c")).toEqual([]);
  });

  test("diamond shape downstream", () => {
    // a -> b, c -> d
    const nodes: NodeDef[] = [
      { id: "a", type: "shell" },
      { id: "b", type: "shell", depends_on: ["a"] },
      { id: "c", type: "shell", depends_on: ["a"] },
      { id: "d", type: "shell", depends_on: ["b", "c"] },
    ];
    const result = buildReverseAdjacency(nodes);
    expect(result.get("a")!.sort()).toEqual(["b", "c"]);
    expect(result.get("b")).toEqual(["d"]);
    expect(result.get("c")).toEqual(["d"]);
    expect(result.get("d")).toEqual([]);
  });

  test("handles node with multiple downstream dependents", () => {
    const nodes: NodeDef[] = [
      { id: "root", type: "shell" },
      { id: "child1", type: "shell", depends_on: ["root"] },
      { id: "child2", type: "shell", depends_on: ["root"] },
      { id: "child3", type: "shell", depends_on: ["root"] },
    ];
    const result = buildReverseAdjacency(nodes);
    expect(result.get("root")!.sort()).toEqual(["child1", "child2", "child3"]);
  });

  test("handles unknown dependency gracefully", () => {
    // buildReverseAdjacency doesn't throw for unknown deps — it creates entry
    const nodes: NodeDef[] = [
      { id: "a", type: "shell", depends_on: ["unknown"] },
    ];
    const result = buildReverseAdjacency(nodes);
    expect(result.get("a")).toEqual([]);
    expect(result.get("unknown")).toEqual(["a"]);
  });
});
