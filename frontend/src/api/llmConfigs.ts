import { get, post, put, del } from "./client";
import type { LLMConfig } from "./types";

export const listLLMConfigs = () => get<LLMConfig[]>("/llm-configs");
export const createLLMConfig = (data: Partial<LLMConfig>) =>
  post<LLMConfig>("/llm-configs", data);
export const updateLLMConfig = (id: number, data: Partial<LLMConfig>) =>
  put<LLMConfig>(`/llm-configs/${id}`, data);
export const deleteLLMConfig = (id: number) => del(`/llm-configs/${id}`);
export const activateLLMConfig = (id: number) =>
  post<LLMConfig>(`/llm-configs/${id}/activate`);
