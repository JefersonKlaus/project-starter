// ============================================================================
// User session (src/lib/auth/session.ts)
// ----------------------------------------------------------------------------
// Stores the Cognito tokens in the browser's localStorage and provides
// helpers to read, refresh and end the session.
//
// Every function is safe to call during SSR: without `window` they simply
// behave as "not authenticated".
// ============================================================================

import { globalSignOut, refreshTokens } from "./cognito";

const STORAGE_KEY = "ai-portal-buddy.session";

/** Safety margin: refresh the token when it is closer than this to expiring. */
const EXPIRY_SKEW_MS = 60 * 1000;

export interface AuthSession {
  accessToken: string;
  idToken: string;
  refreshToken?: string;
  /** Timestamp (ms) at which the access/id token expires. */
  expiresAt: number;
  /** Authenticated user's e-mail (`email` claim of the id token). */
  email: string;
}

function isBrowser(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function isAuthSession(value: unknown): value is AuthSession {
  if (!value || typeof value !== "object") return false;
  const s = value as Record<string, unknown>;
  return (
    typeof s["accessToken"] === "string" &&
    typeof s["idToken"] === "string" &&
    typeof s["expiresAt"] === "number" &&
    typeof s["email"] === "string"
  );
}

/** Reads the stored session (without checking expiration). */
export function getSession(): AuthSession | null {
  if (!isBrowser()) return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return isAuthSession(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function saveSession(session: AuthSession): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  if (!isBrowser()) return;
  window.localStorage.removeItem(STORAGE_KEY);
}

export function isSessionExpired(session: AuthSession): boolean {
  return session.expiresAt - EXPIRY_SKEW_MS <= Date.now();
}

/**
 * Returns a valid session, refreshing the tokens if they have expired.
 * Returns `null` when there is no session or the refresh fails (user must log in).
 */
export async function ensureValidSession(): Promise<AuthSession | null> {
  const session = getSession();
  if (!session) return null;
  if (!isSessionExpired(session)) return session;

  if (!session.refreshToken) {
    clearSession();
    return null;
  }

  try {
    const refreshed = await refreshTokens(session);
    saveSession(refreshed);
    return refreshed;
  } catch {
    clearSession();
    return null;
  }
}

/**
 * Ends the session: tries to invalidate the tokens in Cognito and, regardless
 * of the outcome, removes the local session.
 */
export async function signOut(): Promise<void> {
  const session = getSession();
  clearSession();
  if (session && !isSessionExpired(session)) {
    try {
      await globalSignOut(session);
    } catch {
      // Best-effort: the local session has already been removed.
    }
  }
}

/**
 * Headers for authenticated backend calls (API Gateway + Cognito authorizer).
 * E.g. fetch(url, { headers: { ...getAuthHeaders(), "Content-Type": "application/json" } })
 */
export function getAuthHeaders(): Record<string, string> {
  const session = getSession();
  return session ? { Authorization: `Bearer ${session.idToken}` } : {};
}
