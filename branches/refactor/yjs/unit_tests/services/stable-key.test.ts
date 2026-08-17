// stable-key.test.ts — 稳定序列化 key 函数测试
// 测试目标：stableKey 对 JSON-like 值（含 Map、Array、object）做确定性序列化
// 业务意图：确保 Yjs snapshot 去重时相同语义产生相同 key，不依赖属性插入顺序

import { describe, expect, test } from "bun:test";

// ── 复制源函数（纯函数，无外部依赖）──

function stableKey(value: unknown): string {
  return _stableKey(value);
}

function _stableKey(value: unknown): string {
  if (value === null) return "null";
  if (value === undefined) return "undefined";

  const t = typeof value;
  if (t === "string" || t === "number" || t === "boolean") {
    return JSON.stringify(value);
  }

  if (value instanceof Map) {
    const keys = [...value.keys()].sort();
    const parts = keys.map((k) => {
      const sk = typeof k === "string" ? JSON.stringify(k) : _stableKey(k);
      const sv = _stableKey(value.get(k));
      return `${sk}:${sv}`;
    });
    return `Map(${parts.join(",")})`;
  }

  if (Array.isArray(value)) {
    const parts = value.map((v) => _stableKey(v));
    return `[${parts.join(",")}]`;
  }

  if (typeof value === "object") {
    const keys = Object.keys(value).sort();
    const parts = keys.map((k) => {
      const sv = _stableKey((value as Record<string, unknown>)[k]);
      return `${JSON.stringify(k)}:${sv}`;
    });
    return `{${parts.join(",")}}`;
  }

  return String(value);
}

// ── 原始类型 ──

describe("stableKey 原始类型", () => {
  // null
  test("null 序列化为 'null'", () => {
    expect(stableKey(null)).toBe("null");
  });

  // undefined
  test("undefined 序列化为 'undefined'", () => {
    expect(stableKey(undefined)).toBe("undefined");
  });

  // null 和 undefined 区分
  test("null 和 undefined 产生不同 key", () => {
    expect(stableKey(null)).not.toBe(stableKey(undefined));
  });

  // 字符串
  test("字符串带引号序列化", () => {
    expect(stableKey("hello")).toBe('"hello"');
  });

  // 空字符串
  test("空字符串序列化", () => {
    expect(stableKey("")).toBe('""');
  });

  // 数字
  test("数字序列化", () => {
    expect(stableKey(42)).toBe("42");
    expect(stableKey(0)).toBe("0");
    expect(stableKey(-1.5)).toBe("-1.5");
  });

  // 布尔值
  test("布尔值序列化", () => {
    expect(stableKey(true)).toBe("true");
    expect(stableKey(false)).toBe("false");
  });
});

// ── 数组 ──

describe("stableKey 数组", () => {
  // 空数组
  test("空数组序列化", () => {
    expect(stableKey([])).toBe("[]");
  });

  // 简单数组
  test("简单数组序列化", () => {
    expect(stableKey([1, 2, 3])).toBe("[1,2,3]");
  });

  // 嵌套数组
  test("嵌套数组序列化", () => {
    expect(stableKey([1, [2, 3]])).toBe("[1,[2,3]]");
  });

  // 数组顺序影响结果
  test("数组顺序不同产生不同 key", () => {
    expect(stableKey([1, 2, 3])).not.toBe(stableKey([3, 2, 1]));
  });

  // 混合类型数组
  test("混合类型数组序列化", () => {
    expect(stableKey(["a", 1, true, null])).toBe('["a",1,true,null]');
  });
});

// ── 普通对象 ──

describe("stableKey 普通对象", () => {
  // 空对象
  test("空对象序列化", () => {
    expect(stableKey({})).toBe("{}");
  });

  // 属性按 key 排序，不受插入顺序影响
  test("属性顺序不影响序列化结果", () => {
    const obj1 = { a: 1, b: 2, c: 3 };
    const obj2 = { c: 3, a: 1, b: 2 };
    expect(stableKey(obj1)).toBe(stableKey(obj2));
  });

  // 嵌套对象
  test("嵌套对象序列化", () => {
    const obj = { b: { y: 2, x: 1 }, a: 1 };
    const result = stableKey(obj);
    // 外层按 a, b 排序；内层 b 按 x, y 排序
    expect(result).toBe('{"a":1,"b":{"x":1,"y":2}}');
  });

  // 不同值产生不同 key
  test("不同值产生不同 key", () => {
    expect(stableKey({ a: 1 })).not.toBe(stableKey({ a: 2 }));
  });

  // 不同 key 产生不同 key
  test("不同属性名产生不同 key", () => {
    expect(stableKey({ a: 1 })).not.toBe(stableKey({ b: 1 }));
  });
});

// ── Map ──

describe("stableKey Map", () => {
  // 空 Map
  test("空 Map 序列化", () => {
    expect(stableKey(new Map())).toBe("Map()");
  });

  // 简单 Map
  test("简单 Map 按 key 排序序列化", () => {
    const m = new Map<string, number>();
    m.set("b", 2);
    m.set("a", 1);
    expect(stableKey(m)).toBe('Map("a":1,"b":2)');
  });

  // Map 插入顺序不影响结果
  test("Map 插入顺序不影响序列化", () => {
    const m1 = new Map<string, number>([["x", 1], ["y", 2]]);
    const m2 = new Map<string, number>([["y", 2], ["x", 1]]);
    expect(stableKey(m1)).toBe(stableKey(m2));
  });

  // Map 与普通对象产生不同 key（格式不同）
  test("Map 和普通对象格式不同", () => {
    const m = new Map<string, number>([["a", 1]]);
    const obj = { a: 1 };
    expect(stableKey(m)).not.toBe(stableKey(obj));
  });

  // 嵌套 Map
  test("Map 值可以是复杂类型", () => {
    const m = new Map<string, number[]>([["arr", [1, 2]]]);
    expect(stableKey(m)).toBe('Map("arr":[1,2])');
  });
});

// ── 组合场景 ──

describe("stableKey 组合场景", () => {
  // 对象中包含数组
  test("对象包含数组", () => {
    const obj = { items: [1, 2], name: "test" };
    const result = stableKey(obj);
    expect(result).toBe('{"items":[1,2],"name":"test"}');
  });

  // 数组中包含对象（对象 key 排序）
  test("数组中包含对象", () => {
    const arr = [{ b: 2, a: 1 }, { d: 4, c: 3 }];
    const result = stableKey(arr);
    expect(result).toBe('[{"a":1,"b":2},{"c":3,"d":4}]');
  });

  // 深层嵌套
  test("深层嵌套结构", () => {
    const deep = { a: { b: { c: "deep" } } };
    expect(stableKey(deep)).toBe('{"a":{"b":{"c":"deep"}}}');
  });

  // 确定性：多次调用结果一致
  test("多次调用结果一致", () => {
    const obj = { z: 1, a: 2, m: [3, 4] };
    const k1 = stableKey(obj);
    const k2 = stableKey(obj);
    const k3 = stableKey({ a: 2, z: 1, m: [3, 4] }); // 不同插入顺序
    expect(k1).toBe(k2);
    expect(k1).toBe(k3);
  });
});
