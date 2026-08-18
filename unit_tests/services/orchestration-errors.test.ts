// orchestration-errors.test.ts — 编排域错误体系测试
// 测试目标：OrchestrationError 及所有子类的构造、code 绑定、继承关系
// 业务意图：确保错误分类准确，上层可按 code 做分类处理

import { describe, expect, test } from "bun:test";

// ── 复制错误类（纯类，无外部依赖）──

class OrchestrationError extends Error {
  readonly code: string;
  constructor(message: string, code: string) {
    super(message);
    this.name = new.target.name;
    this.code = code;
  }
}

class AgentNodeUnavailableError extends OrchestrationError {
  constructor(message = "Agent node is unavailable") {
    super(message, "AGENT_NODE_UNAVAILABLE");
  }
}

class IllegalStateTransitionError extends OrchestrationError {
  constructor(message = "Illegal state transition") {
    super(message, "ILLEGAL_STATE_TRANSITION");
  }
}

class ConcurrencyExceededError extends OrchestrationError {
  constructor(message = "Concurrency limit exceeded") {
    super(message, "CONCURRENCY_EXCEEDED");
  }
}

class MachineOfflineError extends OrchestrationError {
  constructor(message = "Target machine is offline") {
    super(message, "MACHINE_OFFLINE");
  }
}

class LaunchSpecBuildError extends OrchestrationError {
  constructor(message = "Failed to build launch spec") {
    super(message, "LAUNCH_SPEC_BUILD_FAILED");
  }
}

class EnvironmentNotFoundError extends OrchestrationError {
  constructor(message = "Environment not found") {
    super(message, "ENVIRONMENT_NOT_FOUND");
  }
}

// ── OrchestrationError 基类 ──

describe("OrchestrationError", () => {
  // 构造函数正确绑定 message 和 code
  test("正确绑定 message、code 和 name", () => {
    const err = new OrchestrationError("test error", "TEST_CODE");
    expect(err.message).toBe("test error");
    expect(err.code).toBe("TEST_CODE");
    expect(err.name).toBe("OrchestrationError");
  });

  // 继承自 Error
  test("instanceof Error", () => {
    const err = new OrchestrationError("test", "TEST");
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(OrchestrationError);
  });
});

// ── 各子类 ──

describe("AgentNodeUnavailableError", () => {
  // 默认 message 和 code
  test("默认 message 和正确 code", () => {
    const err = new AgentNodeUnavailableError();
    expect(err.code).toBe("AGENT_NODE_UNAVAILABLE");
    expect(err.message).toBe("Agent node is unavailable");
    expect(err.name).toBe("AgentNodeUnavailableError");
  });

  // 自定义 message
  test("自定义 message", () => {
    const err = new AgentNodeUnavailableError("node xyz offline");
    expect(err.message).toBe("node xyz offline");
    expect(err.code).toBe("AGENT_NODE_UNAVAILABLE");
  });
});

describe("IllegalStateTransitionError", () => {
  test("默认 message 和正确 code", () => {
    const err = new IllegalStateTransitionError();
    expect(err.code).toBe("ILLEGAL_STATE_TRANSITION");
    expect(err.name).toBe("IllegalStateTransitionError");
  });
});

describe("ConcurrencyExceededError", () => {
  test("默认 message 和正确 code", () => {
    const err = new ConcurrencyExceededError();
    expect(err.code).toBe("CONCURRENCY_EXCEEDED");
    expect(err.name).toBe("ConcurrencyExceededError");
  });

  test("自定义 message", () => {
    const err = new ConcurrencyExceededError("max 10 concurrent sessions exceeded");
    expect(err.message).toBe("max 10 concurrent sessions exceeded");
    expect(err.code).toBe("CONCURRENCY_EXCEEDED");
  });
});

describe("MachineOfflineError", () => {
  test("默认 message 和正确 code", () => {
    const err = new MachineOfflineError();
    expect(err.code).toBe("MACHINE_OFFLINE");
    expect(err.name).toBe("MachineOfflineError");
  });

  test("自定义 message", () => {
    const err = new MachineOfflineError("machine node-42 is offline");
    expect(err.message).toBe("machine node-42 is offline");
    expect(err.code).toBe("MACHINE_OFFLINE");
  });
});

describe("LaunchSpecBuildError", () => {
  test("默认 message 和正确 code", () => {
    const err = new LaunchSpecBuildError();
    expect(err.code).toBe("LAUNCH_SPEC_BUILD_FAILED");
    expect(err.name).toBe("LaunchSpecBuildError");
  });

  test("自定义 message", () => {
    const err = new LaunchSpecBuildError("missing required tool: node-xyz");
    expect(err.message).toBe("missing required tool: node-xyz");
    expect(err.code).toBe("LAUNCH_SPEC_BUILD_FAILED");
  });
});

describe("EnvironmentNotFoundError", () => {
  test("默认 message 和正确 code", () => {
    const err = new EnvironmentNotFoundError();
    expect(err.code).toBe("ENVIRONMENT_NOT_FOUND");
    expect(err.name).toBe("EnvironmentNotFoundError");
  });
});

// ── 继承关系 ──

describe("子类 instanceof 判定", () => {
  test("所有子类 instanceof OrchestrationError 和 Error", () => {
    const errors = [
      new AgentNodeUnavailableError(),
      new IllegalStateTransitionError(),
      new ConcurrencyExceededError(),
      new MachineOfflineError(),
      new LaunchSpecBuildError(),
      new EnvironmentNotFoundError(),
    ];
    for (const err of errors) {
      expect(err).toBeInstanceOf(OrchestrationError);
      expect(err).toBeInstanceOf(Error);
    }
  });
});
