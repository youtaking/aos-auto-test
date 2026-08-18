import { describe, test, expect } from "bun:test";
import { createHmac, timingSafeEqual } from "node:crypto";

// --- Pure functions/types copied from source ---

interface SkillTokenInput { id: string; organizationId: string; name: string; }
interface SkillDownloadPayload {
  type: "skill-download";
  skillId: string;
  organizationId: string;
  skillName: string;
  iat: number;
  exp: number;
}

const TEST_SIGNING_KEY = "test-signing-key-for-unit-tests";

function signPayload(encodedPayload: string, key: string): string {
  return createHmac("sha256", key).update(encodedPayload).digest("base64url");
}

function generateSkillDownloadToken(skill: SkillTokenInput, options?: { expiresInSeconds?: number }): string {
  const iat = Math.floor(Date.now() / 1000);
  const payload: SkillDownloadPayload = {
    type: "skill-download",
    skillId: skill.id,
    organizationId: skill.organizationId,
    skillName: skill.name,
    iat,
    exp: iat + (options?.expiresInSeconds ?? 300),
  };
  const encodedPayload = Buffer.from(JSON.stringify(payload), "utf-8").toString("base64url");
  return `${encodedPayload}.${signPayload(encodedPayload, TEST_SIGNING_KEY)}`;
}

function verifySkillDownloadToken(token: string): SkillDownloadPayload | null {
  const [encodedPayload, signature, extra] = token.split(".");
  if (!encodedPayload || !signature || extra !== undefined) return null;
  const expected = signPayload(encodedPayload, TEST_SIGNING_KEY);
  const signatureBuffer = Buffer.from(signature);
  const expectedBuffer = Buffer.from(expected);
  if (signatureBuffer.length !== expectedBuffer.length || !timingSafeEqual(signatureBuffer, expectedBuffer)) return null;
  try {
    const payload = JSON.parse(Buffer.from(encodedPayload, "base64url").toString("utf-8")) as Partial<SkillDownloadPayload>;
    if (
      payload.type !== "skill-download" ||
      typeof payload.skillId !== "string" ||
      typeof payload.organizationId !== "string" ||
      typeof payload.skillName !== "string" ||
      typeof payload.exp !== "number" ||
      payload.exp < Math.floor(Date.now() / 1000)
    ) return null;
    return payload as SkillDownloadPayload;
  } catch { return null; }
}

// --- Tests ---

const SAMPLE_SKILL: SkillTokenInput = {
  id: "skill-001",
  organizationId: "org-abc",
  name: "My Skill",
};

describe("generateSkillDownloadToken", () => {
  test("produces token with two parts separated by dot", () => {
    const token = generateSkillDownloadToken(SAMPLE_SKILL);
    const parts = token.split(".");
    expect(parts).toHaveLength(2);
    expect(parts[0].length).toBeGreaterThan(0);
    expect(parts[1].length).toBeGreaterThan(0);
  });

  test("payload part is valid base64url-encoded JSON", () => {
    const token = generateSkillDownloadToken(SAMPLE_SKILL);
    const [encodedPayload] = token.split(".");
    const decoded = Buffer.from(encodedPayload, "base64url").toString("utf-8");
    const payload = JSON.parse(decoded);
    expect(payload.type).toBe("skill-download");
    expect(payload.skillId).toBe("skill-001");
    expect(payload.organizationId).toBe("org-abc");
    expect(payload.skillName).toBe("My Skill");
  });

  test("payload contains iat and exp timestamps", () => {
    const before = Math.floor(Date.now() / 1000);
    const token = generateSkillDownloadToken(SAMPLE_SKILL);
    const after = Math.floor(Date.now() / 1000);

    const [encodedPayload] = token.split(".");
    const payload = JSON.parse(Buffer.from(encodedPayload, "base64url").toString("utf-8"));

    expect(payload.iat).toBeGreaterThanOrEqual(before);
    expect(payload.iat).toBeLessThanOrEqual(after);
    expect(payload.exp).toBe(payload.iat + 300); // default 300s
  });

  test("custom expiration is respected", () => {
    const before = Math.floor(Date.now() / 1000);
    const token = generateSkillDownloadToken(SAMPLE_SKILL, { expiresInSeconds: 600 });
    const after = Math.floor(Date.now() / 1000);

    const [encodedPayload] = token.split(".");
    const payload = JSON.parse(Buffer.from(encodedPayload, "base64url").toString("utf-8"));

    expect(payload.exp).toBeGreaterThanOrEqual(before + 600);
    expect(payload.exp).toBeLessThanOrEqual(after + 600);
  });
});

describe("verifySkillDownloadToken", () => {
  test("verifies a valid token and returns payload", () => {
    const token = generateSkillDownloadToken(SAMPLE_SKILL);
    const result = verifySkillDownloadToken(token);
    expect(result).not.toBeNull();
    expect(result!.type).toBe("skill-download");
    expect(result!.skillId).toBe("skill-001");
    expect(result!.organizationId).toBe("org-abc");
    expect(result!.skillName).toBe("My Skill");
    expect(typeof result!.iat).toBe("number");
    expect(typeof result!.exp).toBe("number");
  });

  test("returns null for expired token", () => {
    // Generate a token that expired 10 seconds ago
    const iat = Math.floor(Date.now() / 1000) - 20;
    const payload: SkillDownloadPayload = {
      type: "skill-download",
      skillId: "skill-001",
      organizationId: "org-abc",
      skillName: "My Skill",
      iat,
      exp: iat + 5, // expired 15 seconds ago
    };
    const encodedPayload = Buffer.from(JSON.stringify(payload), "utf-8").toString("base64url");
    const token = `${encodedPayload}.${signPayload(encodedPayload, TEST_SIGNING_KEY)}`;

    const result = verifySkillDownloadToken(token);
    expect(result).toBeNull();
  });

  test("returns null for tampered signature", () => {
    const token = generateSkillDownloadToken(SAMPLE_SKILL);
    const [encodedPayload] = token.split(".");
    // Use a wrong signature
    const tamperedToken = `${encodedPayload}.AAAA_tampered_signature_AAAA`;
    const result = verifySkillDownloadToken(tamperedToken);
    expect(result).toBeNull();
  });

  test("returns null for tampered payload", () => {
    const token = generateSkillDownloadToken(SAMPLE_SKILL);
    const [, signature] = token.split(".");
    // Create a different payload but keep the old signature
    const tamperedPayload: SkillDownloadPayload = {
      type: "skill-download",
      skillId: "skill-HACKED",
      organizationId: "org-HACKED",
      skillName: "Hacked Skill",
      iat: Math.floor(Date.now() / 1000),
      exp: Math.floor(Date.now() / 1000) + 300,
    };
    const encodedTampered = Buffer.from(JSON.stringify(tamperedPayload), "utf-8").toString("base64url");
    const tamperedToken = `${encodedTampered}.${signature}`;
    const result = verifySkillDownloadToken(tamperedToken);
    expect(result).toBeNull();
  });

  test("returns null for token with missing parts (no dot)", () => {
    expect(verifySkillDownloadToken("nodotshere")).toBeNull();
  });

  test("returns null for token with extra parts (three dots)", () => {
    const token = generateSkillDownloadToken(SAMPLE_SKILL);
    const extraToken = `${token}.extra`;
    expect(verifySkillDownloadToken(extraToken)).toBeNull();
  });

  test("returns null for empty string", () => {
    expect(verifySkillDownloadToken("")).toBeNull();
  });

  test("returns null for token with empty payload part", () => {
    expect(verifySkillDownloadToken(".signature")).toBeNull();
  });

  test("returns null for token with empty signature part", () => {
    expect(verifySkillDownloadToken("payload.")).toBeNull();
  });

  test("returns null for invalid base64url in payload", () => {
    // Create a token with valid structure but invalid JSON inside
    const badPayload = Buffer.from("not json at all!!!").toString("base64url");
    const sig = signPayload(badPayload, TEST_SIGNING_KEY);
    const token = `${badPayload}.${sig}`;
    expect(verifySkillDownloadToken(token)).toBeNull();
  });

  test("returns null when payload type is wrong", () => {
    const payload = {
      type: "wrong-type",
      skillId: "skill-001",
      organizationId: "org-abc",
      skillName: "My Skill",
      iat: Math.floor(Date.now() / 1000),
      exp: Math.floor(Date.now() / 1000) + 300,
    };
    const encodedPayload = Buffer.from(JSON.stringify(payload), "utf-8").toString("base64url");
    const token = `${encodedPayload}.${signPayload(encodedPayload, TEST_SIGNING_KEY)}`;
    expect(verifySkillDownloadToken(token)).toBeNull();
  });

  test("payload contains correct skill data", () => {
    const skill: SkillTokenInput = {
      id: "skill-xyz-789",
      organizationId: "org-123",
      name: "Special Skill Name",
    };
    const token = generateSkillDownloadToken(skill);
    const result = verifySkillDownloadToken(token);
    expect(result).not.toBeNull();
    expect(result!.skillId).toBe("skill-xyz-789");
    expect(result!.organizationId).toBe("org-123");
    expect(result!.skillName).toBe("Special Skill Name");
  });

  test("custom expiration is reflected in verified payload", () => {
    const before = Math.floor(Date.now() / 1000);
    const token = generateSkillDownloadToken(SAMPLE_SKILL, { expiresInSeconds: 120 });
    const after = Math.floor(Date.now() / 1000);

    const result = verifySkillDownloadToken(token);
    expect(result).not.toBeNull();
    expect(result!.exp).toBeGreaterThanOrEqual(before + 120);
    expect(result!.exp).toBeLessThanOrEqual(after + 120);
  });
});
