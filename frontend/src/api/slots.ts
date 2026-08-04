import { get, put } from "./client";
import type { EnvironmentSlot } from "./types";

export const listSlots = () => get<EnvironmentSlot[]>("/slots");

export const updateSlot = (id: number, data: Partial<EnvironmentSlot>) =>
  put<EnvironmentSlot>(`/slots/${id}`, data);
