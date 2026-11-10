// organization-schema-validation.test.ts — 组织创建/更新请求体字段校验
// 测试目标：CreateOrganizationBodySchema / UpdateOrganizationBodySchema 的字段约束
// 源码：packages/platform/identity/src/schemas/organization.schema.ts（main 325208eb）
// 业务意图：name/slug 只校验 trim 后非空且保留原始值；更新时顶层字段与 data 互斥

import { describe, test, expect } from "bun:test";

// ── 复制纯校验逻辑（zod refine / refine 等价实现）──

type FieldResult = { ok: true; value: Record<string, unknown> } | { ok: false; message: string };

function checkOrganizationFields(
  body: Record<string, unknown>,
  options: { partial: boolean },
): FieldResult {
  const out: Record<string, unknown> = {};
  for (const field of ["name", "slug"]) {
    const value = body[field];
    if (value === undefined) {
      if (!options.partial) {
        return { ok: false, message: `${field} is required` };
      }
      continue;
    }
    if (typeof value !== "string") {
      return { ok: false, message: `${field} must be a string` };
    }
    if (value.trim().length === 0) {
      return { ok: false, message: `${field} must not be empty` };
    }
    out[field] = value; // 只校验 trim 后非空，保留原始内容
  }
  return { ok: true, value: out };
}

function validateCreateBody(body: Record<string, unknown>): FieldResult {
  const fields = checkOrganizationFields(body, { partial: false });
  if (!fields.ok) {
    return fields;
  }
  if (body.description !== undefined && typeof body.description !== "string") {
    return { ok: false, message: "description must be a string" };
  }
  const out: Record<string, unknown> = { ...fields.value };
  if (body.description !== undefined) {
    out.description = body.description;
  }
  return { ok: true, value: out };
}

function validateUpdateBody(body: Record<string, unknown>): FieldResult {
  const fields = checkOrganizationFields(body, { partial: true });
  if (!fields.ok) {
    return fields;
  }
  const out: Record<string, unknown> = { ...fields.value };
  if (body.data !== undefined) {
    if (typeof body.data !== "object" || body.data === null || Array.isArray(body.data)) {
      return { ok: false, message: "data must be an object" };
    }
    const nested = checkOrganizationFields(body.data as Record<string, unknown>, { partial: true });
    if (!nested.ok) {
      return nested;
    }
    out.data = { ...(body.data as Record<string, unknown>), ...nested.value };
  }
  // refine：data 与顶层 name/slug 互斥
  if (out.data !== undefined && (out.name !== undefined || out.slug !== undefined)) {
    return { ok: false, message: "Provide name and slug either at the top level or inside data, not both" };
  }
  return { ok: true, value: out };
}

// ── 测试 ──

describe("组织创建参数", () => {
  test("合法名称与 Slug 通过", () => {
    const r = validateCreateBody({ name: "研发组织", slug: "rd-team" });
    expect(r).toEqual({ ok: true, value: { name: "研发组织", slug: "rd-team" } });
  });

  test("可选 description 原样保留", () => {
    const r = validateCreateBody({ name: "研发组织", slug: "rd-team", description: "负责平台研发" });
    expect(r).toEqual({ ok: true, value: { name: "研发组织", slug: "rd-team", description: "负责平台研发" } });
  });

  test("缺少 name 被拒绝", () => {
    const r = validateCreateBody({ slug: "rd-team" });
    expect(r).toEqual({ ok: false, message: "name is required" });
  });

  test("缺少 slug 被拒绝", () => {
    const r = validateCreateBody({ name: "研发组织" });
    expect(r).toEqual({ ok: false, message: "slug is required" });
  });

  test("空名称被拒绝", () => {
    const r = validateCreateBody({ name: "", slug: "rd-team" });
    expect(r).toEqual({ ok: false, message: "name must not be empty" });
  });

  test("纯空白名称被拒绝", () => {
    const r = validateCreateBody({ name: "   ", slug: "rd-team" });
    expect(r).toEqual({ ok: false, message: "name must not be empty" });
  });

  test("空 Slug 被拒绝", () => {
    const r = validateCreateBody({ name: "研发组织", slug: "" });
    expect(r).toEqual({ ok: false, message: "slug must not be empty" });
  });

  test("纯空白 Slug 被拒绝", () => {
    const r = validateCreateBody({ name: "研发组织", slug: " \t " });
    expect(r).toEqual({ ok: false, message: "slug must not be empty" });
  });

  test("名称不是字符串时按类型错误拒绝", () => {
    const r = validateCreateBody({ name: 123, slug: "rd-team" });
    expect(r).toEqual({ ok: false, message: "name must be a string" });
  });

  test("前后空格不改变原值（只校验 trim 后非空）", () => {
    const r = validateCreateBody({ name: "  研发组织  ", slug: "  rd-team  " });
    expect(r).toEqual({ ok: true, value: { name: "  研发组织  ", slug: "  rd-team  " } });
  });
});

describe("组织更新参数", () => {
  test("空对象视为合法部分更新", () => {
    expect(validateUpdateBody({})).toEqual({ ok: true, value: {} });
  });

  test("顶层 name 部分更新合法", () => {
    expect(validateUpdateBody({ name: "新名称" })).toEqual({ ok: true, value: { name: "新名称" } });
  });

  test("顶层 slug 部分更新合法", () => {
    expect(validateUpdateBody({ slug: "new-slug" })).toEqual({ ok: true, value: { slug: "new-slug" } });
  });

  test("data 内合法 name/slug 通过", () => {
    const r = validateUpdateBody({ data: { name: "新名称", slug: "new-slug" } });
    expect(r).toEqual({ ok: true, value: { data: { name: "新名称", slug: "new-slug" } } });
  });

  test("data 内其他组织属性原样透传", () => {
    const r = validateUpdateBody({ data: { metadata: { description: "说明" }, name: "新名称" } });
    expect(r).toEqual({
      ok: true,
      value: { data: { metadata: { description: "说明" }, name: "新名称" } },
    });
  });

  test("顶层空白 name 被拒绝", () => {
    expect(validateUpdateBody({ name: "  " })).toEqual({ ok: false, message: "name must not be empty" });
  });

  test("data 内空白 slug 被拒绝", () => {
    expect(validateUpdateBody({ data: { slug: "  " } })).toEqual({
      ok: false,
      message: "slug must not be empty",
    });
  });

  test("顶层字段与 data 混用被拒绝", () => {
    expect(validateUpdateBody({ name: "新名称", data: {} })).toEqual({
      ok: false,
      message: "Provide name and slug either at the top level or inside data, not both",
    });
    expect(validateUpdateBody({ slug: "new-slug", data: { metadata: {} } })).toEqual({
      ok: false,
      message: "Provide name and slug either at the top level or inside data, not both",
    });
  });
});
