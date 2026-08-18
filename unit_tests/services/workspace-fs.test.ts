import { describe, test, expect } from "bun:test";
import { createHash } from "node:crypto";

// ── Pure function copies from src/services/workspace-fs.ts ──

const TEXT_EXTENSIONS = new Set([
  ".txt", ".md", ".json", ".yaml", ".yml", ".ts", ".js", ".tsx", ".jsx",
  ".py", ".go", ".rs", ".css", ".html", ".xml", ".toml", ".ini",
  ".properties", ".cfg", ".sh", ".bash", ".zsh", ".sql", ".env",
]);

const MIME_TYPES: Record<string, string> = {
  ".html": "text/html", ".htm": "text/html", ".css": "text/css",
  ".js": "text/javascript", ".ts": "text/typescript", ".tsx": "text/typescript",
  ".jsx": "text/javascript", ".json": "application/json", ".xml": "application/xml",
  ".txt": "text/plain", ".md": "text/plain", ".yaml": "text/plain",
  ".yml": "text/plain", ".py": "text/plain", ".go": "text/plain",
  ".rs": "text/plain", ".sh": "text/plain", ".bash": "text/plain",
  ".zsh": "text/plain", ".sql": "text/plain", ".csv": "text/csv",
  ".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg", ".gif": "image/gif", ".svg": "image/svg+xml",
  ".webp": "image/webp", ".ico": "image/x-icon", ".mp4": "video/mp4",
  ".webm": "video/webm", ".mp3": "audio/mpeg", ".wav": "audio/wav",
};

const WORKSPACE_BLACKLIST = new Set([
  ".git", "node_modules", "dist", "build", "target", "out",
  ".next", ".nuxt", ".venv", "venv", "__pycache__",
  ".cache", ".pytest_cache", "vendor", ".terraform",
  ".idea", ".vscode", "coverage", ".nyc_output",
  ".opencode", ".claude", ".peri", ".mcp.json",
  "CLAUDE.md", ".tmp", "tmp", ".turbo",
]);

function isUserPath(path: string): boolean {
  return path === "" || path === "user" || path.startsWith("user/");
}

function normalizeUserRoutePath(path: string): string {
  let normalized: string;
  try {
    normalized = decodeURIComponent(path.trim());
  } catch {
    normalized = path.trim();
  }
  if (!normalized) return "user";
  if (normalized === "user" || normalized.startsWith("user/")) return normalized;
  if (normalized.startsWith(".")) return normalized;
  return `user/${normalized}`;
}

function getMimeType(ext: string): string {
  return MIME_TYPES[ext] || "application/octet-stream";
}

function isTextExtension(ext: string): boolean {
  return TEXT_EXTENSIONS.has(ext);
}

function hashOf(input: string): string {
  return createHash("sha1").update(input).digest("hex");
}

function computeTreeFingerprint(paths: string[], mtimes?: Record<string, number>): string {
  const pathHash = hashOf([...paths].sort().join("\n"));
  let maxMtime = 0;
  if (mtimes) for (const t of Object.values(mtimes)) if (t > maxMtime) maxMtime = t;
  return `"${pathHash}-${maxMtime}-${paths.length}"`;
}

function computeListFingerprint(
  entries: Array<{ name: string; type: string; size: number; modifiedAt?: number }>,
): string {
  const hasMtime = entries.some((e) => (e.modifiedAt ?? 0) > 0);
  const lines = entries.map((e) => {
    const base = `${e.name}|${e.type}|${e.size}`;
    return hasMtime ? `${base}|${e.modifiedAt ?? 0}` : base;
  });
  return `"${hashOf(lines.join("\n"))}-${lines.length}"`;
}

function computeReadFingerprint(size: number, mtimeMs?: number): string {
  return mtimeMs !== undefined && mtimeMs > 0 ? `"${size}-${mtimeMs}"` : `"${size}"`;
}

function shouldHideEntry(_entryPath: string, name: string): boolean {
  return WORKSPACE_BLACKLIST.has(name);
}

function shouldHidePath(path: string): boolean {
  return path
    .split("/")
    .filter(Boolean)
    .some((name) => WORKSPACE_BLACKLIST.has(name));
}

// ── Tests ──

describe("isUserPath", () => {
  test("empty string is user path", () => {
    expect(isUserPath("")).toBe(true);
  });

  test("'user' is user path", () => {
    expect(isUserPath("user")).toBe(true);
  });

  test("'user/subdir' is user path", () => {
    expect(isUserPath("user/subdir")).toBe(true);
  });

  test("'user/a/b/c' is user path", () => {
    expect(isUserPath("user/a/b/c")).toBe(true);
  });

  test("'agents' is not user path", () => {
    expect(isUserPath("agents")).toBe(false);
  });

  test("'username' is not user path (prefix but not user/)", () => {
    expect(isUserPath("username")).toBe(false);
  });

  test("'User/file' is not user path (case-sensitive)", () => {
    expect(isUserPath("User/file")).toBe(false);
  });
});

describe("normalizeUserRoutePath", () => {
  test("empty string becomes 'user'", () => {
    expect(normalizeUserRoutePath("")).toBe("user");
  });

  test("whitespace-only becomes 'user'", () => {
    expect(normalizeUserRoutePath("   ")).toBe("user");
  });

  test("'user' stays as 'user'", () => {
    expect(normalizeUserRoutePath("user")).toBe("user");
  });

  test("'user/path' stays unchanged", () => {
    expect(normalizeUserRoutePath("user/path")).toBe("user/path");
  });

  test("plain path gets 'user/' prefix", () => {
    expect(normalizeUserRoutePath("myfile.txt")).toBe("user/myfile.txt");
  });

  test("dot-prefixed path stays as-is", () => {
    expect(normalizeUserRoutePath(".env")).toBe(".env");
  });

  test("URL-encoded characters are decoded", () => {
    expect(normalizeUserRoutePath("user/%28test%29")).toBe("user/(test)");
  });

  test("URL-encoded Chinese characters are decoded", () => {
    expect(normalizeUserRoutePath("user/%E5%9F%83%E7%91%9E")).toBe("user/埃瑞");
  });

  test("nested path without user prefix gets 'user/' added", () => {
    expect(normalizeUserRoutePath("a/b/c")).toBe("user/a/b/c");
  });

  test("trims whitespace", () => {
    expect(normalizeUserRoutePath("  hello  ")).toBe("user/hello");
  });
});

describe("getMimeType", () => {
  test("returns correct MIME for known extensions", () => {
    expect(getMimeType(".html")).toBe("text/html");
    expect(getMimeType(".json")).toBe("application/json");
    expect(getMimeType(".png")).toBe("image/png");
    expect(getMimeType(".pdf")).toBe("application/pdf");
    expect(getMimeType(".mp4")).toBe("video/mp4");
    expect(getMimeType(".mp3")).toBe("audio/mpeg");
  });

  test("returns 'application/octet-stream' for unknown extensions", () => {
    expect(getMimeType(".xyz")).toBe("application/octet-stream");
    expect(getMimeType(".unknown")).toBe("application/octet-stream");
  });

  test("returns 'application/octet-stream' for empty string", () => {
    expect(getMimeType("")).toBe("application/octet-stream");
  });

  test("TypeScript and JavaScript types", () => {
    expect(getMimeType(".ts")).toBe("text/typescript");
    expect(getMimeType(".tsx")).toBe("text/typescript");
    expect(getMimeType(".js")).toBe("text/javascript");
    expect(getMimeType(".jsx")).toBe("text/javascript");
  });
});

describe("isTextExtension", () => {
  test("known text extensions return true", () => {
    expect(isTextExtension(".txt")).toBe(true);
    expect(isTextExtension(".md")).toBe(true);
    expect(isTextExtension(".json")).toBe(true);
    expect(isTextExtension(".py")).toBe(true);
    expect(isTextExtension(".ts")).toBe(true);
    expect(isTextExtension(".yaml")).toBe(true);
    expect(isTextExtension(".sql")).toBe(true);
    expect(isTextExtension(".env")).toBe(true);
  });

  test("non-text extensions return false", () => {
    expect(isTextExtension(".png")).toBe(false);
    expect(isTextExtension(".pdf")).toBe(false);
    expect(isTextExtension(".mp4")).toBe(false);
  });

  test("unknown extensions return false", () => {
    expect(isTextExtension(".xyz")).toBe(false);
    expect(isTextExtension("")).toBe(false);
  });
});

describe("computeTreeFingerprint", () => {
  test("returns ETag-formatted string", () => {
    const fp = computeTreeFingerprint(["a.txt", "b.txt"]);
    expect(fp).toMatch(/^"[a-f0-9]+-\d+-\d+"$/);
  });

  test("same paths produce same fingerprint", () => {
    const fp1 = computeTreeFingerprint(["a.txt", "b.txt"]);
    const fp2 = computeTreeFingerprint(["a.txt", "b.txt"]);
    expect(fp1).toBe(fp2);
  });

  test("different order produces same fingerprint (paths are sorted)", () => {
    const fp1 = computeTreeFingerprint(["b.txt", "a.txt"]);
    const fp2 = computeTreeFingerprint(["a.txt", "b.txt"]);
    expect(fp1).toBe(fp2);
  });

  test("different paths produce different fingerprints", () => {
    const fp1 = computeTreeFingerprint(["a.txt"]);
    const fp2 = computeTreeFingerprint(["b.txt"]);
    expect(fp1).not.toBe(fp2);
  });

  test("rename changes fingerprint (path hash includes names)", () => {
    const fp1 = computeTreeFingerprint(["old.txt"], { "old.txt": 1000 });
    const fp2 = computeTreeFingerprint(["new.txt"], { "new.txt": 1000 });
    expect(fp1).not.toBe(fp2);
  });

  test("mtimes affect fingerprint", () => {
    const fp1 = computeTreeFingerprint(["a.txt"], { "a.txt": 1000 });
    const fp2 = computeTreeFingerprint(["a.txt"], { "a.txt": 2000 });
    expect(fp1).not.toBe(fp2);
  });

  test("path count is included in fingerprint", () => {
    const fp1 = computeTreeFingerprint(["a.txt"]);
    const fp2 = computeTreeFingerprint(["a.txt", "b.txt"]);
    expect(fp1).not.toBe(fp2);
  });

  test("empty paths array produces valid fingerprint", () => {
    const fp = computeTreeFingerprint([]);
    expect(fp).toMatch(/^"[a-f0-9]+-0-0"$/);
  });

  test("missing mtimes defaults maxMtime to 0", () => {
    const fp = computeTreeFingerprint(["a.txt"]);
    expect(fp).toContain("-0-1");
  });
});

describe("computeListFingerprint", () => {
  test("returns ETag-formatted string", () => {
    const fp = computeListFingerprint([
      { name: "a.txt", type: "file", size: 100, modifiedAt: 1000 },
    ]);
    expect(fp).toMatch(/^"[a-f0-9]+-\d+"$/);
  });

  test("same entries produce same fingerprint", () => {
    const entries = [{ name: "a.txt", type: "file", size: 100, modifiedAt: 1000 }];
    expect(computeListFingerprint(entries)).toBe(computeListFingerprint(entries));
  });

  test("different entries produce different fingerprints", () => {
    const e1 = [{ name: "a.txt", type: "file", size: 100, modifiedAt: 1000 }];
    const e2 = [{ name: "b.txt", type: "file", size: 100, modifiedAt: 1000 }];
    expect(computeListFingerprint(e1)).not.toBe(computeListFingerprint(e2));
  });

  test("size change affects fingerprint", () => {
    const e1 = [{ name: "a.txt", type: "file", size: 100, modifiedAt: 1000 }];
    const e2 = [{ name: "a.txt", type: "file", size: 200, modifiedAt: 1000 }];
    expect(computeListFingerprint(e1)).not.toBe(computeListFingerprint(e2));
  });

  test("mtime change affects fingerprint when mtimes present", () => {
    const e1 = [{ name: "a.txt", type: "file", size: 100, modifiedAt: 1000 }];
    const e2 = [{ name: "a.txt", type: "file", size: 100, modifiedAt: 2000 }];
    expect(computeListFingerprint(e1)).not.toBe(computeListFingerprint(e2));
  });

  test("degrades gracefully when no mtimes (all 0)", () => {
    const entries = [{ name: "a.txt", type: "file", size: 100 }];
    const fp = computeListFingerprint(entries);
    expect(fp).toMatch(/^"[a-f0-9]+-\d+"$/);
  });

  test("entry count is in fingerprint", () => {
    const e1 = [{ name: "a.txt", type: "file", size: 100, modifiedAt: 1000 }];
    const e2 = [
      { name: "a.txt", type: "file", size: 100, modifiedAt: 1000 },
      { name: "b.txt", type: "file", size: 50, modifiedAt: 1000 },
    ];
    expect(computeListFingerprint(e1)).not.toBe(computeListFingerprint(e2));
  });

  test("empty entries produce valid fingerprint", () => {
    const fp = computeListFingerprint([]);
    expect(fp).toMatch(/^"[a-f0-9]+-0"$/);
  });
});

describe("computeReadFingerprint", () => {
  test("with size and mtime", () => {
    expect(computeReadFingerprint(1024, 1700000000000)).toBe('"1024-1700000000000"');
  });

  test("with size only (no mtime)", () => {
    expect(computeReadFingerprint(1024)).toBe('"1024"');
  });

  test("with mtime = 0 degrades to size-only", () => {
    expect(computeReadFingerprint(1024, 0)).toBe('"1024"');
  });

  test("with size = 0 and valid mtime", () => {
    expect(computeReadFingerprint(0, 1000)).toBe('"0-1000"');
  });

  test("with size = 0 and no mtime", () => {
    expect(computeReadFingerprint(0)).toBe('"0"');
  });
});

describe("shouldHideEntry", () => {
  test("blacklisted names are hidden", () => {
    expect(shouldHideEntry("/any/path", ".git")).toBe(true);
    expect(shouldHideEntry("/any/path", "node_modules")).toBe(true);
    expect(shouldHideEntry("/any/path", "dist")).toBe(true);
    expect(shouldHideEntry("/any/path", ".venv")).toBe(true);
    expect(shouldHideEntry("/any/path", "__pycache__")).toBe(true);
    expect(shouldHideEntry("/any/path", ".claude")).toBe(true);
    expect(shouldHideEntry("/any/path", "CLAUDE.md")).toBe(true);
  });

  test("non-blacklisted names are visible", () => {
    expect(shouldHideEntry("/any/path", "src")).toBe(false);
    expect(shouldHideEntry("/any/path", "package.json")).toBe(false);
    expect(shouldHideEntry("/any/path", "README.md")).toBe(false);
  });

  test("blacklist is name-based, not path-based", () => {
    expect(shouldHideEntry("/workspace/node_modules/pkg", "index.js")).toBe(false);
  });
});

describe("shouldHidePath", () => {
  test("path containing blacklisted segment is hidden", () => {
    expect(shouldHidePath("node_modules/pkg/index.js")).toBe(true);
    expect(shouldHidePath("src/.git/config")).toBe(true);
    expect(shouldHidePath(".venv/bin/python")).toBe(true);
  });

  test("path with no blacklisted segments is visible", () => {
    expect(shouldHidePath("src/index.ts")).toBe(false);
    expect(shouldHidePath("package.json")).toBe(false);
    expect(shouldHidePath("a/b/c")).toBe(false);
  });

  test("handles leading/trailing slashes", () => {
    expect(shouldHidePath("/node_modules/")).toBe(true);
    expect(shouldHidePath("/src/file.ts")).toBe(false);
  });

  test("empty path is not hidden", () => {
    expect(shouldHidePath("")).toBe(false);
  });

  test("exact blacklisted name as path", () => {
    expect(shouldHidePath("node_modules")).toBe(true);
    expect(shouldHidePath(".git")).toBe(true);
  });
});
