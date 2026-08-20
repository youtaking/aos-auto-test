// engine-plugin-registry.test.ts — Engine plugin 注册表测试
// 测试目标：register/get/require/list/has 行为正确性，重复注册拒绝
// 业务意图：确保引擎插件按 meta.id 唯一注册，查询稳定可断言

import { describe, test, expect, beforeEach } from "bun:test";

// ── 复制纯函数/类 ──

class CoreRuntimeError extends Error {
  readonly code: string;
  readonly details?: Record<string, unknown>;
  constructor(code: string, message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "CoreRuntimeError";
    this.code = code;
    this.details = details;
  }
}

function createCoreRuntimeError(code: string, message: string, details?: Record<string, unknown>) {
  return new CoreRuntimeError(code, message, details);
}

interface EnginePlugin {
  meta: { id: string; displayName: string; version: string };
  createRuntime: () => unknown;
}

class EnginePluginRegistry {
  private readonly plugins = new Map<string, EnginePlugin>();

  register(plugin: EnginePlugin): EnginePlugin {
    const engineType = plugin.meta.id;
    if (this.plugins.has(engineType)) {
      throw createCoreRuntimeError("DUPLICATE_ENGINE_PLUGIN", `Engine plugin already registered: ${engineType}`, {
        engineType,
      });
    }
    this.plugins.set(engineType, plugin);
    return plugin;
  }

  get(engineType: string): EnginePlugin | null {
    return this.plugins.get(engineType) ?? null;
  }

  require(engineType: string): EnginePlugin {
    const plugin = this.get(engineType);
    if (!plugin) {
      throw createCoreRuntimeError("PLUGIN_NOT_FOUND", `Engine plugin not found: ${engineType}`, { engineType });
    }
    return plugin;
  }

  list(): EnginePlugin[] {
    return [...this.plugins.values()];
  }

  has(engineType: string): boolean {
    return this.plugins.has(engineType);
  }
}

function makePlugin(id: string): EnginePlugin {
  return {
    meta: { id, displayName: id, version: "1.0.0" },
    createRuntime: () => ({}),
  };
}

// ── 测试 ──

describe("EnginePluginRegistry", () => {
  let registry: EnginePluginRegistry;

  beforeEach(() => {
    registry = new EnginePluginRegistry();
  });

  describe("register", () => {
    test("正向 - 注册后 has 返回 true", () => {
      registry.register(makePlugin("opencode"));
      expect(registry.has("opencode")).toBe(true);
    });

    test("正向 - 注册返回原 plugin", () => {
      const plugin = makePlugin("opencode");
      expect(registry.register(plugin)).toBe(plugin);
    });

    test("异常 - 重复注册抛 DUPLICATE_ENGINE_PLUGIN", () => {
      registry.register(makePlugin("opencode"));
      try {
        registry.register(makePlugin("opencode"));
        expect.unreachable("should throw");
      } catch (err) {
        expect(err).toBeInstanceOf(CoreRuntimeError);
        expect((err as CoreRuntimeError).code).toBe("DUPLICATE_ENGINE_PLUGIN");
      }
    });
  });

  describe("get / require / has", () => {
    test("正向 - get 已注册返回 plugin", () => {
      registry.register(makePlugin("opencode"));
      expect(registry.get("opencode")?.meta.id).toBe("opencode");
    });

    test("正向 - get 未注册返回 null", () => {
      expect(registry.get("missing")).toBeNull();
    });

    test("正向 - require 已注册返回 plugin", () => {
      registry.register(makePlugin("opencode"));
      expect(registry.require("opencode").meta.id).toBe("opencode");
    });

    test("异常 - require 未注册抛 PLUGIN_NOT_FOUND", () => {
      try {
        registry.require("missing");
        expect.unreachable("should throw");
      } catch (err) {
        expect((err as CoreRuntimeError).code).toBe("PLUGIN_NOT_FOUND");
      }
    });

    test("正向 - has 未注册返回 false", () => {
      expect(registry.has("missing")).toBe(false);
    });
  });

  describe("list", () => {
    test("正向 - 空注册表返回空列表", () => {
      expect(registry.list()).toEqual([]);
    });

    test("正向 - 按注册顺序返回", () => {
      registry.register(makePlugin("opencode"));
      registry.register(makePlugin("claude-code"));
      const ids = registry.list().map((p) => p.meta.id);
      expect(ids).toEqual(["opencode", "claude-code"]);
    });
  });
});
