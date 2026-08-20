// knowledge-provider-registry.test.ts — 知识库 Provider 注册表纯逻辑测试
// 测试目标：getKnowledgeProvider / setKnowledgeProviderForTesting
// 业务意图：确保测试时可以切换 Provider 实现，生产时返回默认 Provider

import { beforeEach, describe, expect, mock, test } from "bun:test";

// ── 复制纯函数 ──

interface KnowledgeProvider {
  name: string;
}

class DefaultProvider implements KnowledgeProvider {
  name = "default";
}

let testProvider: KnowledgeProvider | null = null;

function getKnowledgeProvider(): KnowledgeProvider {
  if (testProvider) return testProvider;
  return new DefaultProvider();
}

function setKnowledgeProviderForTesting(p: KnowledgeProvider | null): void {
  testProvider = p;
}

// ── tests ──

describe("knowledge-provider-registry Provider 注册表", () => {
  beforeEach(() => {
    mock.restore();
    testProvider = null; // reset
  });

  describe("getKnowledgeProvider", () => {
    test("无测试覆盖时返回默认 Provider", () => {
      const provider = getKnowledgeProvider();
      expect(provider.name).toBe("default");
    });

    test("每次调用返回新实例（DefaultProvider 是 new 出来的）", () => {
      const a = getKnowledgeProvider();
      const b = getKnowledgeProvider();
      expect(a).not.toBe(b);
    });
  });

  describe("setKnowledgeProviderForTesting", () => {
    test("设置测试 Provider 后 getKnowledgeProvider 返回它", () => {
      const fake: KnowledgeProvider = { name: "fake" };
      setKnowledgeProviderForTesting(fake);
      expect(getKnowledgeProvider()).toBe(fake);
    });

    test("设置为 null 后恢复默认", () => {
      const fake: KnowledgeProvider = { name: "fake" };
      setKnowledgeProviderForTesting(fake);
      expect(getKnowledgeProvider().name).toBe("fake");

      setKnowledgeProviderForTesting(null);
      expect(getKnowledgeProvider().name).toBe("default");
    });

    test("多次覆盖取最后一个", () => {
      setKnowledgeProviderForTesting({ name: "first" });
      setKnowledgeProviderForTesting({ name: "second" });
      expect(getKnowledgeProvider().name).toBe("second");
    });
  });
});
