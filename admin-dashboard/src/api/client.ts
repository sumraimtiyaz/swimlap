/**
 * Thin HTTP client for the SwimLap backend.
 *
 * Responsibilities kept narrow (SRP): attach the bearer token, serialise JSON,
 * and translate the backend's `{code, message, details}` envelope into a typed
 * `ApiError`. Everything above this layer (hooks, pages) deals in domain types
 * and never touches `fetch` directly.
 */
import { ERROR_MESSAGES, UserRole } from "../lib/contract";
import type {
  AssignRequest,
  CreateSwimRequest,
  CreateSwimmerRequest,
  CreateUserRequest,
  CreateVenueRequest,
  IssuedAccount,
  LiveRow,
  LoginResponse,
  Report,
  Swim,
  SwimDetail,
  Swimmer,
  User,
  Venue,
} from "./types";

const BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ??
  "http://localhost:8000";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  get isAuthError(): boolean {
    return this.status === 401;
  }
}

type TokenSource = () => string | null;

let getToken: TokenSource = () => null;

export function configureAuth(source: TokenSource): void {
  getToken = source;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let payload: string | undefined;
  if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(opts.body);
  }

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method: opts.method ?? "GET",
      headers,
      body: payload,
      signal: opts.signal,
    });
  } catch (cause) {
    throw new ApiError(0, "NETWORK_ERROR", "Could not reach the server. Check that the API is running.", {
      cause: String(cause),
    });
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  const data = text ? safeParse(text) : {};

  if (!response.ok) {
    const code = typeof data.code === "string" ? data.code : "HTTP_ERROR";
    const message =
      (typeof data.message === "string" && data.message) ||
      ERROR_MESSAGES[code] ||
      `Request failed (${response.status}).`;
    const details = (data.details as Record<string, unknown>) ?? {};
    throw new ApiError(response.status, code, message, details);
  }

  return data as T;
}

function safeParse(text: string): Record<string, unknown> {
  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    return {};
  }
}

/** The public surface, grouped by resource, named by coordinator intent. */
export const api = {
  login(username: string, password: string): Promise<LoginResponse> {
    return request<LoginResponse>("/auth/login", { method: "POST", body: { username, password } });
  },

  // Accounts
  listTimers(signal?: AbortSignal): Promise<User[]> {
    return request<User[]>(`/users?role=${UserRole.Timer}`, { signal });
  },
  listUsers(signal?: AbortSignal): Promise<User[]> {
    return request<User[]>("/users", { signal });
  },
  createTimer(body: CreateUserRequest): Promise<IssuedAccount> {
    return request<IssuedAccount>("/users", { method: "POST", body });
  },
  resetPassword(userId: number): Promise<IssuedAccount> {
    return request<IssuedAccount>(`/users/${userId}/reset-password`, { method: "POST" });
  },
  deactivateUser(userId: number): Promise<User> {
    return request<User>(`/users/${userId}/deactivate`, { method: "PATCH" });
  },

  // Setup
  listVenues(signal?: AbortSignal): Promise<Venue[]> {
    return request<Venue[]>("/venues", { signal });
  },
  createVenue(body: CreateVenueRequest): Promise<Venue> {
    return request<Venue>("/venues", { method: "POST", body });
  },
  listSwimmers(signal?: AbortSignal): Promise<Swimmer[]> {
    return request<Swimmer[]>("/swimmers", { signal });
  },
  createSwimmer(body: CreateSwimmerRequest): Promise<Swimmer> {
    return request<Swimmer>("/swimmers", { method: "POST", body });
  },

  // Swims
  listSwims(signal?: AbortSignal): Promise<Swim[]> {
    return request<Swim[]>("/swims", { signal });
  },
  getSwim(swimId: number, signal?: AbortSignal): Promise<SwimDetail> {
    return request<SwimDetail>(`/swims/${swimId}`, { signal });
  },
  createSwim(body: CreateSwimRequest): Promise<SwimDetail> {
    return request<SwimDetail>("/swims", { method: "POST", body });
  },
  liveSwims(signal?: AbortSignal): Promise<LiveRow[]> {
    return request<LiveRow[]>("/swims/live", { signal });
  },
  getReport(swimId: number, signal?: AbortSignal): Promise<Report> {
    return request<Report>(`/swims/${swimId}/report`, { signal });
  },
  closeSwim(swimId: number): Promise<Swim> {
    return request<Swim>(`/swims/${swimId}/close`, { method: "POST" });
  },
  simulateSwim(swimId: number, laps = 6, intervalMs = 41000): Promise<{ laps_submitted: number }> {
    return request<{ laps_submitted: number }>(
      `/swims/${swimId}/simulate?laps=${laps}&interval_ms=${intervalMs}`, { method: "POST" });
  },

  // Assignments
  assignTimer(body: AssignRequest): Promise<{ id: number; swim_id: number; timer_id: number }> {
    return request("/assignments", { method: "POST", body });
  },
  unassign(assignmentId: number): Promise<void> {
    return request<void>(`/assignments/${assignmentId}`, { method: "DELETE" });
  },
};
