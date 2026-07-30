import { get, post, put, del } from "./client";
import type { AuthConfig } from "./types";

export const listAuthConfigs = () => get<AuthConfig[]>("/auth-configs");

export const createAuthConfig = (data: {
  name: string;
  ui_test_email?: string;
  ui_test_password?: string;
  api_test_email?: string;
  api_test_password?: string;
  open_api_key?: string;
}) => post<AuthConfig>("/auth-configs", data);

export const updateAuthConfig = (id: number, data: Partial<AuthConfig>) =>
  put<AuthConfig>(`/auth-configs/${id}`, data);

export const deleteAuthConfig = (id: number) => del(`/auth-configs/${id}`);

export const activateAuthConfig = (id: number) =>
  post<AuthConfig>(`/auth-configs/${id}/activate`);
