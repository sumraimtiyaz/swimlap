/**
 * Session state for the coordinator console.
 *
 * Holds the token + user, persists them to localStorage so a refresh keeps the
 * session, and exposes `login`/`logout`. The client's token source is pointed
 * here (see `configureAuth`) so there is exactly one place that knows how the
 * token is stored.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, ApiError, configureAuth } from "../api/client";
import type { User } from "../api/types";
import { UserRole } from "../lib/contract";

const STORAGE_KEY = "swimlap.session";

interface StoredSession {
  token: string;
  user: User;
}

interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readStored(): StoredSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as StoredSession;
  } catch {
    return null;
  }
}

// Point the API client at localStorage exactly once, at module load, so even
// requests fired before the provider mounts carry the token.
configureAuth(() => readStored()?.token ?? null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<StoredSession | null>(() => readStored());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (session) localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    else localStorage.removeItem(STORAGE_KEY);
  }, [session]);

  const login = useCallback(async (username: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.login(username, password);
      if (result.user.role !== UserRole.Coordinator) {
        // The console is coordinator-only; timers use the mobile app.
        throw new ApiError(403, "FORBIDDEN_ROLE", "This console is for coordinators. Timers use the mobile app.");
      }
      const next: StoredSession = { token: result.token, user: result.user };
      // Persist synchronously BEFORE the re-render: child components fetch in
      // their effects, which run before this provider's persist effect would —
      // without this, the first request after login goes out with no token.
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      setSession(next);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Sign-in failed.";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    setSession(null);
    setError(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: session?.user ?? null,
      token: session?.token ?? null,
      loading,
      error,
      login,
      logout,
    }),
    [session, loading, error, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
