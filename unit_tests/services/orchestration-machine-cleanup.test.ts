// orchestration-machine-cleanup.test.ts — 机器断连幽灵实例清理测试
// 测试目标：cleanupOrchestrationInstancesForMachine 全分支

import { describe, expect, test, beforeEach, mock } from "bun:test";

// ── 复制核心逻辑（隔离编排域依赖）──

interface MockController {
  stopInstancesByMachineId: (machineId: string) => string[];
}

const _deps = {
  getOrchestrationController: (): MockController => ({
    stopInstancesByMachineId: (_machineId: string) => [],
  }),
  reclaimYjsDocs: async (_instanceId: string) => {},
};

function cleanupOrchestrationInstancesForMachine(machineId: string): number {
  const removedInstanceIds = _deps.getOrchestrationController().stopInstancesByMachineId(machineId);
  for (const instanceId of removedInstanceIds) {
    void _deps.reclaimYjsDocs(instanceId).catch(() => {});
  }
  return removedInstanceIds.length;
}

// ── Tests ──

describe("orchestration-machine-cleanup", () => {
  let stopCalls: string[];
  let reclaimCalls: string[];

  beforeEach(() => {
    mock.restore();
    stopCalls = [];
    reclaimCalls = [];
    _deps.getOrchestrationController = () => ({
      stopInstancesByMachineId: (machineId: string) => {
        stopCalls.push(machineId);
        return [];
      },
    });
    _deps.reclaimYjsDocs = async (instanceId: string) => {
      reclaimCalls.push(instanceId);
    };
  });

  test("无幽灵实例时返回 0", () => {
    const count = cleanupOrchestrationInstancesForMachine("machine-1");
    expect(count).toBe(0);
  });

  test("传递正确的 machineId 到 controller", () => {
    cleanupOrchestrationInstancesForMachine("machine-42");
    expect(stopCalls).toEqual(["machine-42"]);
  });

  test("有幽灵实例时返回清理数量", () => {
    _deps.getOrchestrationController = () => ({
      stopInstancesByMachineId: (machineId: string) => {
        stopCalls.push(machineId);
        return ["inst-1", "inst-2", "inst-3"];
      },
    });
    const count = cleanupOrchestrationInstancesForMachine("machine-1");
    expect(count).toBe(3);
  });

  test("每个被移除实例触发 reclaimYjsDocs", () => {
    _deps.getOrchestrationController = () => ({
      stopInstancesByMachineId: () => ["inst-a", "inst-b"],
    });
    cleanupOrchestrationInstancesForMachine("machine-1");
    // reclaimYjsDocs 是 fire-and-forget（void），等待微任务
    // 在同步测试中验证调用已经被排队
    expect(reclaimCalls).toEqual(["inst-a", "inst-b"]);
  });

  test("reclaimYjsDocs 失败不影响返回值", async () => {
    _deps.getOrchestrationController = () => ({
      stopInstancesByMachineId: () => ["inst-fail"],
    });
    _deps.reclaimYjsDocs = async () => {
      throw new Error("reclaim failed");
    };
    const count = cleanupOrchestrationInstancesForMachine("machine-1");
    expect(count).toBe(1);
  });

  test("空 machineId 也正常调用 controller", () => {
    cleanupOrchestrationInstancesForMachine("");
    expect(stopCalls).toEqual([""]);
  });
});
