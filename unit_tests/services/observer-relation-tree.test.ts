// observer-relation-tree.test.ts — Observer 关系树组装测试
// 测试目标：buildRelationTree 的 byOrg/byEntity/integrity 分组正确性
// 业务意图：确保观察数据按 org→user→agent→instance 层级正确组装

import { describe, test, expect } from "bun:test";

// ── 复制纯函数（来自 src/services/observer/relation-tree.ts + types.ts）──

interface Observation {
  id: string;
  kind: string;
  entityIds: { role: string; id: string }[];
  source: string;
  ts: number;
  payload?: Record<string, unknown>;
  verified?: boolean;
}

interface LeafView {
  id: string;
  source: string;
  machineId: string | null;
  payload?: Record<string, unknown>;
}

interface InstanceNodeView {
  instanceId: string;
  leafCount: number;
  leaves: LeafView[];
}

interface AgentNodeView {
  agentConfigId: string;
  instanceCount: number;
  leafCount: number;
  children: InstanceNodeView[];
  leaves?: LeafView[];
}

interface UserNodeView {
  userId: string;
  agentCount: number;
  leafCount: number;
  children: AgentNodeView[];
}

interface OrgNodeView {
  organizationId: string;
  userCount: number;
  agentCount: number;
  instanceCount: number;
  leafCount: number;
  children: UserNodeView[];
}

interface MachineTreeLeaf {
  id: string;
  source: string;
  roleId: string;
}

interface MachineTreeView {
  machineId: string;
  count: number;
  leaves: MachineTreeLeaf[];
}

interface IntegritySummary {
  checked: number;
  mismatched: number;
  mismatchedItems: { kind: string; id: string }[];
}

interface ObservationNames {
  organizationId: Record<string, string>;
  userId: Record<string, string>;
  agentConfigId: Record<string, string>;
  instanceId: Record<string, string>;
  machineId: Record<string, string>;
}

const EMPTY_OBSERVATION_NAMES: ObservationNames = {
  organizationId: {},
  userId: {},
  agentConfigId: {},
  instanceId: {},
  machineId: {},
};

interface RelationTreeView {
  generatedAt: string;
  kind: string;
  total: number;
  byOrg: OrgNodeView[];
  byEntity: MachineTreeView[];
  integrity: IntegritySummary;
  names: ObservationNames;
}

function buildRoleMap(observation: Observation): Map<string, string> {
  const roles = new Map<string, string>();
  for (const { role, id } of observation.entityIds) {
    if (!roles.has(role)) roles.set(role, id);
  }
  return roles;
}

interface AgentAcc {
  node: AgentNodeView;
  leafIds: Set<string>;
  instances: Map<string, InstanceNodeView>;
}
interface UserAcc {
  node: UserNodeView;
  leafIds: Set<string>;
  agents: Map<string, AgentAcc>;
}
interface OrgAcc {
  node: OrgNodeView;
  leafIds: Set<string>;
  users: Map<string, UserAcc>;
}

function sortedBy<T>(items: T[], key: (item: T) => string): T[] {
  return [...items].sort((a, b) => key(a).localeCompare(key(b)));
}

function buildByOrg(observations: Observation[]): OrgNodeView[] {
  const orgs = new Map<string, OrgAcc>();

  for (const observation of observations) {
    const roles = buildRoleMap(observation);
    const orgId = roles.get("organizationId");
    if (!orgId) continue;
    const userId = roles.get("userId");
    const agentConfigId = roles.get("agentConfigId");
    const instanceId = roles.get("instanceId");

    const leaf: LeafView = {
      id: observation.id,
      source: observation.source,
      machineId: roles.get("machineId") ?? null,
      ...(observation.payload ? { payload: observation.payload } : {}),
    };

    if (!agentConfigId) continue;

    let orgAcc = orgs.get(orgId);
    if (!orgAcc) {
      orgAcc = {
        node: { organizationId: orgId, userCount: 0, agentCount: 0, instanceCount: 0, leafCount: 0, children: [] },
        leafIds: new Set(),
        users: new Map(),
      };
      orgs.set(orgId, orgAcc);
    }
    orgAcc.leafIds.add(observation.id);

    if (!userId) continue;
    let userAcc = orgAcc.users.get(userId);
    if (!userAcc) {
      userAcc = { node: { userId, agentCount: 0, leafCount: 0, children: [] }, leafIds: new Set(), agents: new Map() };
      orgAcc.users.set(userId, userAcc);
    }
    userAcc.leafIds.add(observation.id);

    let agentAcc = userAcc.agents.get(agentConfigId);
    if (!agentAcc) {
      agentAcc = {
        node: { agentConfigId, instanceCount: 0, leafCount: 0, children: [], leaves: undefined },
        leafIds: new Set(),
        instances: new Map(),
      };
      userAcc.agents.set(agentConfigId, agentAcc);
    }
    agentAcc.leafIds.add(observation.id);

    if (instanceId) {
      let instance = agentAcc.instances.get(instanceId);
      if (!instance) {
        instance = { instanceId, leafCount: 0, leaves: [] };
        agentAcc.instances.set(instanceId, instance);
      }
      instance.leaves.push(leaf);
    } else {
      agentAcc.node.leaves ??= [];
      agentAcc.node.leaves.push(leaf);
    }
  }

  const out: OrgNodeView[] = [];
  for (const orgAcc of orgs.values()) {
    const { node: orgNode } = orgAcc;
    const users = sortedBy([...orgAcc.users.values()], (u) => u.node.userId);
    orgNode.children = users.map((userAcc) => {
      const agents = sortedBy([...userAcc.agents.values()], (a) => a.node.agentConfigId);
      userAcc.node.children = agents.map((agentAcc) => {
        const instances = sortedBy([...agentAcc.instances.values()], (i) => i.instanceId);
        for (const instance of instances) {
          instance.leaves = sortedBy(instance.leaves, (l) => l.id);
          instance.leafCount = instance.leaves.length;
        }
        agentAcc.node.children = instances;
        agentAcc.node.instanceCount = instances.length;
        agentAcc.node.leafCount = agentAcc.leafIds.size;
        if (agentAcc.node.leaves) {
          agentAcc.node.leaves = sortedBy(agentAcc.node.leaves, (l) => l.id);
        }
        return agentAcc.node;
      });
      userAcc.node.agentCount = agents.length;
      userAcc.node.leafCount = userAcc.leafIds.size;
      return userAcc.node;
    });
    orgNode.userCount = users.length;
    orgNode.agentCount = users.reduce((sum, u) => sum + u.node.agentCount, 0);
    orgNode.instanceCount = orgNode.children.reduce((sum, u) => sum + u.children.reduce((s, a) => s + a.instanceCount, 0), 0);
    orgNode.leafCount = orgAcc.leafIds.size;
    out.push(orgNode);
  }
  return sortedBy(out, (o) => o.organizationId);
}

function buildByEntity(observations: Observation[]): MachineTreeView[] {
  const groups = new Map<string, MachineTreeView>();
  for (const observation of observations) {
    const machineId = buildRoleMap(observation).get("machineId");
    if (!machineId) continue;
    let group = groups.get(machineId);
    if (!group) {
      group = { machineId, count: 0, leaves: [] };
      groups.set(machineId, group);
    }
    group.leaves.push({ id: observation.id, source: observation.source, roleId: machineId });
  }
  const out = [...groups.values()];
  for (const group of out) {
    group.leaves = sortedBy(group.leaves, (l) => l.id);
    group.count = group.leaves.length;
  }
  return sortedBy(out, (g) => g.machineId);
}

function buildIntegrity(kind: string, observations: Observation[]): IntegritySummary {
  const mismatchedItems = observations
    .filter((o) => o.verified === false)
    .map((o) => ({ kind, id: o.id }));
  return { checked: observations.length, mismatched: mismatchedItems.length, mismatchedItems };
}

function buildRelationTree(kind: string, observations: Observation[], names: ObservationNames = EMPTY_OBSERVATION_NAMES): RelationTreeView {
  return {
    generatedAt: new Date().toISOString(),
    kind,
    total: observations.length,
    byOrg: buildByOrg(observations),
    byEntity: buildByEntity(observations),
    integrity: buildIntegrity(kind, observations),
    names,
  };
}

// ── 辅助 ──

function makeObservation(id: string, roles: Record<string, string>, verified?: boolean): Observation {
  return {
    id,
    kind: "acp-link",
    entityIds: Object.entries(roles).map(([role, id]) => ({ role, id })),
    source: "acp-ws",
    ts: Date.now(),
    ...(verified !== undefined ? { verified } : {}),
  };
}

// ── 测试 ──

describe("buildRelationTree", () => {
  test("正向 - 空观察返回空树", () => {
    const tree = buildRelationTree("acp-link", []);
    expect(tree.total).toBe(0);
    expect(tree.byOrg).toEqual([]);
    expect(tree.byEntity).toEqual([]);
    expect(tree.integrity.checked).toBe(0);
    expect(tree.integrity.mismatched).toBe(0);
  });

  test("正向 - kind 和 generatedAt 正确设置", () => {
    const tree = buildRelationTree("acp-link", []);
    expect(tree.kind).toBe("acp-link");
    expect(tree.generatedAt).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  test("正向 - total 等于观察数", () => {
    const obs = [
      makeObservation("l1", { organizationId: "o1", userId: "u1", agentConfigId: "a1" }),
      makeObservation("l2", { organizationId: "o1", userId: "u1", agentConfigId: "a1" }),
    ];
    expect(buildRelationTree("acp-link", obs).total).toBe(2);
  });
});

describe("buildByOrg", () => {
  test("正向 - 按 org→user→agent→instance 分层", () => {
    const obs = [
      makeObservation("l1", { organizationId: "o1", userId: "u1", agentConfigId: "a1", instanceId: "i1", machineId: "m1" }),
    ];
    const tree = buildRelationTree("acp-link", obs);
    expect(tree.byOrg.length).toBe(1);
    expect(tree.byOrg[0].organizationId).toBe("o1");
    expect(tree.byOrg[0].children.length).toBe(1);
    expect(tree.byOrg[0].children[0].userId).toBe("u1");
    expect(tree.byOrg[0].children[0].children[0].agentConfigId).toBe("a1");
    expect(tree.byOrg[0].children[0].children[0].children[0].instanceId).toBe("i1");
  });

  test("正向 - 同一 org 多 user 分组", () => {
    const obs = [
      makeObservation("l1", { organizationId: "o1", userId: "u1", agentConfigId: "a1", instanceId: "i1", machineId: "m1" }),
      makeObservation("l2", { organizationId: "o1", userId: "u2", agentConfigId: "a2", instanceId: "i2", machineId: "m2" }),
    ];
    const tree = buildRelationTree("acp-link", obs);
    expect(tree.byOrg[0].userCount).toBe(2);
  });

  test("正向 - 无 instanceId 的叶子挂在 agent 节点", () => {
    const obs = [
      makeObservation("l1", { organizationId: "o1", userId: "u1", agentConfigId: "a1", machineId: "m1" }),
    ];
    const tree = buildRelationTree("acp-link", obs);
    const agent = tree.byOrg[0].children[0].children[0];
    expect(agent.instanceCount).toBe(0);
    expect(agent.leaves!.length).toBe(1);
    expect(agent.leaves![0].id).toBe("l1");
  });

  test("分支 - 无 org 的观察不进 byOrg", () => {
    const obs = [makeObservation("l1", { machineId: "m1" })];
    const tree = buildRelationTree("acp-link", obs);
    expect(tree.byOrg).toEqual([]);
    expect(tree.total).toBe(1);
  });

  test("分支 - 无 agentConfigId 的观察不进 byOrg 但有 total", () => {
    const obs = [makeObservation("l1", { organizationId: "o1", userId: "u1" })];
    const tree = buildRelationTree("acp-link", obs);
    expect(tree.byOrg).toEqual([]);
    expect(tree.total).toBe(1);
  });

  test("正向 - leafCount 正确汇总", () => {
    const obs = [
      makeObservation("l1", { organizationId: "o1", userId: "u1", agentConfigId: "a1", instanceId: "i1", machineId: "m1" }),
      makeObservation("l2", { organizationId: "o1", userId: "u1", agentConfigId: "a1", instanceId: "i1", machineId: "m1" }),
    ];
    const tree = buildRelationTree("acp-link", obs);
    expect(tree.byOrg[0].leafCount).toBe(2);
    expect(tree.byOrg[0].children[0].leafCount).toBe(2);
    expect(tree.byOrg[0].children[0].children[0].leafCount).toBe(2);
  });
});

describe("buildByEntity", () => {
  test("正向 - 按 machineId 分组", () => {
    const obs = [
      makeObservation("l1", { machineId: "m1" }),
      makeObservation("l2", { machineId: "m1" }),
      makeObservation("l3", { machineId: "m2" }),
    ];
    const tree = buildRelationTree("acp-link", obs);
    expect(tree.byEntity.length).toBe(2);
    expect(tree.byEntity[0].machineId).toBe("m1");
    expect(tree.byEntity[0].count).toBe(2);
    expect(tree.byEntity[1].machineId).toBe("m2");
    expect(tree.byEntity[1].count).toBe(1);
  });

  test("正向 - 叶子 roleId 等于 machineId", () => {
    const obs = [makeObservation("l1", { machineId: "m1" })];
    const tree = buildRelationTree("acp-link", obs);
    expect(tree.byEntity[0].leaves[0].roleId).toBe("m1");
  });

  test("分支 - 无 machineId 的观察不进 byEntity", () => {
    const obs = [makeObservation("l1", { organizationId: "o1", userId: "u1", agentConfigId: "a1" })];
    const tree = buildRelationTree("acp-link", obs);
    expect(tree.byEntity).toEqual([]);
  });
});

describe("buildIntegrity", () => {
  test("正向 - checked 等于观察总数", () => {
    const obs = [
      makeObservation("l1", { machineId: "m1" }),
      makeObservation("l2", { machineId: "m2" }),
    ];
    expect(buildRelationTree("acp-link", obs).integrity.checked).toBe(2);
  });

  test("正向 - verified===false 计入 mismatched", () => {
    const obs = [
      makeObservation("l1", { machineId: "m1" }, true),
      makeObservation("l2", { machineId: "m2" }, false),
    ];
    const summary = buildRelationTree("acp-link", obs).integrity;
    expect(summary.mismatched).toBe(1);
    expect(summary.mismatchedItems[0].id).toBe("l2");
    expect(summary.mismatchedItems[0].kind).toBe("acp-link");
  });

  test("分支 - verified===true 或 undefined 不计入 mismatched", () => {
    const obs = [
      makeObservation("l1", { machineId: "m1" }, true),
      makeObservation("l2", { machineId: "m2" }),
    ];
    expect(buildRelationTree("acp-link", obs).integrity.mismatched).toBe(0);
  });
});
