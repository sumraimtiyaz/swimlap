/**
 * TypeScript mirror of `shared/contracts/contract.json`.
 *
 * This file is hand-kept in sync with the shared contract so the dashboard
 * agrees with the backend and the mobile app on enum spellings, error codes,
 * and timing thresholds (DRY across the three runtimes). See
 * `docs/ARCHITECTURE.md` for the codegen story that would replace this by-hand
 * mirror in a later phase.
 */

export const CONTRACT_VERSION = "2.0.0";

export const UserRole = {
  Coordinator: "coordinator",
  Timer: "timer",
} as const;
export type UserRole = (typeof UserRole)[keyof typeof UserRole];

export const SwimStatus = {
  Scheduled: "scheduled",
  Live: "live",
  Closed: "closed",
} as const;
export type SwimStatus = (typeof SwimStatus)[keyof typeof SwimStatus];

export const ClosureMethod = {
  TimerCompleted: "timer_completed",
  AutoInactivity: "auto_inactivity",
  Coordinator: "coordinator",
} as const;
export type ClosureMethod = (typeof ClosureMethod)[keyof typeof ClosureMethod];

export const LapSource = {
  Manual: "manual",
  Simulated: "simulated",
} as const;
export type LapSource = (typeof LapSource)[keyof typeof LapSource];

/** Human-readable fallbacks for the backend's `{code, message}` error envelope. */
export const ERROR_MESSAGES: Record<string, string> = {
  AUTH_INVALID_CREDENTIALS: "Login id or password is incorrect.",
  AUTH_TOKEN_EXPIRED: "Session expired; sign in again.",
  AUTH_LOCKED: "Too many failed attempts. Try again later.",
  AUTH_ACCOUNT_DISABLED: "This account has been deactivated. Contact your coordinator.",
  FORBIDDEN_ROLE: "Your role may not perform this action.",
  NOT_OWNER: "You do not have access to this record.",
  USER_NOT_FOUND: "User does not exist.",
  SWIM_NOT_FOUND: "Swim does not exist.",
  SWIM_NOT_LIVE: "Laps can only be recorded once a swim is live.",
  NOT_ASSIGNED: "You are not assigned to this swim.",
  OVERLAPPING_ASSIGNMENT: "This timer is already assigned to an overlapping swim.",
  LAP_INVALID_TIMING: "Lap rejected: timing values were not finite/plausible.",
  LAP_DUPLICATE_SEQ: "A lap with this sequence number already exists.",
  VALIDATION_ERROR: "Request payload failed validation.",
  ILLEGAL_STATE_TRANSITION: "That state change is not allowed.",
};

export const TIMING = {
  swim: {
    autoInactivityTimeoutSeconds: 900,
    defaultLaneCount: 8,
    maxLaneCount: 12,
  },
  lapIngest: {
    maxLapsPerBatch: 500,
    minInterLapMs: 250,
  },
  auth: {
    tokenTtlHours: 24,
    maxFailedAttempts: 5,
    lockoutMinutes: 15,
  },
} as const;

/** Banner mandated by PRD §9 — shown on every screen/export built on simulated data. */
export const SIMULATED_BANNER = "SIMULATED DATA — NOT MEASURED TIMING";
