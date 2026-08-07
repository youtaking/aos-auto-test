export interface AutomationStateResponse {
  enabled: boolean;
  phase: "standby" | "sleeping" | null;
  next_tick_at: number | null;
  sleep_until: number | null;
}
