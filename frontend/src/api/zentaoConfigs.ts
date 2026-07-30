import { get, post, put, del } from "./client";
import type { ZentaoConfig } from "./types";

export const listZentaoConfigs = () => get<ZentaoConfig[]>("/zentao-configs");
export const createZentaoConfig = (data: Partial<ZentaoConfig>) =>
  post<ZentaoConfig>("/zentao-configs", data);
export const updateZentaoConfig = (id: number, data: Partial<ZentaoConfig>) =>
  put<ZentaoConfig>(`/zentao-configs/${id}`, data);
export const deleteZentaoConfig = (id: number) => del(`/zentao-configs/${id}`);
export const activateZentaoConfig = (id: number) =>
  post<ZentaoConfig>(`/zentao-configs/${id}/activate`);
