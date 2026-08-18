import { describe, test, expect } from "bun:test";

// ========== Pure function copies from packages/orchestration/src/errors.ts ==========

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

// ========== Tests ==========

describe("OrchestrationError", () => {
  test("has correct name, code, and message", () => {
    const err = new OrchestrationError("test error", "TEST_CODE");
    expect(err.name).toBe("OrchestrationError");
    expect(err.code).toBe("TEST_CODE");
    expect(err.message).toBe("test error");
  });

  test("is instanceof Error", () => {
    const err = new OrchestrationError("msg", "CODE");
    expect(err instanceof Error).toBe(true);
  });

  test("is instanceof OrchestrationError", () => {
    const err = new OrchestrationError("msg", "CODE");
    expect(err instanceof OrchestrationError).toBe(true);
  });

  test("has a stack trace", () => {
    const err = new OrchestrationError("msg", "CODE");
    expect(err.stack).toBeDefined();
    expect(typeof err.stack).toBe("string");
  });
});

describe("AgentNodeUnavailableError", () => {
  test("has correct default message", () => {
    const err = new AgentNodeUnavailableError();
    expect(err.message).toBe("Agent node is unavailable");
  });

  test("has correct code", () => {
    const err = new AgentNodeUnavailableError();
    expect(err.code).toBe("AGENT_NODE_UNAVAILABLE");
  });

  test("has correct name", () => {
    const err = new AgentNodeUnavailableError();
    expect(err.name).toBe("AgentNodeUnavailableError");
  });

  test("accepts custom message", () => {
    const err = new AgentNodeUnavailableError("Custom message");
    expect(err.message).toBe("Custom message");
  });

  test("is instanceof OrchestrationError", () => {
    const err = new AgentNodeUnavailableError();
    expect(err instanceof OrchestrationError).toBe(true);
  });

  test("is instanceof Error", () => {
    const err = new AgentNodeUnavailableError();
    expect(err instanceof Error).toBe(true);
  });
});

describe("IllegalStateTransitionError", () => {
  test("has correct default message", () => {
    const err = new IllegalStateTransitionError();
    expect(err.message).toBe("Illegal state transition");
  });

  test("has correct code", () => {
    const err = new IllegalStateTransitionError();
    expect(err.code).toBe("ILLEGAL_STATE_TRANSITION");
  });

  test("has correct name", () => {
    const err = new IllegalStateTransitionError();
    expect(err.name).toBe("IllegalStateTransitionError");
  });

  test("accepts custom message", () => {
    const err = new IllegalStateTransitionError("bad transition");
    expect(err.message).toBe("bad transition");
  });

  test("is instanceof OrchestrationError", () => {
    const err = new IllegalStateTransitionError();
    expect(err instanceof OrchestrationError).toBe(true);
  });

  test("is instanceof Error", () => {
    const err = new IllegalStateTransitionError();
    expect(err instanceof Error).toBe(true);
  });
});

describe("ConcurrencyExceededError", () => {
  test("has correct default message", () => {
    const err = new ConcurrencyExceededError();
    expect(err.message).toBe("Concurrency limit exceeded");
  });

  test("has correct code", () => {
    const err = new ConcurrencyExceededError();
    expect(err.code).toBe("CONCURRENCY_EXCEEDED");
  });

  test("has correct name", () => {
    const err = new ConcurrencyExceededError();
    expect(err.name).toBe("ConcurrencyExceededError");
  });

  test("accepts custom message", () => {
    const err = new ConcurrencyExceededError("max 10 concurrent sessions exceeded");
    expect(err.message).toBe("max 10 concurrent sessions exceeded");
    expect(err.code).toBe("CONCURRENCY_EXCEEDED");
  });

  test("is instanceof OrchestrationError", () => {
    const err = new ConcurrencyExceededError();
    expect(err instanceof OrchestrationError).toBe(true);
  });

  test("is instanceof Error", () => {
    const err = new ConcurrencyExceededError();
    expect(err instanceof Error).toBe(true);
  });
});

describe("MachineOfflineError", () => {
  test("has correct default message", () => {
    const err = new MachineOfflineError();
    expect(err.message).toBe("Target machine is offline");
  });

  test("has correct code", () => {
    const err = new MachineOfflineError();
    expect(err.code).toBe("MACHINE_OFFLINE");
  });

  test("has correct name", () => {
    const err = new MachineOfflineError();
    expect(err.name).toBe("MachineOfflineError");
  });

  test("accepts custom message", () => {
    const err = new MachineOfflineError("machine node-42 is offline");
    expect(err.message).toBe("machine node-42 is offline");
    expect(err.code).toBe("MACHINE_OFFLINE");
  });

  test("is instanceof OrchestrationError", () => {
    const err = new MachineOfflineError();
    expect(err instanceof OrchestrationError).toBe(true);
  });

  test("is instanceof Error", () => {
    const err = new MachineOfflineError();
    expect(err instanceof Error).toBe(true);
  });
});

describe("LaunchSpecBuildError", () => {
  test("has correct default message", () => {
    const err = new LaunchSpecBuildError();
    expect(err.message).toBe("Failed to build launch spec");
  });

  test("has correct code", () => {
    const err = new LaunchSpecBuildError();
    expect(err.code).toBe("LAUNCH_SPEC_BUILD_FAILED");
  });

  test("has correct name", () => {
    const err = new LaunchSpecBuildError();
    expect(err.name).toBe("LaunchSpecBuildError");
  });

  test("accepts custom message", () => {
    const err = new LaunchSpecBuildError("missing required tool: node-xyz");
    expect(err.message).toBe("missing required tool: node-xyz");
    expect(err.code).toBe("LAUNCH_SPEC_BUILD_FAILED");
  });

  test("is instanceof OrchestrationError", () => {
    const err = new LaunchSpecBuildError();
    expect(err instanceof OrchestrationError).toBe(true);
  });

  test("is instanceof Error", () => {
    const err = new LaunchSpecBuildError();
    expect(err instanceof Error).toBe(true);
  });
});

describe("EnvironmentNotFoundError", () => {
  test("has correct default message", () => {
    const err = new EnvironmentNotFoundError();
    expect(err.message).toBe("Environment not found");
  });

  test("has correct code", () => {
    const err = new EnvironmentNotFoundError();
    expect(err.code).toBe("ENVIRONMENT_NOT_FOUND");
  });

  test("has correct name", () => {
    const err = new EnvironmentNotFoundError();
    expect(err.name).toBe("EnvironmentNotFoundError");
  });

  test("accepts custom message", () => {
    const err = new EnvironmentNotFoundError("Env xyz missing");
    expect(err.message).toBe("Env xyz missing");
    expect(err.code).toBe("ENVIRONMENT_NOT_FOUND");
  });

  test("is instanceof OrchestrationError", () => {
    const err = new EnvironmentNotFoundError();
    expect(err instanceof OrchestrationError).toBe(true);
  });

  test("is instanceof Error", () => {
    const err = new EnvironmentNotFoundError();
    expect(err instanceof Error).toBe(true);
  });
});

describe("error hierarchy", () => {
  test("all errors extend OrchestrationError", () => {
    const errors = [
      new AgentNodeUnavailableError(),
      new IllegalStateTransitionError(),
      new ConcurrencyExceededError(),
      new MachineOfflineError(),
      new LaunchSpecBuildError(),
      new EnvironmentNotFoundError(),
    ];
    for (const err of errors) {
      expect(err instanceof OrchestrationError).toBe(true);
      expect(err instanceof Error).toBe(true);
      expect(typeof err.code).toBe("string");
      expect(err.code.length).toBeGreaterThan(0);
    }
  });

  test("each error has a unique code", () => {
    const errors = [
      new AgentNodeUnavailableError(),
      new IllegalStateTransitionError(),
      new ConcurrencyExceededError(),
      new MachineOfflineError(),
      new LaunchSpecBuildError(),
      new EnvironmentNotFoundError(),
    ];
    const codes = errors.map((e) => e.code);
    const uniqueCodes = new Set(codes);
    expect(uniqueCodes.size).toBe(codes.length);
  });

  test("each error has its own class name", () => {
    expect(new AgentNodeUnavailableError().name).toBe("AgentNodeUnavailableError");
    expect(new IllegalStateTransitionError().name).toBe("IllegalStateTransitionError");
    expect(new ConcurrencyExceededError().name).toBe("ConcurrencyExceededError");
    expect(new MachineOfflineError().name).toBe("MachineOfflineError");
    expect(new LaunchSpecBuildError().name).toBe("LaunchSpecBuildError");
    expect(new EnvironmentNotFoundError().name).toBe("EnvironmentNotFoundError");
  });
});
