// launch-spec-builder.test.ts — LaunchSpec 构建器测试
// 测试目标：LaunchSpecBuilder.build() 的正常流程和各类缺失字段错误
// 业务意图：确保启动实例前的规格构建完整校验，缺失环节准确报错

import { describe, expect, test } from "bun:test";

// ── 复制错误类 ──

class OrchestrationError extends Error {
  readonly code: string;
  constructor(message: string, code: string) {
    super(message);
    this.name = new.target.name;
    this.code = code;
  }
}

class LaunchSpecBuildError extends OrchestrationError {
  constructor(message = "Failed to build launch spec") {
    super(message, "LAUNCH_SPEC_BUILD_FAILED");
  }
}

// ── 复制 LaunchSpecBuilder（内联 Repo 接口）──

interface AgentConfigData {
  id: string;
  name: string;
  modelName: string;
  engineId: string;
}

interface AgentEngineData {
  id: string;
  type: string;
}

interface EnvironmentData {
  id: string;
  organizationId: string;
  agentConfigId: string | null;
}

interface AgentConfigRepo {
  getConfig(id: string): Promise<AgentConfigData | null>;
}
interface EnvironmentRepo {
  getEnvironment(id: string, userId: string): Promise<EnvironmentData | null>;
}
interface AgentEngineRepo {
  getEngine(id: string): Promise<AgentEngineData | null>;
}

interface LaunchSpecBuilderDeps {
  agentConfigRepo: AgentConfigRepo;
  environmentRepo: EnvironmentRepo;
  agentEngineRepo: AgentEngineRepo;
  workspaceRoot?: string;
}

interface LaunchSpec {
  environmentId: string;
  agentConfig: AgentConfigData;
  engine: AgentEngineData;
  cwd: string;
  userId: string;
}

class LaunchSpecBuilder {
  readonly #agentConfigRepo: AgentConfigRepo;
  readonly #environmentRepo: EnvironmentRepo;
  readonly #agentEngineRepo: AgentEngineRepo;
  readonly #workspaceRoot: string;

  constructor(deps: LaunchSpecBuilderDeps) {
    this.#agentConfigRepo = deps.agentConfigRepo;
    this.#environmentRepo = deps.environmentRepo;
    this.#agentEngineRepo = deps.agentEngineRepo;
    this.#workspaceRoot = deps.workspaceRoot ?? "workspaces";
  }

  async build(envId: string, userId: string): Promise<LaunchSpec> {
    const environment = await this.#environmentRepo.getEnvironment(envId, userId);
    if (environment === null) {
      throw new LaunchSpecBuildError(`Cannot build launch spec: environment '${envId}' not found`);
    }
    if (!environment.agentConfigId) {
      throw new LaunchSpecBuildError(
        `Cannot build launch spec: environment '${envId}' has no agentConfigId configured`,
      );
    }

    const agentConfig = await this.#agentConfigRepo.getConfig(environment.agentConfigId);
    if (agentConfig === null) {
      throw new LaunchSpecBuildError(
        `Cannot build launch spec: agent config '${environment.agentConfigId}' not found (referenced by environment '${envId}')`,
      );
    }
    const missingField = this.#findMissingConfigField(agentConfig);
    if (missingField !== null) {
      throw new LaunchSpecBuildError(
        `Cannot build launch spec: agent config '${agentConfig.id}' is missing required field '${missingField}'`,
      );
    }

    const engine = await this.#agentEngineRepo.getEngine(agentConfig.engineId);
    if (engine === null) {
      throw new LaunchSpecBuildError(
        `Cannot build launch spec: engine '${agentConfig.engineId}' not found (referenced by agent config '${agentConfig.id}')`,
      );
    }

    return {
      environmentId: envId,
      agentConfig,
      engine,
      cwd: `${this.#workspaceRoot}/${environment.organizationId}/${userId}/${envId}`,
      userId,
    };
  }

  #findMissingConfigField(config: { name: string; modelName: string; engineId: string }): string | null {
    const required: Record<keyof typeof config, string> = {
      name: "name",
      modelName: "modelName",
      engineId: "engineId",
    };
    for (const key of Object.keys(required) as (keyof typeof config)[]) {
      if (!config[key]) {
        return required[key];
      }
    }
    return null;
  }
}

// ── Mock 工厂 ──

function makeDeps(overrides: Partial<LaunchSpecBuilderDeps> = {}): LaunchSpecBuilderDeps {
  return {
    environmentRepo: {
      getEnvironment: async (id: string, _userId: string) => ({
        id,
        organizationId: "org-1",
        agentConfigId: "config-1",
      }),
    },
    agentConfigRepo: {
      getConfig: async (id: string) => ({
        id,
        name: "Test Agent",
        modelName: "claude-sonnet-4-20250514",
        engineId: "engine-1",
      }),
    },
    agentEngineRepo: {
      getEngine: async (id: string) => ({
        id,
        type: "claude-code",
      }),
    },
    ...overrides,
  };
}

// ── 正常流程 ──

describe("LaunchSpecBuilder.build 正常流程", () => {
  // 完整构建返回正确的 LaunchSpec
  test("正常构建返回完整 LaunchSpec", async () => {
    const builder = new LaunchSpecBuilder(makeDeps());
    const spec = await builder.build("env-1", "user-1");

    expect(spec.environmentId).toBe("env-1");
    expect(spec.userId).toBe("user-1");
    expect(spec.agentConfig.name).toBe("Test Agent");
    expect(spec.engine.type).toBe("claude-code");
  });

  // cwd 路径遵循 {workspaceRoot}/{orgId}/{userId}/{envId} 不变量
  test("cwd 遵循 workspace 路径不变量", async () => {
    const builder = new LaunchSpecBuilder(makeDeps());
    const spec = await builder.build("env-1", "user-1");
    expect(spec.cwd).toBe("workspaces/org-1/user-1/env-1");
  });

  // 自定义 workspaceRoot
  test("自定义 workspaceRoot 生效", async () => {
    const builder = new LaunchSpecBuilder(makeDeps({ workspaceRoot: "/data/ws" }));
    const spec = await builder.build("env-1", "user-1");
    expect(spec.cwd).toBe("/data/ws/org-1/user-1/env-1");
  });
});

// ── 环境缺失 ──

describe("LaunchSpecBuilder.build 环境缺失", () => {
  // 环境不存在时抛 LaunchSpecBuildError
  test("环境不存在时抛 LaunchSpecBuildError", async () => {
    const builder = new LaunchSpecBuilder(makeDeps({
      environmentRepo: {
        getEnvironment: async () => null,
      },
    }));

    expect(builder.build("env-missing", "user-1")).rejects.toThrow(LaunchSpecBuildError);
  });

  // 环境无 agentConfigId 时抛错
  test("环境无 agentConfigId 时抛 LaunchSpecBuildError", async () => {
    const builder = new LaunchSpecBuilder(makeDeps({
      environmentRepo: {
        getEnvironment: async (id: string) => ({
          id,
          organizationId: "org-1",
          agentConfigId: null,
        }),
      },
    }));

    try {
      await builder.build("env-1", "user-1");
      expect.unreachable("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(LaunchSpecBuildError);
      expect((err as LaunchSpecBuildError).message).toContain("no agentConfigId");
    }
  });
});

// ── Agent 配置缺失 ──

describe("LaunchSpecBuilder.build Agent 配置缺失", () => {
  // agent 配置不存在时抛错
  test("agent 配置不存在时抛 LaunchSpecBuildError", async () => {
    const builder = new LaunchSpecBuilder(makeDeps({
      agentConfigRepo: {
        getConfig: async () => null,
      },
    }));

    try {
      await builder.build("env-1", "user-1");
      expect.unreachable("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(LaunchSpecBuildError);
      expect((err as LaunchSpecBuildError).message).toContain("agent config");
    }
  });

  // agent 配置 name 为空时抛错
  test("agent 配置 name 为空时抛错", async () => {
    const builder = new LaunchSpecBuilder(makeDeps({
      agentConfigRepo: {
        getConfig: async (id: string) => ({
          id, name: "", modelName: "model", engineId: "eng-1",
        }),
      },
    }));

    try {
      await builder.build("env-1", "user-1");
      expect.unreachable("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(LaunchSpecBuildError);
      expect((err as LaunchSpecBuildError).message).toContain("name");
    }
  });

  // agent 配置 modelName 为空时抛错
  test("agent 配置 modelName 为空时抛错", async () => {
    const builder = new LaunchSpecBuilder(makeDeps({
      agentConfigRepo: {
        getConfig: async (id: string) => ({
          id, name: "Agent", modelName: "", engineId: "eng-1",
        }),
      },
    }));

    try {
      await builder.build("env-1", "user-1");
      expect.unreachable("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(LaunchSpecBuildError);
      expect((err as LaunchSpecBuildError).message).toContain("modelName");
    }
  });
});

// ── 引擎缺失 ──

describe("LaunchSpecBuilder.build 引擎缺失", () => {
  // 引擎不存在时抛错
  test("引擎不存在时抛 LaunchSpecBuildError", async () => {
    const builder = new LaunchSpecBuilder(makeDeps({
      agentEngineRepo: {
        getEngine: async () => null,
      },
    }));

    try {
      await builder.build("env-1", "user-1");
      expect.unreachable("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(LaunchSpecBuildError);
      expect((err as LaunchSpecBuildError).message).toContain("engine");
    }
  });
});

// ── 错误码校验 ──

describe("LaunchSpecBuilder.build 错误码", () => {
  // 所有错误统一为 LAUNCH_SPEC_BUILD_FAILED 码
  test("所有构建失败使用 LAUNCH_SPEC_BUILD_FAILED 错误码", async () => {
    const cases: LaunchSpecBuilderDeps[] = [
      makeDeps({ environmentRepo: { getEnvironment: async () => null } }),
      makeDeps({ agentConfigRepo: { getConfig: async () => null } }),
      makeDeps({ agentEngineRepo: { getEngine: async () => null } }),
    ];

    for (const deps of cases) {
      const builder = new LaunchSpecBuilder(deps);
      try {
        await builder.build("env-1", "user-1");
        expect.unreachable("should have thrown");
      } catch (err) {
        expect((err as LaunchSpecBuildError).code).toBe("LAUNCH_SPEC_BUILD_FAILED");
      }
    }
  });
});
