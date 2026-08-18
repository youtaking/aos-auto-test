import { describe, test, expect } from "bun:test";

// ── Pure function copy from src/services/org-context.ts ──
// Source version: FenixAgent/src/services/org-context.ts (commit f5ac00e, 2025-08)
//
// Test adaptation (function signature):
//   Source: `extractActiveOrgId(request: Request): string | null` — takes a Request object
//   Test:   `extractActiveOrgId(requestUrl: string, headers: Record<string, string | undefined>): string | null`
//   Rationale: Avoids constructing Request objects in unit tests. The extraction logic
//   (header > query param > cookie) is identical — only the data source differs.
//   Source reads `request.headers.get("x-active-org-id")` → test reads `headers["x-active-org-id"]`.
//   Source reads `request.headers.get("cookie")` → test reads `headers["cookie"]`.
//   Source reads `new URL(request.url)` → test reads `new URL(requestUrl)`.

/**
 * Extracts the active organization ID from request headers/URL.
 * Priority: x-active-org-id header > URL query param > cookie.
 */
function extractActiveOrgId(
  requestUrl: string,
  headers: Record<string, string | undefined>,
): string | null {
  const header = headers["x-active-org-id"];
  if (header) return header;

  const url = new URL(requestUrl);
  const query = url.searchParams.get("activeOrganizationId");
  if (query) return query;

  const cookie = headers["cookie"]?.match(/(?:^|;\s*)active_org_id=([^;]+)/)?.[1];
  if (cookie) return cookie;

  return null;
}

// ── Tests ──

describe("extractActiveOrgId", () => {
  const baseUrl = "http://localhost:3000/api/agents";

  test("header takes priority over query and cookie", () => {
    const url = `${baseUrl}?activeOrganizationId=from-query`;
    const headers = {
      "x-active-org-id": "from-header",
      cookie: "active_org_id=from-cookie",
    };
    expect(extractActiveOrgId(url, headers)).toBe("from-header");
  });

  test("query param used when header is absent", () => {
    const url = `${baseUrl}?activeOrganizationId=org-query-123`;
    const headers: Record<string, string | undefined> = {};
    expect(extractActiveOrgId(url, headers)).toBe("org-query-123");
  });

  test("query param takes priority over cookie", () => {
    const url = `${baseUrl}?activeOrganizationId=org-query`;
    const headers = {
      cookie: "active_org_id=org-cookie",
    };
    expect(extractActiveOrgId(url, headers)).toBe("org-query");
  });

  test("cookie used when header and query are absent", () => {
    const headers = {
      cookie: "active_org_id=org-cookie-456",
    };
    expect(extractActiveOrgId(baseUrl, headers)).toBe("org-cookie-456");
  });

  test("cookie with other cookies present", () => {
    const headers = {
      cookie: "session=abc123; active_org_id=org-mixed; theme=dark",
    };
    expect(extractActiveOrgId(baseUrl, headers)).toBe("org-mixed");
  });

  test("cookie at the beginning", () => {
    const headers = {
      cookie: "active_org_id=org-first; other=val",
    };
    expect(extractActiveOrgId(baseUrl, headers)).toBe("org-first");
  });

  test("cookie at the end", () => {
    const headers = {
      cookie: "other=val; active_org_id=org-last",
    };
    expect(extractActiveOrgId(baseUrl, headers)).toBe("org-last");
  });

  test("returns null when nothing found", () => {
    const headers: Record<string, string | undefined> = {};
    expect(extractActiveOrgId(baseUrl, headers)).toBeNull();
  });

  test("returns null when cookie exists but has no active_org_id", () => {
    const headers = {
      cookie: "session=abc; theme=dark",
    };
    expect(extractActiveOrgId(baseUrl, headers)).toBeNull();
  });

  test("returns null when header is empty string", () => {
    const headers = {
      "x-active-org-id": "",
    };
    expect(extractActiveOrgId(baseUrl, headers)).toBeNull();
  });

  test("returns null when URL has no query param and no headers", () => {
    expect(extractActiveOrgId(baseUrl, {})).toBeNull();
  });

  test("URL with unrelated query params returns null", () => {
    const url = `${baseUrl}?foo=bar&baz=qux`;
    expect(extractActiveOrgId(url, {})).toBeNull();
  });

  test("header value is returned as-is without trimming", () => {
    const headers = {
      "x-active-org-id": " org-spaces ",
    };
    expect(extractActiveOrgId(baseUrl, headers)).toBe(" org-spaces ");
  });

  // ── Boundary tests ──

  test("query param with empty string falls through to cookie", () => {
    const url = `${baseUrl}?activeOrganizationId=`;
    const headers = {
      cookie: "active_org_id=from-cookie",
    };
    // Empty query param is falsy, so cookie takes precedence
    expect(extractActiveOrgId(url, headers)).toBe("from-cookie");
  });

  test("multiple activeOrganizationId query params returns first", () => {
    const url = `${baseUrl}?activeOrganizationId=first&activeOrganizationId=second`;
    expect(extractActiveOrgId(url, {})).toBe("first");
  });

  test("cookie value with encoded characters", () => {
    const headers = {
      cookie: "active_org_id=org%2D123",
    };
    // Cookie regex captures raw value (no URL decoding)
    expect(extractActiveOrgId(baseUrl, headers)).toBe("org%2D123");
  });
});
