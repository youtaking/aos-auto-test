import { get } from "./client";
import type { Pipeline } from "./types";

interface PipelineListResult {
  items: Pipeline[];
  total: number;
  page: number;
  page_size: number;
}

export const listPipelines = (params?: { status?: string; page?: number; page_size?: number }) =>
  get<PipelineListResult>("/pipelines", params);

export const getPipeline = (id: number) => get<Pipeline>(`/pipelines/${id}`);
