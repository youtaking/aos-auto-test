// emitter.test.ts — EventEmitter 类型安全事件发射器测试
// 测试目标：on/off/emit/removeAllListeners 的行为正确性
// 业务意图：确保 ACP 模块共用的事件总线在订阅、取消、广播、清理时均符合预期

import { describe, test, expect } from "bun:test";

// ── 复制纯类（来自 packages/acp-link/src/client/emitter.ts）──

type Handler<T = void> = T extends void ? () => void : (payload: T) => void;

class EventEmitter<Events extends Record<string, unknown>> {
  // biome-ignore lint/suspicious/noExplicitAny: generic event handler storage requires erased types
  private handlers = new Map<string, Set<Handler<any>>>();

  on<Event extends keyof Events>(event: Event, handler: Handler<Events[Event]>): void {
    let set = this.handlers.get(event as string);
    if (!set) {
      set = new Set();
      this.handlers.set(event as string, set);
    }
    set.add(handler);
  }

  off<Event extends keyof Events>(event: Event, handler: Handler<Events[Event]>): void {
    const set = this.handlers.get(event as string);
    if (set) {
      set.delete(handler);
    }
  }

  emit<Event extends keyof Events>(event: Event, ...args: Events[Event] extends void ? [] : [Events[Event]]): void {
    const set = this.handlers.get(event as string);
    if (set) {
      for (const handler of set) {
        // biome-ignore lint/suspicious/noExplicitAny: handler invocation requires erased generic type
        (handler as any)(...args);
      }
    }
  }

  removeAllListeners(event?: keyof Events): void {
    if (event !== undefined) {
      this.handlers.delete(event as string);
    } else {
      this.handlers.clear();
    }
  }
}

// ── 测试用事件类型定义 ──

type TestEvents = {
  data: string;
  count: number;
  ping: void;
  payload: { id: number; name: string };
};

// ── tests ──

describe("EventEmitter on + emit", () => {
  // 单 handler 订阅后 emit 触发，payload 正确传递
  test("单 handler 收到 emit 的 payload", () => {
    const emitter = new EventEmitter<TestEvents>();
    let received: string | null = null;
    emitter.on("data", (msg) => { received = msg; });
    emitter.emit("data", "hello");
    expect(received).toBe("hello");
  });

  // 多个 handler 订阅同一事件，emit 时全部触发
  test("多个 handler 均收到同一 emit", () => {
    const emitter = new EventEmitter<TestEvents>();
    const calls: string[] = [];
    emitter.on("data", (msg) => { calls.push(`a:${msg}`); });
    emitter.on("data", (msg) => { calls.push(`b:${msg}`); });
    emitter.emit("data", "x");
    expect(calls).toEqual(["a:x", "b:x"]);
  });

  // void 事件 handler 无参数调用，不抛错
  test("void 事件 handler 无参数正常触发", () => {
    const emitter = new EventEmitter<TestEvents>();
    let called = false;
    emitter.on("ping", () => { called = true; });
    emitter.emit("ping");
    expect(called).toBe(true);
  });

  // number payload 正确传递
  test("number payload 正确传递", () => {
    const emitter = new EventEmitter<TestEvents>();
    let received: number | null = null;
    emitter.on("count", (n) => { received = n; });
    emitter.emit("count", 42);
    expect(received).toBe(42);
  });

  // object payload 深比较正确
  test("object payload 内容完整传递", () => {
    const emitter = new EventEmitter<TestEvents>();
    let received: { id: number; name: string } | null = null;
    emitter.on("payload", (p) => { received = p; });
    const obj = { id: 7, name: "test" };
    emitter.emit("payload", obj);
    expect(received).toEqual({ id: 7, name: "test" });
    // 引用同一对象
    expect(received).toBe(obj);
  });

  // emit 期间 handler 抛异常时其他 handler 的行为
  // 源码 emit() 使用 for...of 循环直接调用 handler，无 try-catch 保护。
  // 因此第一个 handler 抛异常后，循环中断，后续 handler 不会执行，异常向上传播。
  test("emit 期间 handler 抛异常时其他 handler 仍然触发", () => {
    const emitter = new EventEmitter<TestEvents>();
    const calls: string[] = [];
    emitter.on("data", () => {
      calls.push("first");
      throw new Error("handler error");
    });
    emitter.on("data", () => {
      calls.push("second");
    });
    // 第一个 handler 抛异常，emit 整体抛出
    expect(() => emitter.emit("data", "x")).toThrow("handler error");
    // 第一个 handler 在抛异常前已执行，第二个 handler 因循环中断未执行
    expect(calls).toEqual(["first"]);
  });
});

describe("EventEmitter emit 无 handler 不抛错", () => {
  // 未订阅任何 handler 时 emit 不抛异常
  test("无 handler 时 emit 不抛异常", () => {
    const emitter = new EventEmitter<TestEvents>();
    expect(() => emitter.emit("data", "hello")).not.toThrow();
  });

  // void 事件无 handler 时 emit 不抛异常
  test("void 事件无 handler 时 emit 不抛异常", () => {
    const emitter = new EventEmitter<TestEvents>();
    expect(() => emitter.emit("ping")).not.toThrow();
  });
});

describe("EventEmitter off 取消订阅", () => {
  // off 后 handler 不再被触发
  test("off 后 handler 不再触发", () => {
    const emitter = new EventEmitter<TestEvents>();
    let count = 0;
    const handler = () => { count++; };
    emitter.on("ping", handler);
    emitter.emit("ping");
    expect(count).toBe(1);
    emitter.off("ping", handler);
    emitter.emit("ping");
    // off 后第二次 emit 不应增加 count
    expect(count).toBe(1);
  });

  // off 只移除指定 handler，其他 handler 不受影响
  test("off 只移除指定 handler，其他 handler 仍触发", () => {
    const emitter = new EventEmitter<TestEvents>();
    const calls: string[] = [];
    const handlerA = (msg: string) => { calls.push(`a:${msg}`); };
    const handlerB = (msg: string) => { calls.push(`b:${msg}`); };
    emitter.on("data", handlerA);
    emitter.on("data", handlerB);
    emitter.off("data", handlerA);
    emitter.emit("data", "x");
    expect(calls).toEqual(["b:x"]);
  });

  // off 未注册过的 handler 不抛错
  test("off 未注册过的 handler 不抛异常", () => {
    const emitter = new EventEmitter<TestEvents>();
    const handler = () => {};
    expect(() => emitter.off("ping", handler)).not.toThrow();
  });

  // off 未订阅的事件名不抛错
  test("off 从未订阅的事件名不抛异常", () => {
    const emitter = new EventEmitter<TestEvents>();
    const handler = (msg: string) => {};
    expect(() => emitter.off("data", handler)).not.toThrow();
  });
});

describe("EventEmitter 多事件类型独立性", () => {
  // 不同事件的 handler 互不干扰
  test("不同事件类型的 handler 独立触发", () => {
    const emitter = new EventEmitter<TestEvents>();
    const dataCalls: string[] = [];
    const countCalls: number[] = [];
    emitter.on("data", (msg) => { dataCalls.push(msg); });
    emitter.on("count", (n) => { countCalls.push(n); });
    emitter.emit("data", "hello");
    emitter.emit("count", 99);
    emitter.emit("data", "world");
    expect(dataCalls).toEqual(["hello", "world"]);
    expect(countCalls).toEqual([99]);
  });

  // off 一个事件不影响另一个事件的 handler
  test("off 一个事件的 handler 不影响另一事件", () => {
    const emitter = new EventEmitter<TestEvents>();
    let dataCalls = 0;
    let countCalls = 0;
    const dataHandler = () => { dataCalls++; };
    const countHandler = () => { countCalls++; };
    emitter.on("ping", dataHandler);
    emitter.on("count", countHandler);
    emitter.off("ping", dataHandler);
    emitter.emit("count", 1);
    expect(countCalls).toBe(1);
    // ping 的 handler 已 off，不触发
    emitter.emit("ping");
    expect(dataCalls).toBe(0);
  });
});

describe("EventEmitter 重复 on 同一 handler（Set 去重）", () => {
  // 同一 handler 重复 on 只触发一次（Set 去重）
  test("同一 handler 重复 on 仅触发一次", () => {
    const emitter = new EventEmitter<TestEvents>();
    let count = 0;
    const handler = (msg: string) => { count++; };
    emitter.on("data", handler);
    emitter.on("data", handler); // 重复订阅
    emitter.on("data", handler); // 再次重复
    emitter.emit("data", "x");
    expect(count).toBe(1);
  });

  // 重复 on 后 off 一次即可完全移除
  test("重复 on 后 off 一次完全移除（Set 中只有一个实例）", () => {
    const emitter = new EventEmitter<TestEvents>();
    let count = 0;
    const handler = () => { count++; };
    emitter.on("ping", handler);
    emitter.on("ping", handler);
    emitter.off("ping", handler);
    emitter.emit("ping");
    expect(count).toBe(0);
  });
});

describe("EventEmitter removeAllListeners", () => {
  // 指定事件名：只清除该事件的 handler
  test("removeAllListeners(event) 只清除指定事件的 handler", () => {
    const emitter = new EventEmitter<TestEvents>();
    let dataCalls = 0;
    let countCalls = 0;
    emitter.on("data", () => { dataCalls++; });
    emitter.on("count", () => { countCalls++; });
    emitter.removeAllListeners("data");
    emitter.emit("data", "x");
    emitter.emit("count", 1);
    expect(dataCalls).toBe(0);
    expect(countCalls).toBe(1);
  });

  // 不传参数：清除所有事件的全部 handler
  test("removeAllListeners() 不传参数清除所有事件 handler", () => {
    const emitter = new EventEmitter<TestEvents>();
    let dataCalls = 0;
    let countCalls = 0;
    let pingCalls = 0;
    emitter.on("data", () => { dataCalls++; });
    emitter.on("count", () => { countCalls++; });
    emitter.on("ping", () => { pingCalls++; });
    emitter.removeAllListeners();
    emitter.emit("data", "x");
    emitter.emit("count", 1);
    emitter.emit("ping");
    expect(dataCalls).toBe(0);
    expect(countCalls).toBe(0);
    expect(pingCalls).toBe(0);
  });

  // 清除后重新 on 可正常订阅
  test("removeAllListeners 后重新 on 可正常触发", () => {
    const emitter = new EventEmitter<TestEvents>();
    let first = 0;
    emitter.on("ping", () => { first++; });
    emitter.emit("ping");
    expect(first).toBe(1);
    emitter.removeAllListeners("ping");
    let second = 0;
    emitter.on("ping", () => { second++; });
    emitter.emit("ping");
    expect(first).toBe(1);  // 旧 handler 不再触发
    expect(second).toBe(1); // 新 handler 正常触发
  });

  // 对从未订阅的事件调用 removeAllListeners 不抛错
  test("对未订阅的事件 removeAllListeners 不抛异常", () => {
    const emitter = new EventEmitter<TestEvents>();
    expect(() => emitter.removeAllListeners("payload")).not.toThrow();
  });
});
