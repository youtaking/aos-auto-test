import { get } from "./client";
import type { DashboardSummary, TrendItem } from "./types";

export const getSummary = () => get<DashboardSummary>("/dashboard/summary");
export const getTrend = (limit = 10) => get<TrendItem[]>(`/dashboard/trend?limit=${limit}`);
