// system-people-tree-service.test.ts — 人员树构建逻辑测试
// 测试目标：组织→用户→智能体树的内存聚合逻辑

import { describe, expect, test } from "bun:test";

// ── 复制树构建的纯逻辑部分（隔离 DB 依赖）──

interface SystemPeopleAgent {
  id: string;
  name: string;
  description: string | null;
  machineId: string | null;
  engineType: string | null;
}

interface SystemPeopleUser {
  id: string;
  name: string;
  email: string;
  phoneNumber: string | null;
  role: string | null;
  agents: SystemPeopleAgent[];
}

interface SystemPeopleOrganization {
  id: string;
  name: string;
  slug: string;
  users: SystemPeopleUser[];
}

interface MemberRow {
  id: string;
  name: string;
  email: string;
  phoneNumber: string | null;
  role: string;
}

interface AgentRow {
  id: string;
  userId: string;
  name: string;
  description: string | null;
  machineId: string | null;
  engineType: string | null;
  userName: string;
  userEmail: string;
  userPhoneNumber: string | null;
}

/** 纯函数：从 members 和 agents 行构建组织树节点 */
function buildOrganizationUsers(members: MemberRow[], agents: AgentRow[]): SystemPeopleUser[] {
  const users = new Map<string, SystemPeopleUser>(
    members.map((item) => [
      item.id,
      {
        id: item.id,
        name: item.name,
        email: item.email,
        phoneNumber: item.phoneNumber,
        role: item.role,
        agents: [],
      },
    ]),
  );

  for (const agent of agents) {
    const current = users.get(agent.userId);
    const target = current ?? {
      id: agent.userId,
      name: agent.userName,
      email: agent.userEmail,
      phoneNumber: agent.userPhoneNumber,
      role: null,
      agents: [],
    };
    target.agents.push({
      id: agent.id,
      name: agent.name,
      description: agent.description,
      machineId: agent.machineId,
      engineType: agent.engineType,
    });
    users.set(agent.userId, target);
  }

  return [...users.values()].sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
}

// ── Tests ──

describe("system-people-tree-service", () => {
  describe("buildOrganizationUsers", () => {
    test("空成员空智能体返回空数组", () => {
      const result = buildOrganizationUsers([], []);
      expect(result).toEqual([]);
    });

    test("只有成员无智能体", () => {
      const members: MemberRow[] = [
        { id: "u1", name: "Alice", email: "alice@test.com", phoneNumber: null, role: "owner" },
        { id: "u2", name: "Bob", email: "bob@test.com", phoneNumber: "13800000001", role: "member" },
      ];
      const result = buildOrganizationUsers(members, []);
      expect(result.length).toBe(2);
      // 按 name 排序
      expect(result[0].name).toBe("Alice");
      expect(result[1].name).toBe("Bob");
      expect(result[0].agents).toEqual([]);
    });

    test("智能体归属到对应成员", () => {
      const members: MemberRow[] = [
        { id: "u1", name: "Alice", email: "alice@test.com", phoneNumber: null, role: "owner" },
      ];
      const agents: AgentRow[] = [
        {
          id: "a1", userId: "u1", name: "Agent-1", description: "desc-1",
          machineId: "m1", engineType: "claude-code", userName: "Alice", userEmail: "alice@test.com", userPhoneNumber: null,
        },
      ];
      const result = buildOrganizationUsers(members, agents);
      expect(result.length).toBe(1);
      expect(result[0].agents.length).toBe(1);
      expect(result[0].agents[0].name).toBe("Agent-1");
    });

    test("非成员的智能体 owner 被加入（role=null）", () => {
      const members: MemberRow[] = [];
      const agents: AgentRow[] = [
        {
          id: "a1", userId: "orphan-user", name: "Orphan-Agent", description: null,
          machineId: null, engineType: null, userName: "Orphan", userEmail: "orphan@test.com", userPhoneNumber: null,
        },
      ];
      const result = buildOrganizationUsers(members, agents);
      expect(result.length).toBe(1);
      expect(result[0].id).toBe("orphan-user");
      expect(result[0].name).toBe("Orphan");
      expect(result[0].role).toBeNull();
      expect(result[0].agents.length).toBe(1);
    });

    test("同用户多智能体聚合到同一用户下", () => {
      const members: MemberRow[] = [
        { id: "u1", name: "Alice", email: "alice@test.com", phoneNumber: null, role: "owner" },
      ];
      const agents: AgentRow[] = [
        {
          id: "a1", userId: "u1", name: "Agent-A", description: null,
          machineId: null, engineType: null, userName: "Alice", userEmail: "alice@test.com", userPhoneNumber: null,
        },
        {
          id: "a2", userId: "u1", name: "Agent-B", description: "second",
          machineId: "m2", engineType: "opencode", userName: "Alice", userEmail: "alice@test.com", userPhoneNumber: null,
        },
      ];
      const result = buildOrganizationUsers(members, agents);
      expect(result.length).toBe(1);
      expect(result[0].agents.length).toBe(2);
    });

    test("用户按 name 排序", () => {
      const members: MemberRow[] = [
        { id: "u3", name: "Charlie", email: "c@test.com", phoneNumber: null, role: "member" },
        { id: "u1", name: "Alice", email: "a@test.com", phoneNumber: null, role: "owner" },
        { id: "u2", name: "Bob", email: "b@test.com", phoneNumber: null, role: "admin" },
      ];
      const result = buildOrganizationUsers(members, []);
      expect(result.map((u) => u.name)).toEqual(["Alice", "Bob", "Charlie"]);
    });

    test("同名用户按 id 排序", () => {
      const members: MemberRow[] = [
        { id: "u-b", name: "Same", email: "b@test.com", phoneNumber: null, role: "member" },
        { id: "u-a", name: "Same", email: "a@test.com", phoneNumber: null, role: "member" },
      ];
      const result = buildOrganizationUsers(members, []);
      expect(result[0].id).toBe("u-a");
      expect(result[1].id).toBe("u-b");
    });

    test("成员与智能体 owner 并集（member 用户也有 agent）", () => {
      const members: MemberRow[] = [
        { id: "u1", name: "Alice", email: "alice@test.com", phoneNumber: null, role: "owner" },
        { id: "u2", name: "Bob", email: "bob@test.com", phoneNumber: null, role: "member" },
      ];
      const agents: AgentRow[] = [
        {
          id: "a1", userId: "u1", name: "Alice-Agent", description: null,
          machineId: null, engineType: null, userName: "Alice", userEmail: "alice@test.com", userPhoneNumber: null,
        },
        {
          id: "a2", userId: "u3", name: "NonMember-Agent", description: null,
          machineId: null, engineType: null, userName: "NonMember", userEmail: "nm@test.com", userPhoneNumber: null,
        },
      ];
      const result = buildOrganizationUsers(members, agents);
      expect(result.length).toBe(3);
      const names = result.map((u) => u.name);
      expect(names).toContain("Alice");
      expect(names).toContain("Bob");
      expect(names).toContain("NonMember");
    });

    test("phoneNumber 正确透传", () => {
      const members: MemberRow[] = [
        { id: "u1", name: "Phone", email: "p@test.com", phoneNumber: "13900001111", role: "member" },
      ];
      const result = buildOrganizationUsers(members, []);
      expect(result[0].phoneNumber).toBe("13900001111");
    });
  });
});
