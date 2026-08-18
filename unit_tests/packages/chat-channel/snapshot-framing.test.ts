import { describe, test, expect } from "bun:test";

// ========== Pure function copies from packages/chat-channel/src/persist/snapshot-framing.ts ==========

const PUBLISH_FRAME_FLAG = 0x80;
const PUBLISHER_ID_BYTES = 16;
const PUBLISH_PAYLOAD_LENGTH_BYTES = 4;
const PUBLISH_HEADER_LENGTH = 1 + PUBLISHER_ID_BYTES + PUBLISH_PAYLOAD_LENGTH_BYTES;

function createPublisherId(uuid: string): Uint8Array {
  const hex = uuid.replace(/-/g, "");
  const bytes = new Uint8Array(PUBLISHER_ID_BYTES);
  for (let index = 0; index < PUBLISHER_ID_BYTES; index += 1) {
    bytes[index] = Number.parseInt(hex.slice(index * 2, index * 2 + 2), 16);
  }
  return bytes;
}

function isSamePublisherId(a: Uint8Array, b: Uint8Array): boolean {
  for (let index = 0; index < PUBLISHER_ID_BYTES; index += 1) {
    if (a[index] !== b[index]) return false;
  }
  return true;
}

function framePublishUpdate(update: Uint8Array, publisherId: Uint8Array): Buffer {
  const framed = Buffer.alloc(PUBLISH_HEADER_LENGTH + update.length);
  framed[0] = PUBLISH_FRAME_FLAG;
  framed.set(publisherId, 1);
  framed.writeUInt32BE(update.length, 1 + PUBLISHER_ID_BYTES);
  framed.set(update, PUBLISH_HEADER_LENGTH);
  return framed;
}

function parseFramedPublish(payload: Uint8Array): { publisherId: Uint8Array; update: Uint8Array } | null {
  if (payload.length < PUBLISH_HEADER_LENGTH || payload[0] !== PUBLISH_FRAME_FLAG) return null;

  const lengthOffset = 1 + PUBLISHER_ID_BYTES;
  const payloadLength =
    ((payload[lengthOffset] << 24) |
      (payload[lengthOffset + 1] << 16) |
      (payload[lengthOffset + 2] << 8) |
      payload[lengthOffset + 3]) >>>
    0;
  if (payloadLength !== payload.length - PUBLISH_HEADER_LENGTH) return null;

  return {
    publisherId: payload.subarray(1, lengthOffset),
    update: payload.subarray(PUBLISH_HEADER_LENGTH),
  };
}

// ========== Tests ==========

describe("createPublisherId", () => {
  test("creates 16-byte array from UUID", () => {
    const uuid = "550e8400-e29b-41d4-a716-446655440000";
    const result = createPublisherId(uuid);

    expect(result).toBeInstanceOf(Uint8Array);
    expect(result.length).toBe(16);
  });

  test("correctly parses UUID without hyphens", () => {
    const uuid = "550e8400-e29b-41d4-a716-446655440000";
    const result = createPublisherId(uuid);

    // 55 0e 84 00 e2 9b 41 d4 a7 16 44 66 55 44 00 00
    expect(result[0]).toBe(0x55);
    expect(result[1]).toBe(0x0e);
    expect(result[2]).toBe(0x84);
    expect(result[3]).toBe(0x00);
    expect(result[4]).toBe(0xe2);
    expect(result[5]).toBe(0x9b);
    expect(result[6]).toBe(0x41);
    expect(result[7]).toBe(0xd4);
  });

  test("handles all-zeros UUID", () => {
    const uuid = "00000000-0000-0000-0000-000000000000";
    const result = createPublisherId(uuid);

    for (let i = 0; i < 16; i++) {
      expect(result[i]).toBe(0);
    }
  });

  test("handles all-ones UUID", () => {
    const uuid = "ffffffff-ffff-ffff-ffff-ffffffffffff";
    const result = createPublisherId(uuid);

    for (let i = 0; i < 16; i++) {
      expect(result[i]).toBe(0xff);
    }
  });

  test("is deterministic", () => {
    const uuid = "12345678-1234-5678-1234-567812345678";
    const result1 = createPublisherId(uuid);
    const result2 = createPublisherId(uuid);

    expect(result1).toEqual(result2);
  });

  test("different UUIDs produce different IDs", () => {
    const id1 = createPublisherId("00000000-0000-0000-0000-000000000001");
    const id2 = createPublisherId("00000000-0000-0000-0000-000000000002");

    expect(id1).not.toEqual(id2);
  });
});

describe("isSamePublisherId", () => {
  test("returns true for identical IDs", () => {
    const id = createPublisherId("550e8400-e29b-41d4-a716-446655440000");
    expect(isSamePublisherId(id, id)).toBe(true);
  });

  test("returns true for equal IDs (different instances)", () => {
    const uuid = "550e8400-e29b-41d4-a716-446655440000";
    const id1 = createPublisherId(uuid);
    const id2 = createPublisherId(uuid);

    expect(isSamePublisherId(id1, id2)).toBe(true);
  });

  test("returns false for different IDs", () => {
    const id1 = createPublisherId("00000000-0000-0000-0000-000000000001");
    const id2 = createPublisherId("00000000-0000-0000-0000-000000000002");

    expect(isSamePublisherId(id1, id2)).toBe(false);
  });

  test("returns false when first byte differs", () => {
    const id1 = new Uint8Array([0x00, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
    const id2 = new Uint8Array([0x01, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);

    expect(isSamePublisherId(id1, id2)).toBe(false);
  });

  test("returns false when last byte differs", () => {
    const id1 = new Uint8Array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0x00]);
    const id2 = new Uint8Array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0x01]);

    expect(isSamePublisherId(id1, id2)).toBe(false);
  });

  test("returns true for all-zeros IDs", () => {
    const id1 = new Uint8Array(16);
    const id2 = new Uint8Array(16);

    expect(isSamePublisherId(id1, id2)).toBe(true);
  });

  test("returns true for all-ones IDs", () => {
    const id1 = new Uint8Array(16).fill(0xff);
    const id2 = new Uint8Array(16).fill(0xff);

    expect(isSamePublisherId(id1, id2)).toBe(true);
  });
});

describe("framePublishUpdate", () => {
  test("creates framed buffer with correct structure", () => {
    const publisherId = createPublisherId("550e8400-e29b-41d4-a716-446655440000");
    const update = new Uint8Array([0x01, 0x02, 0x03]);
    const framed = framePublishUpdate(update, publisherId);

    expect(framed[0]).toBe(0x80); // flag
    expect(framed.length).toBe(PUBLISH_HEADER_LENGTH + 3);
  });

  test("includes publisher ID in frame", () => {
    const publisherId = createPublisherId("550e8400-e29b-41d4-a716-446655440000");
    const update = new Uint8Array([0x01]);
    const framed = framePublishUpdate(update, publisherId);

    // Check publisher ID bytes (positions 1-16)
    for (let i = 0; i < 16; i++) {
      expect(framed[1 + i]).toBe(publisherId[i]);
    }
  });

  test("encodes update length in big-endian", () => {
    const publisherId = new Uint8Array(16);
    const update = new Uint8Array(256); // 0x00000100
    const framed = framePublishUpdate(update, publisherId);

    const lengthOffset = 1 + 16;
    expect(framed[lengthOffset]).toBe(0x00); // byte 0
    expect(framed[lengthOffset + 1]).toBe(0x00); // byte 1
    expect(framed[lengthOffset + 2]).toBe(0x01); // byte 2
    expect(framed[lengthOffset + 3]).toBe(0x00); // byte 3
  });

  test("preserves update bytes", () => {
    const publisherId = new Uint8Array(16);
    const update = new Uint8Array([0xde, 0xad, 0xbe, 0xef]);
    const framed = framePublishUpdate(update, publisherId);

    const updateStart = PUBLISH_HEADER_LENGTH;
    expect(framed[updateStart]).toBe(0xde);
    expect(framed[updateStart + 1]).toBe(0xad);
    expect(framed[updateStart + 2]).toBe(0xbe);
    expect(framed[updateStart + 3]).toBe(0xef);
  });

  test("handles empty update", () => {
    const publisherId = new Uint8Array(16);
    const update = new Uint8Array([]);
    const framed = framePublishUpdate(update, publisherId);

    expect(framed.length).toBe(PUBLISH_HEADER_LENGTH);
    const lengthOffset = 1 + 16;
    expect(framed[lengthOffset]).toBe(0);
    expect(framed[lengthOffset + 1]).toBe(0);
    expect(framed[lengthOffset + 2]).toBe(0);
    expect(framed[lengthOffset + 3]).toBe(0);
  });

  test("handles large update", () => {
    const publisherId = new Uint8Array(16);
    const update = new Uint8Array(10000);
    const framed = framePublishUpdate(update, publisherId);

    expect(framed.length).toBe(PUBLISH_HEADER_LENGTH + 10000);
    const lengthOffset = 1 + 16;
    // 10000 = 0x00002710
    expect(framed[lengthOffset]).toBe(0x00);
    expect(framed[lengthOffset + 1]).toBe(0x00);
    expect(framed[lengthOffset + 2]).toBe(0x27);
    expect(framed[lengthOffset + 3]).toBe(0x10);
  });
});

describe("parseFramedPublish", () => {
  test("parses valid framed update", () => {
    const publisherId = createPublisherId("550e8400-e29b-41d4-a716-446655440000");
    const update = new Uint8Array([0x01, 0x02, 0x03]);
    const framed = framePublishUpdate(update, publisherId);
    const parsed = parseFramedPublish(framed);

    expect(parsed).not.toBeNull();
    expect(parsed!.publisherId).toEqual(publisherId);
    expect(parsed!.update).toEqual(update);
  });

  test("returns null for empty payload", () => {
    expect(parseFramedPublish(new Uint8Array([]))).toBeNull();
  });

  test("returns null for payload shorter than header", () => {
    const short = new Uint8Array(PUBLISH_HEADER_LENGTH - 1);
    short[0] = 0x80;
    expect(parseFramedPublish(short)).toBeNull();
  });

  test("returns null for wrong flag byte", () => {
    const payload = new Uint8Array(PUBLISH_HEADER_LENGTH + 1);
    payload[0] = 0x7f; // wrong flag
    expect(parseFramedPublish(payload)).toBeNull();
  });

  test("returns null when length field doesn't match actual length", () => {
    const publisherId = new Uint8Array(16);
    const update = new Uint8Array([0x01, 0x02]);
    const framed = framePublishUpdate(update, publisherId);

    // Tamper with length field
    framed[1 + 16 + 3] = 0x99; // wrong length

    expect(parseFramedPublish(framed)).toBeNull();
  });

  test("returns null when payload is truncated", () => {
    const publisherId = new Uint8Array(16);
    const update = new Uint8Array([0x01, 0x02, 0x03, 0x04]);
    const framed = framePublishUpdate(update, publisherId);

    // Truncate the payload
    const truncated = framed.subarray(0, framed.length - 2);
    expect(parseFramedPublish(truncated)).toBeNull();
  });

  test("handles empty update", () => {
    const publisherId = new Uint8Array(16);
    const update = new Uint8Array([]);
    const framed = framePublishUpdate(update, publisherId);
    const parsed = parseFramedPublish(framed);

    expect(parsed).not.toBeNull();
    expect(parsed!.update.length).toBe(0);
  });

  test("handles large update", () => {
    const publisherId = new Uint8Array(16);
    const update = new Uint8Array(5000);
    for (let i = 0; i < update.length; i++) {
      update[i] = i % 256;
    }
    const framed = framePublishUpdate(update, publisherId);
    const parsed = parseFramedPublish(framed);

    expect(parsed).not.toBeNull();
    expect(parsed!.update.length).toBe(5000);
    expect(parsed!.update).toEqual(update);
  });

  test("returns views into original buffer (zero-copy)", () => {
    const publisherId = createPublisherId("550e8400-e29b-41d4-a716-446655440000");
    const update = new Uint8Array([0x01]);
    const framed = framePublishUpdate(update, publisherId);
    const parsed = parseFramedPublish(framed);

    expect(parsed).not.toBeNull();
    // Both should be views into the same underlying buffer
    expect(parsed!.publisherId.buffer).toBe(framed.buffer);
    expect(parsed!.update.buffer).toBe(framed.buffer);
  });
});

describe("frame/parse roundtrip", () => {
  test("roundtrip with various updates", () => {
    const publisherId = createPublisherId("12345678-1234-5678-1234-567812345678");

    const testCases = [
      new Uint8Array([]),
      new Uint8Array([0x01]),
      new Uint8Array([0xde, 0xad, 0xbe, 0xef]),
      new Uint8Array(1000).fill(0x42),
    ];

    for (const update of testCases) {
      const framed = framePublishUpdate(update, publisherId);
      const parsed = parseFramedPublish(framed);

      expect(parsed).not.toBeNull();
      expect(isSamePublisherId(parsed!.publisherId, publisherId)).toBe(true);
      expect(parsed!.update).toEqual(update);
    }
  });

  test("roundtrip preserves different publisher IDs", () => {
    const publishers = [
      createPublisherId("00000000-0000-0000-0000-000000000001"),
      createPublisherId("ffffffff-ffff-ffff-ffff-ffffffffffff"),
      createPublisherId("550e8400-e29b-41d4-a716-446655440000"),
    ];

    const update = new Uint8Array([0x01, 0x02]);

    for (const pubId of publishers) {
      const framed = framePublishUpdate(update, pubId);
      const parsed = parseFramedPublish(framed);

      expect(parsed).not.toBeNull();
      expect(isSamePublisherId(parsed!.publisherId, pubId)).toBe(true);
    }
  });

  test("can distinguish between different publishers", () => {
    const pub1 = createPublisherId("00000000-0000-0000-0000-000000000001");
    const pub2 = createPublisherId("00000000-0000-0000-0000-000000000002");
    const update = new Uint8Array([0x01]);

    const framed1 = framePublishUpdate(update, pub1);
    const framed2 = framePublishUpdate(update, pub2);

    const parsed1 = parseFramedPublish(framed1);
    const parsed2 = parseFramedPublish(framed2);

    expect(parsed1).not.toBeNull();
    expect(parsed2).not.toBeNull();
    expect(isSamePublisherId(parsed1!.publisherId, parsed2!.publisherId)).toBe(false);
    expect(isSamePublisherId(parsed1!.publisherId, pub1)).toBe(true);
    expect(isSamePublisherId(parsed2!.publisherId, pub2)).toBe(true);
  });
});
