import { get, post, del } from "./client";
import type { Pipeline } from "./types";

export const listPipelines = (params?: { status?: string; page?: number; page_size?: number }) =>
  get<Pipeline[]>("/pipelines", params);

export const getPipeline = (id: number) => get<Pipeline>(`/pipelines/${id}`);

export const rerunPipeline = (id: number, caseIds?: number[]) =>
  post<{ message: string }>(`/pipelines/${id}/rerun`, { case_ids: caseIds });

export const destroyPipeline = (id: number) =>
  del<{ message: string }>(`/pipelines/${id}`);

export const cancelPipeline = (id: number) =>
  post<{ message: string }>(`/pipelines/${id}/cancel`);
