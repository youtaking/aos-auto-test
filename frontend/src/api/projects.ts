import { get, post, put, del } from "./client";
import type { Project, TestSuite } from "./types";

export const listProjects = () => get<Project[]>("/projects");
export const createProject = (data: { name: string; url: string; description?: string }) =>
  post<Project>("/projects", data);
export const updateProject = (id: number, data: Partial<Project>) =>
  put<Project>(`/projects/${id}`, data);
export const deleteProject = (id: number) => del(`/projects/${id}`);

export const listSuites = (projectId: number) =>
  get<TestSuite[]>(`/projects/${projectId}/suites`);
export const createSuite = (projectId: number, data: { name: string; description?: string }) =>
  post<TestSuite>(`/projects/${projectId}/suites`, data);
