import { Outlet, createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { Loader2 } from "lucide-react";

import { ArchitectSocketProvider } from "@/lib/architect-socket-context";
import { clearSession, ensureValidSession } from "@/lib/auth/session";

/**
 * Pathless layout that protects every child route.
 * Any page placed in `src/routes/_authenticated/` requires login: without a
 * valid session the user is sent to /login and, after authenticating, returns
 * to the URL they originally tried to access.
 *
 * It also owns the WebSocket connection to the generation backend: the
 * connection is opened as soon as the user is authenticated and closed when
 * they leave (logout).
 */
export const Route = createFileRoute("/_authenticated")({
  // The session lives in localStorage, so the check must run in the browser.
  ssr: false,
  beforeLoad: async ({ location }) => {
    const session = await ensureValidSession();
    if (!session) {
      throw redirect({
        to: "/login",
        search: location.href === "/" ? {} : { redirect: location.href },
      });
    }
    return { session };
  },
  pendingComponent: AuthPending,
  component: AuthenticatedLayout,
});

function AuthenticatedLayout() {
  const navigate = useNavigate();

  // The WebSocket could not obtain a valid Cognito token (refresh failed):
  // drop the local session and ask the user to log in again.
  const handleSessionExpired = () => {
    clearSession();
    void navigate({ to: "/login", replace: true });
  };

  return (
    <ArchitectSocketProvider onSessionExpired={handleSessionExpired}>
      <Outlet />
    </ArchitectSocketProvider>
  );
}

function AuthPending() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  );
}
