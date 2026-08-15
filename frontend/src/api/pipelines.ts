import { get, post, del } from "./client";
import type { Pipeline } from "./types";

interface PipelineListResult {
  items: Pipeline[];
  total: number;
  page: number;
  page_size: number;
}

interface PipelineLogsResult {
  logs: string;
  pipeline_id: number;
}

export const listPipelines = (params?: { status?: string; page?: number; page_size?: number }) =>
  get<PipelineListResult>("/pipelines", params);

export const getPipeline = (id: number) => get<Pipeline>(`/pipelines/${id}`);

export const getPipelineLogs = (id: number) => get<PipelineLogsResult>(`/pipelines/${id}/logs`);

export const deletePipeline = (id: number) => del<{ deleted: number }>(`/pipelines/${id}`);

export const batchDeletePipelines = (pipelineIds: number[]) =>
  post<{ deleted: number[]; count: number }>("/pipelines/batch-delete", { pipeline_ids: pipelineIds });
