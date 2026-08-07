import { get, put } from "./client";

export interface SettingItem {
  key: string;
  value: string;
  description: string;
}

export function listSettings(): Promise<SettingItem[]> {
  return get<SettingItem[]>("/settings");
}

export function getSetting(key: string): Promise<SettingItem> {
  return get<SettingItem>(`/settings/${key}`);
}

export function updateSetting(key: string, value: string): Promise<SettingItem> {
  return put<SettingItem>(`/settings/${key}`, { value });
}
