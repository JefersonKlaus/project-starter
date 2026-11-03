import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FakeSocket } from "@/test/fake-socket";
import { makeSession, mockResultado } from "@/test/fixtures";

vi.mock("./auth/session", () => ({
  ensureValidSession: vi.fn(),
}));

import { ArchitectSocketProvider, useArchitectSocket } from "./architect-socket-context";
import { ensureValidSession } from "./auth/session";

/** Small consumer exposing the hook state for assertions. */
function Probe({
  onSend,
}: {
  onSend?: (send: ReturnType<typeof useArchitectSocket>["sendPrompt"]) => void;
}) {
  const socket = useArchitectSocket();
  onSend?.(socket.sendPrompt);
  return (
    <div>
      <span data-testid="status">{socket.status}</span>
      <span data-testid="config-error">{socket.configError ?? ""}</span>
      <button onClick={socket.reconnect}>reconnect</button>
    </div>
  );
}

beforeEach(() => {
  FakeSocket.reset();
  vi.stubEnv("VITE_WS_API_ID", "abc123");
  vi.stubEnv("VITE_WS_STAGE", "");
  vi.stubEnv("VITE_WS_AUTH_PARAM", "");
  vi.stubEnv("VITE_WS_AUTH_TOKEN", "");
  vi.stubEnv("VITE_WS_KEEPALIVE_SECONDS", "0");
  // The provider uses the browser WebSocket; swap it for the fake.
  vi.stubGlobal(
    "WebSocket",
    Object.assign(FakeSocket, { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 }),
  );
  vi.mocked(ensureValidSession).mockResolvedValue(makeSession({ accessToken: "ACCESS" }));
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("ArchitectSocketProvider", () => {
  it("connects on mount using the session's access token and closes on unmount", async () => {
    const { unmount } = render(
      <ArchitectSocketProvider>
        <Probe />
      </ArchitectSocketProvider>,
    );

    expect(screen.getByTestId("status")).toHaveTextContent("connecting");
    await waitFor(() => expect(FakeSocket.instances).toHaveLength(1));
    expect(FakeSocket.last().url).toBe(
      "wss://abc123.execute-api.us-east-2.amazonaws.com/dev?token=ACCESS",
    );

    act(() => FakeSocket.last().open());
    expect(screen.getByTestId("status")).toHaveTextContent("open");

    unmount();
    expect(FakeSocket.last().readyState).toBe(WebSocket.CLOSED);
  });

  it("exposes a configuration error instead of crashing when VITE_WS_API_ID is missing", () => {
    vi.stubEnv("VITE_WS_API_ID", "");
    render(
      <ArchitectSocketProvider>
        <Probe />
      </ArchitectSocketProvider>,
    );
    expect(screen.getByTestId("config-error")).toHaveTextContent("VITE_WS_API_ID");
    expect(FakeSocket.instances).toHaveLength(0);
  });

  it("sendPrompt goes through the live socket", async () => {
    let send: ReturnType<typeof useArchitectSocket>["sendPrompt"] | undefined;
    render(
      <ArchitectSocketProvider>
        <Probe onSend={(s) => (send = s)} />
      </ArchitectSocketProvider>,
    );
    await waitFor(() => expect(FakeSocket.instances).toHaveLength(1));
    act(() => FakeSocket.last().open());

    const promise = send!("hello");
    await waitFor(() => expect(FakeSocket.last().sent).toHaveLength(1));
    act(() => {
      FakeSocket.last().receive({ type: "accepted", request_id: "r1" });
      FakeSocket.last().receive({ type: "result", request_id: "r1", result: mockResultado });
    });
    await expect(promise).resolves.toEqual({ requestId: "r1", result: mockResultado });
  });

  it("reconnect() opens a new connection after a drop", async () => {
    render(
      <ArchitectSocketProvider>
        <Probe />
      </ArchitectSocketProvider>,
    );
    await waitFor(() => expect(FakeSocket.instances).toHaveLength(1));
    act(() => FakeSocket.last().open());
    act(() => FakeSocket.last().drop());
    expect(screen.getByTestId("status")).toHaveTextContent("reconnecting");

    act(() => screen.getByText("reconnect").click());
    await waitFor(() => expect(FakeSocket.instances).toHaveLength(2));
  });

  it("reconnects immediately when the browser comes back online or the tab becomes visible", async () => {
    render(
      <ArchitectSocketProvider>
        <Probe />
      </ArchitectSocketProvider>,
    );
    await waitFor(() => expect(FakeSocket.instances).toHaveLength(1));
    act(() => FakeSocket.last().open());

    act(() => FakeSocket.last().drop());
    act(() => window.dispatchEvent(new Event("online")));
    await waitFor(() => expect(FakeSocket.instances).toHaveLength(2));
    act(() => FakeSocket.last().open());

    act(() => FakeSocket.last().drop());
    act(() => document.dispatchEvent(new Event("visibilitychange")));
    await waitFor(() => expect(FakeSocket.instances).toHaveLength(3));
  });

  it("reports an expired session that could not be refreshed", async () => {
    vi.mocked(ensureValidSession).mockResolvedValue(null);
    const onSessionExpired = vi.fn();
    render(
      <ArchitectSocketProvider onSessionExpired={onSessionExpired}>
        <Probe />
      </ArchitectSocketProvider>,
    );
    await waitFor(() => expect(onSessionExpired).toHaveBeenCalledTimes(1));
    expect(onSessionExpired.mock.calls[0]?.[0]).toMatchObject({ message: /Sessão expirada/ });
    expect(screen.getByTestId("status")).toHaveTextContent("closed");
    expect(FakeSocket.instances).toHaveLength(0);
  });

  it("throws when the hook is used outside the provider", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Probe />)).toThrow(/ArchitectSocketProvider/);
  });
});
