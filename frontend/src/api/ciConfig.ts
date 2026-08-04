import { get, put, post } from "./client";
import type { CIConfig } from "./types";

export const getCIConfig = () => get<CIConfig>("/ci/config");

export const updateCIConfig = (data: Partial<CIConfig>) =>
  put<CIConfig>("/ci/config", data);

export const regenerateToken = () =>
  post<{ token: string }>("/ci/config/regenerate-token");
