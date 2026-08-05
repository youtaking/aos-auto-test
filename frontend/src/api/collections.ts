import { get, post, put, del } from "./client";
import type { Collection } from "./types";

export interface CollectionCaseInfo {
  id: number;
  name: string;
  suite_id: number;
  file_path: string;
  function_name: string;
  tags: string;
  priority: string;
}

export const listCollections = (projectId?: number) =>
  get<Collection[]>("/collections", projectId ? { project_id: projectId } : undefined);

export const getCollection = (id: number) =>
  get<Collection & { cases: CollectionCaseInfo[] }>(`/collections/${id}`);

export const createCollection = (data: { name: string; description?: string; case_ids?: number[] }) =>
  post<Collection>("/collections", data);

export const updateCollection = (id: number, data: { name?: string; description?: string; case_ids?: number[] }) =>
  put<Collection>(`/collections/${id}`, data);

export const deleteCollection = (id: number) =>
  del<{ message: string }>(`/collections/${id}`);
