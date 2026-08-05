import { get, put, post, del } from "./client";
import type { EnvironmentSlot } from "./types";

export const listSlots = () => get<EnvironmentSlot[]>("/slots");

export const updateSlot = (id: number, data: Partial<EnvironmentSlot>) =>
  put<EnvironmentSlot>(`/slots/${id}`, data);

export const createSlot = (data?: Partial<EnvironmentSlot>) =>
  post<EnvironmentSlot>("/slots", data || {});

export const deleteSlot = (id: number) =>
  del<{ id: number }>(`/slots/${id}`);
