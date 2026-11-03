import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { makeSession } from "@/test/fixtures";

// The session layer calls into the Cognito client only to refresh / sign out.
vi.mock("./cognito", () => ({
  refreshTokens: vi.fn(),
  globalSignOut: vi.fn(),
}));

import { globalSignOut, refreshTokens } from "./cognito";
import {
  clearSession,
  ensureValidSession,
  getAuthHeaders,
  getSession,
  isSessionExpired,
  saveSession,
  signOut,
} from "./session";

const STORAGE_KEY = "ai-portal-buddy.session";

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("persistence", () => {
  it("round-trips a session through localStorage", () => {
    const session = makeSession();
    saveSession(session);
    expect(getSession()).toEqual(session);
    expect(JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "null")).toEqual(session);
  });

  it("returns null when nothing is stored", () => {
    expect(getSession()).toBeNull();
  });

  it("ignores corrupted or incomplete stored values", () => {
    window.localStorage.setItem(STORAGE_KEY, "{not json");
    expect(getSession()).toBeNull();

    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ accessToken: "only-this" }));
    expect(getSession()).toBeNull();
  });

  it("clearSession removes the stored session", () => {
    saveSession(makeSession());
    clearSession();
    expect(getSession()).toBeNull();
  });
});

describe("isSessionExpired", () => {
  it("treats sessions within the 60s safety margin as expired", () => {
    expect(isSessionExpired(makeSession({ expiresAt: Date.now() + 30_000 }))).toBe(true);
    expect(isSessionExpired(makeSession({ expiresAt: Date.now() + 120_000 }))).toBe(false);
    expect(isSessionExpired(makeSession({ expiresAt: Date.now() - 1 }))).toBe(true);
  });
});

describe("ensureValidSession", () => {
  it("returns null when there is no session", async () => {
    expect(await ensureValidSession()).toBeNull();
    expect(refreshTokens).not.toHaveBeenCalled();
  });

  it("returns the stored session untouched while it is still valid", async () => {
    const session = makeSession();
    saveSession(session);
    expect(await ensureValidSession()).toEqual(session);
    expect(refreshTokens).not.toHaveBeenCalled();
  });

  it("refreshes and persists an expired session", async () => {
    const expired = makeSession({ expiresAt: Date.now() - 1000 });
    const refreshed = makeSession({ accessToken: "new-access", expiresAt: Date.now() + 3_600_000 });
    saveSession(expired);
    vi.mocked(refreshTokens).mockResolvedValueOnce(refreshed);

    expect(await ensureValidSession()).toEqual(refreshed);
    expect(refreshTokens).toHaveBeenCalledWith(expired);
    expect(getSession()).toEqual(refreshed);
  });

  it("clears the session when the refresh fails", async () => {
    saveSession(makeSession({ expiresAt: Date.now() - 1000 }));
    vi.mocked(refreshTokens).mockRejectedValueOnce(new Error("NotAuthorizedException"));

    expect(await ensureValidSession()).toBeNull();
    expect(getSession()).toBeNull();
  });

  it("clears an expired session that has no refresh token", async () => {
    const session = makeSession({ expiresAt: Date.now() - 1000 });
    delete session.refreshToken;
    saveSession(session);

    expect(await ensureValidSession()).toBeNull();
    expect(refreshTokens).not.toHaveBeenCalled();
    expect(getSession()).toBeNull();
  });
});

describe("signOut", () => {
  it("removes the local session and revokes tokens in Cognito", async () => {
    const session = makeSession();
    saveSession(session);
    vi.mocked(globalSignOut).mockResolvedValueOnce();

    await signOut();

    expect(getSession()).toBeNull();
    expect(globalSignOut).toHaveBeenCalledWith(session);
  });

  it("still clears the local session when GlobalSignOut fails", async () => {
    saveSession(makeSession());
    vi.mocked(globalSignOut).mockRejectedValueOnce(new Error("network"));

    await expect(signOut()).resolves.toBeUndefined();
    expect(getSession()).toBeNull();
  });

  it("does not call Cognito for an already expired session", async () => {
    saveSession(makeSession({ expiresAt: Date.now() - 1000 }));
    await signOut();
    expect(globalSignOut).not.toHaveBeenCalled();
    expect(getSession()).toBeNull();
  });
});

describe("getAuthHeaders", () => {
  it("returns a Bearer header with the id token when logged in", () => {
    const session = makeSession();
    saveSession(session);
    expect(getAuthHeaders()).toEqual({ Authorization: `Bearer ${session.idToken}` });
  });

  it("returns no headers when logged out", () => {
    expect(getAuthHeaders()).toEqual({});
  });
});
