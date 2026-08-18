/**
 * ws-types.test.ts — WsConnection 接口契约验证
 *
 * 源文件 src/transport/ws-types.ts 仅导出一个纯接口 WsConnection，
 * 没有运行时代码。这里通过构造符合接口的 mock 对象来验证类型契约：
 * - send(data: string | Uint8Array): void
 * - close(code?: number, reason?: string): void
 * - readyState: number (readonly)
 * - bufferedAmount?: number (readonly, optional)
 */

import { describe, test, expect } from "bun:test";

// ── 从源文件复制接口定义（纯类型，无运行时代码） ──────────────────────
interface WsConnection {
  send(data: string | Uint8Array): void;
  close(code?: number, reason?: string): void;
  readonly readyState: number;
  readonly bufferedAmount?: number;
}

// ── 辅助：创建 mock WsConnection ──────────────────────────────────────
function createMockWs(overrides?: Partial<WsConnection>): WsConnection {
  return {
    send: overrides?.send ?? (() => {}),
    close: overrides?.close ?? (() => {}),
    readyState: overrides?.readyState ?? 1, // OPEN
    bufferedAmount: overrides?.bufferedAmount,
  };
}

describe("WsConnection interface contract", () => {
  describe("send()", () => {
    test("accepts string data", () => {
      const sent: (string | Uint8Array)[] = [];
      const ws = createMockWs({ send: (data) => sent.push(data) });
      ws.send('{"type":"ping"}');
      expect(sent).toEqual(['{"type":"ping"}']);
    });

    test("accepts Uint8Array (binary frame)", () => {
      const sent: (string | Uint8Array)[] = [];
      const ws = createMockWs({ send: (data) => sent.push(data) });
      const binary = new Uint8Array([0x01, 0x02, 0x03]);
      ws.send(binary);
      expect(sent.length).toBe(1);
      expect(sent[0]).toBeInstanceOf(Uint8Array);
      expect((sent[0] as Uint8Array).length).toBe(3);
    });

    test("returns void", () => {
      const ws = createMockWs();
      const result = ws.send("hello");
      expect(result).toBeUndefined();
    });
  });

  describe("close()", () => {
    test("can be called with no arguments", () => {
      let called = false;
      const ws = createMockWs({ close: () => { called = true; } });
      ws.close();
      expect(called).toBe(true);
    });

    test("accepts code and reason", () => {
      let capturedCode: number | undefined;
      let capturedReason: string | undefined;
      const ws = createMockWs({
        close: (code?: number, reason?: string) => {
          capturedCode = code;
          capturedReason = reason;
        },
      });
      ws.close(1001, "going away");
      expect(capturedCode).toBe(1001);
      expect(capturedReason).toBe("going away");
    });

    test("accepts code only (no reason)", () => {
      let capturedCode: number | undefined;
      let capturedReason: string | undefined;
      const ws = createMockWs({
        close: (code?: number, reason?: string) => {
          capturedCode = code;
          capturedReason = reason;
        },
      });
      ws.close(1000);
      expect(capturedCode).toBe(1000);
      expect(capturedReason).toBeUndefined();
    });

    test("returns void", () => {
      const ws = createMockWs();
      const result = ws.close(1000, "done");
      expect(result).toBeUndefined();
    });
  });

  describe("readyState (readonly)", () => {
    test("exposes numeric ready state", () => {
      const ws = createMockWs({ readyState: 1 });
      expect(typeof ws.readyState).toBe("number");
      expect(ws.readyState).toBe(1);
    });

    test("supports all standard WebSocket states", () => {
      // 0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED
      for (const state of [0, 1, 2, 3]) {
        const ws = createMockWs({ readyState: state });
        expect(ws.readyState).toBe(state);
      }
    });
  });

  describe("bufferedAmount (readonly, optional)", () => {
    test("is undefined when not provided", () => {
      const ws = createMockWs();
      expect(ws.bufferedAmount).toBeUndefined();
    });

    test("exposes numeric value when provided", () => {
      const ws = createMockWs({ bufferedAmount: 65536 });
      expect(ws.bufferedAmount).toBe(65536);
    });

    test("can be zero (no buffered data)", () => {
      const ws = createMockWs({ bufferedAmount: 0 });
      expect(ws.bufferedAmount).toBe(0);
    });
  });

  describe("full lifecycle simulation", () => {
    test("open → send → close", () => {
      const log: string[] = [];
      const ws: WsConnection = {
        readyState: 1,
        bufferedAmount: 0,
        send(data) {
          log.push(`send:${typeof data === "string" ? data : "binary"}`);
        },
        close(code, reason) {
          log.push(`close:${code}:${reason ?? ""}`);
        },
      };

      expect(ws.readyState).toBe(1);
      ws.send("hello");
      ws.send(new Uint8Array([1]));
      ws.close(1000, "normal");

      expect(log).toEqual([
        "send:hello",
        "send:binary",
        "close:1000:normal",
      ]);
    });
  });
});
