/**
 * Wire types mirroring the backend pydantic schemas (`app/schemas/*`).
 *
 * Field names match the JSON exactly (snake_case) so the mapping in `client.ts`
 * is a pass-through with no translation layer that could drift.
 */
import type { ClosureMethod, SwimStatus, UserRole } from "../lib/contract";

export interface User {
  id: number;
  username: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string | null;
}

export interface IssuedAccount {
  user: User;
  password: string; // one-time plaintext, shown once
}

export interface LoginResponse {
  token: string;
  user: User;
}

export interface Venue {
  id: number;
  name: string;
  lane_count: number;
}

export interface Swimmer {
  id: number;
  name: string;
}

export interface Swim {
  id: number;
  venue_id: number;
  swimmer_id: number;
  lane_no: number;
  scheduled_start: string; // ISO-8601
  lap_target: number | null;
  status: SwimStatus;
  closure_method: ClosureMethod | null;
  closed_at: string | null;
  swimmer_name: string;
  venue_name: string;
}

export interface SwimDetail extends Swim {
  assigned_timer_id: number | null;
  assigned_timer_name: string | null;
  assignment_id: number | null;
}

export interface LiveRow {
  swim_id: number;
  swimmer_name: string;
  venue_name: string;
  lane_no: number;
  timer_id: number | null;
  timer_name: string | null;
  connected: boolean;
  lap_count: number;
  last_lap_ms: number | null;
  stalled: boolean;
}

export interface ReportLap {
  lap_no: number;
  seq: number;
  recorded_ms: number | null;
  cumulative_ms: number | null;
  reference_ms: number | null;
  deviation_ms: number | null;
  derived: boolean;
  was_late: boolean;
  is_valid: boolean;
  note: string;
}

export interface ReportSummary {
  laps_recorded: number;
  average_deviation_ms: number | null;
  largest_deviation_ms: number | null;
  largest_deviation_lap: number | null;
  laps_without_comparison: number;
  late_count: number;
  comparable: boolean;
}

export interface Report {
  swim_id: number;
  swimmer_name: string;
  venue_name: string;
  lane_no: number;
  status: SwimStatus;
  scheduled_start: string;
  simulated: boolean;
  banner: string;
  laps: ReportLap[];
  summary: ReportSummary;
}

// --- request bodies ---
export interface CreateVenueRequest {
  name: string;
  lane_count: number;
}

export interface CreateSwimmerRequest {
  name: string;
}

export interface CreateSwimRequest {
  venue_id: number;
  swimmer_id: number;
  lane_no: number;
  scheduled_start: string;
  lap_target: number | null;
}

export interface CreateUserRequest {
  username: string;
  display_name: string;
  role: UserRole;
}

export interface AssignRequest {
  swim_id: number;
  timer_id: number;
}
