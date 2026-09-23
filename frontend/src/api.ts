export type Rules = { minimum_ttc_s: number; maximum_lane_deviation_m: number; lane_boundary_m: number; safe_stop_distance_m: number; speed_tolerance_fraction: number; fail_on_critical_ttc: boolean; fail_on_speeding: boolean };
export type Configuration = { ego_speed_kph: number; speed_limit_kph: number; weather: string; rain_intensity: number; fog_density: number; time_of_day: string; traffic_density: number; obstacle_distance_m: number; sensor_noise: number; reaction_delay_s: number; random_seed: number; duration_s: number; rules: Rules };
export type Scenario = { id: number; name: string; scenario_type: string; description: string; configuration: Configuration };
export type Algorithm = { id: number; name: string; version: string; artifact_id: string; configuration: { reaction_multiplier: number; braking_multiplier: number; lane_gain_multiplier: number } };
export type Metrics = { passed: boolean; violations: string[]; warnings?: string[]; failure_severity: string; collision_count: number; minimum_time_to_collision_s: number | null; average_speed_kph: number; [key: string]: number | boolean | string | string[] | null | undefined };
export type Sample = { timestamp_s: number; position_m: number; speed_kph: number; distance_to_obstacle_m: number | null; lane_offset_m: number; time_to_collision_s: number | null; collision: boolean };
export type Run = { id: number; scenario_id: number; algorithm_id: number; status: 'queued' | 'running' | 'completed' | 'failed'; metrics: Partial<Metrics>; random_seed: number; environment: Configuration; snapshot: { scenario_name?: string; scenario_type?: string; algorithm_name?: string; algorithm_version?: string }; telemetry?: Sample[]; error_message: string; started_at: string; ended_at: string | null };
export type Report = { run_id: number; headline: string; summary: string; recommendation: string; generated_by: string; limitations: string; ai_analysis?: string; llm_status?: string; failure_cases: { timestamp_s: number; distance_m: number | null; ttc_s: number | null; lane_offset_m: number }[] };
export type Overview = { total_runs: number; completed_runs: number; passed_runs: number; pass_rate: number | null; failed_evaluations: number; active_jobs: number };
export type Comparison = { runs: Run[]; comparable: boolean; warning: string | null; deltas_from_first: { run_id: number; metrics: Record<string, number> }[] };
export const API = import.meta.env.VITE_API_URL ?? '';

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...options?.headers } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((e: { loc: string[]; msg: string }) => `${e.loc.join('.')}: ${e.msg}`).join('; ') : `Request failed (${response.status})`);
  }
  return response.json();
}
export const post = <T,>(path: string, data: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(data) });
export function downloadJson(name: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export async function downloadRun(id: number, format: string) {
  const response = await fetch(`${API}/api/runs/${id}/export?format=${format}`);
  if (!response.ok) throw new Error('Export failed');
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a'); link.href = url; link.download = `driveeval-run-${id}.${format}`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const defaults: Configuration = { ego_speed_kph: 50, speed_limit_kph: 50, weather: 'clear', rain_intensity: 0, fog_density: 0, time_of_day: 'day', traffic_density: 0.3, obstacle_distance_m: 35, sensor_noise: 0.02, reaction_delay_s: 0.5, random_seed: 7, duration_s: 12, rules: { minimum_ttc_s: 1.5, maximum_lane_deviation_m: 1, lane_boundary_m: 0.8, safe_stop_distance_m: 0.5, speed_tolerance_fraction: 0.05, fail_on_critical_ttc: true, fail_on_speeding: true } };
