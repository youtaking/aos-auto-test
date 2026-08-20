// secret-box.test.ts — opensandbox-cluster 凭据加解密测试
// 测试目标：createSecretBox 的 encrypt/decrypt 往返一致性、格式校验、密钥长度校验
// 业务意图：确保 API key 等敏感凭据加密存储后可正确解密，密钥不匹配时拒绝

import { describe, test, expect } from "bun:test";

// ── 复制纯函数（来自 packages/opensandbox-cluster/src/security/secret-box.ts）──
// 使用 Bun 内置 crypto 替代 @noble/ciphers（避免外部依赖）

const VERSION = "v1";
const NONCE_LENGTH = 12;

function encode(value: Uint8Array): string {
  return Buffer.from(value).toString("base64url");
}

function decode(value: string): Uint8Array {
  return new Uint8Array(Buffer.from(value, "base64url"));
}

// AES-256-GCM 加解密（使用 Node.js crypto 模块，与 @noble/ciphers 语义等价）
import { createCipheriv, createDecipheriv, randomBytes as nodeRandomBytes } from "node:crypto";

function aesGcmEncrypt(key: Uint8Array, nonce: Uint8Array, plaintext: Uint8Array): Uint8Array {
  const cipher = createCipheriv("aes-256-gcm", key, nonce);
  const encrypted = Buffer.concat([cipher.update(plaintext), cipher.final(), cipher.getAuthTag()]);
  return new Uint8Array(encrypted);
}

function aesGcmDecrypt(key: Uint8Array, nonce: Uint8Array, ciphertext: Uint8Array): Uint8Array {
  const tagStart = ciphertext.length - 16;
  const data = ciphertext.slice(0, tagStart);
  const tag = ciphertext.slice(tagStart);
  const decipher = createDecipheriv("aes-256-gcm", key, nonce);
  decipher.setAuthTag(tag);
  return new Uint8Array(Buffer.concat([decipher.update(data), decipher.final()]));
}

function randomBytes(n: number): Uint8Array {
  return new Uint8Array(nodeRandomBytes(n));
}

function createSecretBox(key: Uint8Array) {
  if (key.length !== 32) throw new Error("secret box key must be 32 bytes");

  return {
    encryptCredential(value: string): string {
      const nonce = randomBytes(NONCE_LENGTH);
      const ciphertext = aesGcmEncrypt(key, nonce, new TextEncoder().encode(value));
      return [VERSION, encode(nonce), encode(ciphertext)].join(".");
    },
    decryptCredential(value: string): string {
      const [version, nonceText, ciphertextText] = value.split(".");
      if (version !== VERSION || !nonceText || !ciphertextText) throw new Error("invalid encrypted credential format");
      try {
        const plaintext = aesGcmDecrypt(key, decode(nonceText), decode(ciphertextText));
        return new TextDecoder().decode(plaintext);
      } catch {
        throw new Error("unable to decrypt credential");
      }
    },
    encryptApiKey(value: string): string {
      return this.encryptCredential(value);
    },
    decryptApiKey(value: string): string {
      try {
        return this.decryptCredential(value);
      } catch {
        throw new Error("unable to decrypt OpenSandbox API key");
      }
    },
  };
}

// ── 辅助 ──

function makeKey(): Uint8Array {
  return randomBytes(32);
}

describe("createSecretBox", () => {
  test("异常 - 密钥非 32 字节抛错", () => {
    expect(() => createSecretBox(new Uint8Array(16))).toThrow("must be 32 bytes");
    expect(() => createSecretBox(new Uint8Array(0))).toThrow("must be 32 bytes");
  });
});

describe("encryptCredential / decryptCredential", () => {
  test("正向 - 加密后解密恢复原文", () => {
    const box = createSecretBox(makeKey());
    const plaintext = "my-secret-api-key-12345";
    const encrypted = box.encryptCredential(plaintext);
    expect(box.decryptCredential(encrypted)).toBe(plaintext);
  });

  test("正向 - 加密结果格式为 v1.nonce.ciphertext（三段式点分隔）", () => {
    const box = createSecretBox(makeKey());
    const encrypted = box.encryptCredential("hello");
    const parts = encrypted.split(".");
    expect(parts.length).toBe(3);
    expect(parts[0]).toBe("v1");
    expect(parts[1].length).toBeGreaterThan(0);
    expect(parts[2].length).toBeGreaterThan(0);
  });

  test("正向 - 两次加密同一明文产生不同密文（随机 nonce）", () => {
    const box = createSecretBox(makeKey());
    const a = box.encryptCredential("same");
    const b = box.encryptCredential("same");
    expect(a).not.toBe(b);
  });

  test("分支 - 空字符串可加密解密", () => {
    const box = createSecretBox(makeKey());
    const encrypted = box.encryptCredential("");
    expect(box.decryptCredential(encrypted)).toBe("");
  });

  test("分支 - UTF-8 多字节字符可加密解密", () => {
    const box = createSecretBox(makeKey());
    const plaintext = "你好世界 🔑";
    const encrypted = box.encryptCredential(plaintext);
    expect(box.decryptCredential(encrypted)).toBe(plaintext);
  });

  test("异常 - 版本不匹配抛错", () => {
    const box = createSecretBox(makeKey());
    expect(() => box.decryptCredential("v2.abc.def")).toThrow("invalid encrypted credential format");
  });

  test("异常 - 缺少 nonce 段抛错", () => {
    const box = createSecretBox(makeKey());
    expect(() => box.decryptCredential("v1")).toThrow("invalid encrypted credential format");
  });

  test("异常 - 密钥不匹配解密失败", () => {
    const box1 = createSecretBox(makeKey());
    const box2 = createSecretBox(makeKey());
    const encrypted = box1.encryptCredential("secret");
    expect(() => box2.decryptCredential(encrypted)).toThrow("unable to decrypt");
  });

  test("异常 - 篡改密文解密失败", () => {
    const box = createSecretBox(makeKey());
    const encrypted = box.encryptCredential("secret");
    const parts = encrypted.split(".");
    // 篡改密文部分
    parts[2] = parts[2].slice(0, -2) + "XX";
    expect(() => box.decryptCredential(parts.join("."))).toThrow("unable to decrypt");
  });
});

describe("encryptApiKey / decryptApiKey", () => {
  test("正向 - 委托 encrypt/decrypt Credential 往返一致", () => {
    const box = createSecretBox(makeKey());
    const apiKey = "sk_live_abc123";
    const encrypted = box.encryptApiKey(apiKey);
    expect(box.decryptApiKey(encrypted)).toBe(apiKey);
  });

  test("异常 - 格式错误时 decryptApiKey 抛专用错误", () => {
    const box = createSecretBox(makeKey());
    expect(() => box.decryptApiKey("bad-format")).toThrow("unable to decrypt OpenSandbox API key");
  });
});
