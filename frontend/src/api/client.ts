import axios from "axios";
import type { ApiResponse } from "./types";

const client = axios.create({
  baseURL: "/api",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

export async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const resp = await client.get<ApiResponse<T>>(url, { params });
  if (!resp.data.success) throw new Error(resp.data.error ?? "请求失败");
  return resp.data.data;
}

export async function post<T>(url: string, data?: unknown): Promise<T> {
  const resp = await client.post<ApiResponse<T>>(url, data);
  if (!resp.data.success) throw new Error(resp.data.error ?? "请求失败");
  return resp.data.data;
}

export async function put<T>(url: string, data?: unknown): Promise<T> {
  const resp = await client.put<ApiResponse<T>>(url, data);
  if (!resp.data.success) throw new Error(resp.data.error ?? "请求失败");
  return resp.data.data;
}

export async function del<T>(url: string): Promise<T> {
  const resp = await client.delete<ApiResponse<T>>(url);
  if (!resp.data.success) throw new Error(resp.data.error ?? "请求失败");
  return resp.data.data;
}
