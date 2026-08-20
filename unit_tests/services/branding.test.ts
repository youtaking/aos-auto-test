import { describe, test, expect } from "bun:test";

// --- Pure functions/constants copied from source ---

const DEFAULT_BRAND_NAME = "Fenix";

interface BrandingConfig {
  brandName: string;
  logoPath: string | null;
  logoUrl: string | null;
}

function getBrandingConfig(): BrandingConfig {
  const brandName = process.env.APP_BRAND_NAME?.trim() || DEFAULT_BRAND_NAME;
  const logoPath = process.env.APP_LOGO_PATH?.trim() || null;
  return {
    brandName,
    logoPath,
    logoUrl: logoPath ? "/web/branding/logo" : null,
  };
}

/** 解析品牌 logo 文件路径：未配置或文件不存在时返回 null */
function resolveBrandLogoFile(existsSync: (path: string) => boolean): string | null {
  const { logoPath } = getBrandingConfig();
  if (!logoPath) return null;
  return existsSync(logoPath) ? logoPath : null;
}

// --- Helper ---

function withEnv(overrides: Record<string, string | undefined>, fn: () => void) {
  const saved: Record<string, string | undefined> = {};
  for (const key of Object.keys(overrides)) {
    saved[key] = process.env[key];
    if (overrides[key] === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = overrides[key];
    }
  }
  try {
    fn();
  } finally {
    for (const key of Object.keys(saved)) {
      if (saved[key] === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = saved[key];
      }
    }
  }
}

// --- Tests ---

describe("DEFAULT_BRAND_NAME", () => {
  test("is Fenix", () => {
    expect(DEFAULT_BRAND_NAME).toBe("Fenix");
  });
});

describe("getBrandingConfig", () => {
  test("returns default config when no env vars are set", () => {
    withEnv({ APP_BRAND_NAME: undefined, APP_LOGO_PATH: undefined }, () => {
      const config = getBrandingConfig();
      expect(config.brandName).toBe("Fenix");
      expect(config.logoPath).toBeNull();
      expect(config.logoUrl).toBeNull();
    });
  });

  test("uses custom brand name from APP_BRAND_NAME", () => {
    withEnv({ APP_BRAND_NAME: "MyBrand", APP_LOGO_PATH: undefined }, () => {
      const config = getBrandingConfig();
      expect(config.brandName).toBe("MyBrand");
    });
  });

  test("trims brand name whitespace", () => {
    withEnv({ APP_BRAND_NAME: "  Trimmed  ", APP_LOGO_PATH: undefined }, () => {
      const config = getBrandingConfig();
      expect(config.brandName).toBe("Trimmed");
    });
  });

  test("falls back to default for whitespace-only brand name", () => {
    withEnv({ APP_BRAND_NAME: "   ", APP_LOGO_PATH: undefined }, () => {
      const config = getBrandingConfig();
      expect(config.brandName).toBe("Fenix");
    });
  });

  test("falls back to default for empty brand name", () => {
    withEnv({ APP_BRAND_NAME: "", APP_LOGO_PATH: undefined }, () => {
      const config = getBrandingConfig();
      expect(config.brandName).toBe("Fenix");
    });
  });

  test("uses logo path from APP_LOGO_PATH", () => {
    withEnv({ APP_BRAND_NAME: undefined, APP_LOGO_PATH: "/assets/logo.png" }, () => {
      const config = getBrandingConfig();
      expect(config.logoPath).toBe("/assets/logo.png");
    });
  });

  test("logoUrl is derived from logoPath when logoPath is set", () => {
    withEnv({ APP_BRAND_NAME: undefined, APP_LOGO_PATH: "/assets/logo.png" }, () => {
      const config = getBrandingConfig();
      expect(config.logoUrl).toBe("/web/branding/logo");
    });
  });

  test("logoUrl is null when logoPath is not set", () => {
    withEnv({ APP_BRAND_NAME: undefined, APP_LOGO_PATH: undefined }, () => {
      const config = getBrandingConfig();
      expect(config.logoUrl).toBeNull();
    });
  });

  test("logoUrl is null when logoPath is whitespace-only", () => {
    withEnv({ APP_BRAND_NAME: undefined, APP_LOGO_PATH: "   " }, () => {
      const config = getBrandingConfig();
      expect(config.logoPath).toBeNull();
      expect(config.logoUrl).toBeNull();
    });
  });

  test("logoUrl is null when logoPath is empty string", () => {
    withEnv({ APP_BRAND_NAME: undefined, APP_LOGO_PATH: "" }, () => {
      const config = getBrandingConfig();
      expect(config.logoPath).toBeNull();
      expect(config.logoUrl).toBeNull();
    });
  });

  test("trims logo path whitespace", () => {
    withEnv({ APP_BRAND_NAME: undefined, APP_LOGO_PATH: "  /logo.png  " }, () => {
      const config = getBrandingConfig();
      expect(config.logoPath).toBe("/logo.png");
      expect(config.logoUrl).toBe("/web/branding/logo");
    });
  });

  test("full config with all env vars set", () => {
    withEnv({ APP_BRAND_NAME: "Acme Corp", APP_LOGO_PATH: "/images/acme.svg" }, () => {
      const config = getBrandingConfig();
      expect(config).toEqual({
        brandName: "Acme Corp",
        logoPath: "/images/acme.svg",
        logoUrl: "/web/branding/logo",
      });
    });
  });
});

describe("resolveBrandLogoFile", () => {
  test("未配置 logoPath 时返回 null", () => {
    withEnv({ APP_LOGO_PATH: undefined }, () => {
      expect(resolveBrandLogoFile(() => true)).toBeNull();
    });
  });

  test("空白 logoPath 返回 null", () => {
    withEnv({ APP_BRAND_NAME: undefined, APP_LOGO_PATH: "   " }, () => {
      expect(resolveBrandLogoFile(() => true)).toBeNull();
    });
  });

  test("logoPath 存在且文件在磁盘上存在时返回路径", () => {
    withEnv({ APP_LOGO_PATH: "/var/assets/logo.png" }, () => {
      expect(resolveBrandLogoFile((p) => p === "/var/assets/logo.png")).toBe("/var/assets/logo.png");
    });
  });

  test("logoPath 配置但文件不存在时返回 null", () => {
    withEnv({ APP_LOGO_PATH: "/missing/logo.png" }, () => {
      expect(resolveBrandLogoFile(() => false)).toBeNull();
    });
  });

  test("将已解析的 logoPath 传递给 existsSync（已 trim）", () => {
    withEnv({ APP_LOGO_PATH: "  /trimmed/path.svg  " }, () => {
      const checkedPaths: string[] = [];
      resolveBrandLogoFile((p) => {
        checkedPaths.push(p);
        return true;
      });
      expect(checkedPaths).toEqual(["/trimmed/path.svg"]);
    });
  });

  test("existsSync 不被调用当 logoPath 为 null", () => {
    withEnv({ APP_LOGO_PATH: undefined }, () => {
      let called = false;
      resolveBrandLogoFile(() => {
        called = true;
        return true;
      });
      expect(called).toBe(false);
    });
  });
});
