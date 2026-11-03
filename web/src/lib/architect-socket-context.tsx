// ============================================================================
// React integration for the WebSocket client (src/lib/architect-socket-context.tsx)
// ----------------------------------------------------------------------------
// `ArchitectSocketProvider` opens the connection when mounted (right after
// login, from the `_authenticated` layout) and closes it when unmounted
// (logout / leaving the authenticated area). While mounted it also:
//   - reconnects immediately when the browser comes back online or the tab
//     becomes visible again (instead of waiting for the backoff timer);
//   - calls `onSessionExpired` when the Cognito session cannot be refreshed,
//     so the layout can send the user back to the login screen.
//
// `useArchitectSocket()` exposes the live connection status and `sendPrompt`.
// ============================================================================

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import {
  ArchitectSocket,
  getWebSocketBaseUrl,
  getWebSocketUrl,
  type PromptResponse,
  type SendPromptOptions,
  type SocketStatus,
} from "./architect-socket";
import { ensureValidSession } from "./auth/session";

/**
 * Resolved right before every connection attempt so the handshake always
 * carries a valid (refreshed if needed) Cognito token.
 */
async function resolveAuthenticatedUrl(): Promise<string> {
  const session = await ensureValidSession();
  if (!session) throw new Error("Sessão expirada. Faça login novamente.");
  return getWebSocketUrl({ idToken: session.idToken, accessToken: session.accessToken });
}

interface ArchitectSocketContextValue {
  status: SocketStatus;
  /** Set when the client could not be created (e.g. missing VITE_WS_API_ID). */
  configError: string | null;
  sendPrompt: (prompt: string, options?: SendPromptOptions) => Promise<PromptResponse>;
  /** Forces a new connection attempt (e.g. from a "reconnect" button). */
  reconnect: () => void;
}

const ArchitectSocketContext = createContext<ArchitectSocketContextValue | null>(null);

export interface ArchitectSocketProviderProps {
  children: ReactNode;
  /** Invoked when the session expired and could not be refreshed with Cognito. */
  onSessionExpired?: (error: Error) => void;
}

export function ArchitectSocketProvider({
  children,
  onSessionExpired,
}: ArchitectSocketProviderProps) {
  // Keep the latest callback without recreating the socket.
  const onSessionExpiredRef = useRef(onSessionExpired);
  useEffect(() => {
    onSessionExpiredRef.current = onSessionExpired;
  }, [onSessionExpired]);

  // Created once per mount. A config error is captured instead of thrown so the
  // page can still render and show a helpful message.
  const { socket, configError } = useMemo(() => {
    try {
      getWebSocketBaseUrl(); // validates VITE_WS_API_ID up front
      return {
        socket: new ArchitectSocket(resolveAuthenticatedUrl, {
          onAuthError: (error) => onSessionExpiredRef.current?.(error),
        }),
        configError: null,
      };
    } catch (error) {
      return {
        socket: null,
        configError: error instanceof Error ? error.message : String(error),
      };
    }
  }, []);

  useEffect(() => {
    if (!socket) return;
    socket.connect();

    // Recover quickly after network changes or when the user returns to the tab.
    const onOnline = () => socket.reconnectNow();
    const onVisible = () => {
      if (document.visibilityState === "visible") socket.reconnectNow();
    };
    window.addEventListener("online", onOnline);
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      window.removeEventListener("online", onOnline);
      document.removeEventListener("visibilitychange", onVisible);
      socket.close();
    };
  }, [socket]);

  const status = useSyncExternalStore(
    (onChange) => socket?.subscribe(onChange) ?? (() => {}),
    () => socket?.getStatus() ?? "closed",
    () => "idle" as const,
  );

  const value = useMemo<ArchitectSocketContextValue>(
    () => ({
      status,
      configError,
      sendPrompt: (prompt, options) => {
        if (!socket) return Promise.reject(new Error(configError ?? "WebSocket indisponível."));
        return socket.sendPrompt(prompt, options);
      },
      reconnect: () => socket?.connect(),
    }),
    [socket, status, configError],
  );

  return (
    <ArchitectSocketContext.Provider value={value}>{children}</ArchitectSocketContext.Provider>
  );
}

export function useArchitectSocket(): ArchitectSocketContextValue {
  const ctx = useContext(ArchitectSocketContext);
  if (!ctx) {
    throw new Error("useArchitectSocket must be used inside <ArchitectSocketProvider>.");
  }
  return ctx;
}
