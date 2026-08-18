import { describe, test, expect } from "bun:test";

// ========== Pure function copies from packages/chat-channel/src/protocol/update-frame.ts ==========

const TEXT_ENCODER = new TextEncoder();
const TEXT_DECODER = new TextDecoder();

const YJS_UPDATE_FRAME_TYPE = 0x01;

interface YjsUpdateFrame {
  docName: string;
  update: Uint8Array;
}

function encodeYjsUpdateFrame(docName: string, update: Uint8Array): Uint8Array {
  const docNameBytes = TEXT_ENCODER.encode(docName);
  if (docNameBytes.length > 0xffff) {
    throw new Error(`yjs update frame docName too long: ${docNameBytes.length} bytes`);
  }
  const frame = new Uint8Array(3 + docNameBytes.length + update.length);
  frame[0] = YJS_UPDATE_FRAME_TYPE;
  frame[1] = (docNameBytes.length >> 8) & 0xff;
  frame[2] = docNameBytes.length & 0xff;
  frame.set(docNameBytes, 3);
  frame.set(update, 3 + docNameBytes.length);
  return frame;
}

function decodeYjsUpdateFrame(data: Uint8Array): YjsUpdateFrame | null {
  if (data.length < 3 || data[0] !== YJS_UPDATE_FRAME_TYPE) return null;
  const docNameLen = (data[1] << 8) | data[2];
  if (3 + docNameLen > data.length) return null;
  const docName = TEXT_DECODER.decode(data.subarray(3, 3 + docNameLen));
  return { docName, update: data.subarray(3 + docNameLen) };
}

// ========== Tests ==========

describe("encodeYjsUpdateFrame", () => {
  test("encodes simple docName and update", () => {
    const update = new Uint8Array([0x01, 0x02, 0x03]);
    const frame = encodeYjsUpdateFrame("chat:test", update);

    expect(frame[0]).toBe(0x01); // frame type
    expect(frame.length).toBe(3 + 9 + 3); // 3-byte header + "chat:test" (9 bytes) + 3-byte update
  });

  test("encodes docName length in big-endian", () => {
    const docName = "a".repeat(256); // 256 bytes = 0x0100
    const update = new Uint8Array([]);
    const frame = encodeYjsUpdateFrame(docName, update);

    expect(frame[1]).toBe(0x01); // high byte
    expect(frame[2]).toBe(0x00); // low byte
  });

  test("handles empty docName", () => {
    const update = new Uint8Array([0x01]);
    const frame = encodeYjsUpdateFrame("", update);

    expect(frame[0]).toBe(0x01);
    expect(frame[1]).toBe(0x00);
    expect(frame[2]).toBe(0x00);
    expect(frame[3]).toBe(0x01); // update byte
  });

  test("handles empty update", () => {
    const frame = encodeYjsUpdateFrame("test", new Uint8Array([]));

    expect(frame[0]).toBe(0x01);
    expect(frame[1]).toBe(0x00);
    expect(frame[2]).toBe(0x04); // "test" = 4 bytes
    expect(frame.length).toBe(3 + 4 + 0);
  });

  test("throws when docName exceeds 65535 bytes", () => {
    const docName = "a".repeat(65536);
    const update = new Uint8Array([]);

    expect(() => encodeYjsUpdateFrame(docName, update)).toThrow("docName too long");
  });

  test("handles unicode docName", () => {
    const docName = "chat:测试";
    const update = new Uint8Array([0x01]);
    const frame = encodeYjsUpdateFrame(docName, update);

    expect(frame[0]).toBe(0x01);
    expect(frame.length).toBeGreaterThan(3 + 1); // at least header + some bytes
  });

  test("preserves update bytes exactly", () => {
    const update = new Uint8Array([0xde, 0xad, 0xbe, 0xef]);
    const frame = encodeYjsUpdateFrame("doc", update);

    const updateStart = 3 + 3; // header + "doc" (3 bytes)
    expect(frame[updateStart]).toBe(0xde);
    expect(frame[updateStart + 1]).toBe(0xad);
    expect(frame[updateStart + 2]).toBe(0xbe);
    expect(frame[updateStart + 3]).toBe(0xef);
  });
});

describe("decodeYjsUpdateFrame", () => {
  test("decodes valid frame", () => {
    const originalUpdate = new Uint8Array([0x01, 0x02, 0x03]);
    const frame = encodeYjsUpdateFrame("chat:test", originalUpdate);
    const decoded = decodeYjsUpdateFrame(frame);

    expect(decoded).not.toBeNull();
    expect(decoded!.docName).toBe("chat:test");
    expect(decoded!.update).toEqual(originalUpdate);
  });

  test("returns null for empty data", () => {
    expect(decodeYjsUpdateFrame(new Uint8Array([]))).toBeNull();
  });

  test("returns null for data shorter than 3 bytes", () => {
    expect(decodeYjsUpdateFrame(new Uint8Array([0x01, 0x00]))).toBeNull();
  });

  test("returns null for wrong frame type", () => {
    const frame = new Uint8Array([0x02, 0x00, 0x04, 0x74, 0x65, 0x73, 0x74]); // type 0x02
    expect(decodeYjsUpdateFrame(frame)).toBeNull();
  });

  test("returns null when docName length exceeds data length", () => {
    const frame = new Uint8Array([0x01, 0x00, 0x10]); // claims 16-byte docName but no data
    expect(decodeYjsUpdateFrame(frame)).toBeNull();
  });

  test("handles frame with empty docName", () => {
    const frame = encodeYjsUpdateFrame("", new Uint8Array([0x01]));
    const decoded = decodeYjsUpdateFrame(frame);

    expect(decoded).not.toBeNull();
    expect(decoded!.docName).toBe("");
    expect(decoded!.update).toEqual(new Uint8Array([0x01]));
  });

  test("handles frame with empty update", () => {
    const frame = encodeYjsUpdateFrame("test", new Uint8Array([]));
    const decoded = decodeYjsUpdateFrame(frame);

    expect(decoded).not.toBeNull();
    expect(decoded!.docName).toBe("test");
    expect(decoded!.update).toEqual(new Uint8Array([]));
  });

  test("decodes unicode docName correctly", () => {
    const docName = "chat:测试";
    const frame = encodeYjsUpdateFrame(docName, new Uint8Array([0x01]));
    const decoded = decodeYjsUpdateFrame(frame);

    expect(decoded).not.toBeNull();
    expect(decoded!.docName).toBe(docName);
  });

  test("handles large docName", () => {
    const docName = "a".repeat(1000);
    const frame = encodeYjsUpdateFrame(docName, new Uint8Array([0x01]));
    const decoded = decodeYjsUpdateFrame(frame);

    expect(decoded).not.toBeNull();
    expect(decoded!.docName).toBe(docName);
    expect(decoded!.docName.length).toBe(1000);
  });

  test("update is a view into the original buffer (zero-copy)", () => {
    const frame = encodeYjsUpdateFrame("doc", new Uint8Array([0x01, 0x02]));
    const decoded = decodeYjsUpdateFrame(frame);

    expect(decoded).not.toBeNull();
    // The update should be a subarray of the frame buffer
    expect(decoded!.update.buffer).toBe(frame.buffer);
  });
});

describe("encode/decode roundtrip", () => {
  test("roundtrip with various docNames", () => {
    const testCases = [
      { docName: "chat:rcs_abc123", update: new Uint8Array([0x01]) },
      { docName: "session:user-456", update: new Uint8Array([0xde, 0xad]) },
      { docName: "", update: new Uint8Array([]) },
      { docName: "very-long-docname-" + "x".repeat(100), update: new Uint8Array(100) },
    ];

    for (const { docName, update } of testCases) {
      const frame = encodeYjsUpdateFrame(docName, update);
      const decoded = decodeYjsUpdateFrame(frame);

      expect(decoded).not.toBeNull();
      expect(decoded!.docName).toBe(docName);
      expect(decoded!.update).toEqual(update);
    }
  });

  test("roundtrip with large update", () => {
    const docName = "chat:test";
    const update = new Uint8Array(10000);
    for (let i = 0; i < update.length; i++) {
      update[i] = i % 256;
    }

    const frame = encodeYjsUpdateFrame(docName, update);
    const decoded = decodeYjsUpdateFrame(frame);

    expect(decoded).not.toBeNull();
    expect(decoded!.docName).toBe(docName);
    expect(decoded!.update.length).toBe(update.length);
    expect(decoded!.update).toEqual(update);
  });
});
