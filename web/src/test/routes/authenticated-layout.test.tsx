import { render } from "@testing-library/react";
import { isRedirect } from "@tanstack/react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { navigateMock, pageOf, resetRouterMock } from "@/test/router-mock";
import { makeSession } from "@/test/fixtures";

// Hoisted above the imports, so the helper must be imported inside the factory.
vi.mock("@tanstack/react-router", async (importOriginal) => {
  const { mockReactRouterModule } = await import("@/test/router-mock");
  return mockReactRouterModule(importOriginal as () => Promise<Record<string, unknown>>);
});
vi.mock("@/lib/auth/session", () => ({ ensureValidSession: vi.fn(), clearSession: vi.fn() }));

let capturedOnSessionExpired: ((error: Error) => void) | undefined;
vi.mock("@/lib/architect-socket-context", () => ({
  ArchitectSocketProvider: ({
    children,
    onSessionExpired,
  }: {
    children: React.ReactNode;
    onSessionExpired?: (error: Error) => void;
  }) => {
    capturedOnSessionExpired = onSessionExpired;
    return <>{children}</>;
  },
}));

import { clearSession, ensureValidSession } from "@/lib/auth/session";
import { Route } from "@/routes/_authenticated";

type BeforeLoad = (ctx: { location: { href: string } }) => Promise<{ session: unknown }>;
const beforeLoad = Route.options.beforeLoad as unknown as BeforeLoad;

beforeEach(() => {
  resetRouterMock();
});

describe("_authenticated guard", () => {
  it("is rendered only on the client (session lives in localStorage)", () => {
    expect(Route.options.ssr).toBe(false);
  });

  it("provides the session to child routes when authenticated", async () => {
    const session = makeSession();
    vi.mocked(ensureValidSession).mockResolvedValue(session);
    await expect(beforeLoad({ location: { href: "/" } })).resolves.toEqual({ session });
  });

  it("redirects to /login when there is no valid session", async () => {
    vi.mocked(ensureValidSession).mockResolvedValue(null);
    const thrown = await beforeLoad({ location: { href: "/" } }).catch((e: unknown) => e);
    expect(isRedirect(thrown)).toBe(true);
    expect((thrown as { options: { to: string; search: unknown } }).options).toMatchObject({
      to: "/login",
      search: {},
    });
  });

  it("remembers the requested page so the user returns to it after login", async () => {
    vi.mocked(ensureValidSession).mockResolvedValue(null);
    const thrown = await beforeLoad({ location: { href: "/projetos/7?tab=code" } }).catch(
      (e: unknown) => e,
    );
    expect((thrown as { options: { search: unknown } }).options.search).toEqual({
      redirect: "/projetos/7?tab=code",
    });
  });
});

describe("_authenticated layout", () => {
  it("drops the session and returns to the login page when the WebSocket reports an expired session", () => {
    const Layout = pageOf(Route);
    render(<Layout />);
    expect(capturedOnSessionExpired).toBeTypeOf("function");

    capturedOnSessionExpired?.(new Error("Sessão expirada."));

    expect(clearSession).toHaveBeenCalled();
    expect(navigateMock).toHaveBeenCalledWith({ to: "/login", replace: true });
  });
});
