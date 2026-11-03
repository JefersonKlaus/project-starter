import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  AbortError,
  ArchitectSocket,
  SocketError,
  getKeepAliveConfig,
  getWebSocketBaseUrl,
  getWebSocketUrl,
  type ArchitectSocketOptions,
  type SocketStatus,
} from "./architect-socket";
import { FakeSocket } from "@/test/fake-socket";
import { mockResultado } from "@/test/fixtures";

const auth = { idToken: "ID.TOKEN", accessToken: "ACCESS.TOKEN" };

/** Lets queued promise callbacks run. */
const flush = () => new Promise<void>((r) => setTimeout(r, 0));

/** Clients created during a test; closed afterwards so reconnect timers don't leak. */
const clients: ArchitectSocket[] = [];

function createClient(
  resolveUrl: () => string | Promise<string> = () => "wss://test/de?token=x",
  options: Omit<ArchitectSocketOptions, "createSocket"> = {},
) {
  const client = new ArchitectSocket(resolveUrl, {
    createSocket: (url) => new FakeSocket(url),
    reconnectDelayMs: 10,
    maxReconnectDelayMs: 20,
    keepAlive: { intervalMs: 0, message: { action: "ping" } },
    ...options,
  });
  clients.push(client);
  return client;
}

beforeEach(() => {
  FakeSocket.reset();
  vi.stubEnv("VITE_WS_API_ID", "abc123");
  vi.stubEnv("VITE_WS_STAGE", "");
  vi.stubEnv("VITE_WS_AUTH_PARAM", "");
  vi.stubEnv("VITE_WS_AUTH_TOKEN", "");
  vi.stubEnv("VITE_WS_KEEPALIVE_SECONDS", "");
  vi.stubEnv("VITE_WS_KEEPALIVE_ACTION", "");
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  for (const client of clients.splice(0)) client.close();
  vi.useRealTimers();
  vi.unstubAllEnvs();
});

describe("URL building", () => {
  it("uses the fixed region, the API id from the env and the default stage", () => {
    expect(getWebSocketBaseUrl()).toBe("wss://abc123.execute-api.us-east-2.amazonaws.com/dev");
  });

  it("sends the access token as `token` by default", () => {
    expect(getWebSocketUrl(auth)).toBe(
      "wss://abc123.execute-api.us-east-2.amazonaws.com/dev?token=ACCESS.TOKEN",
    );
  });

  it("honours stage, parameter name and token type overrides", () => {
    vi.stubEnv("VITE_WS_STAGE", "/prod/");
    vi.stubEnv("VITE_WS_AUTH_PARAM", "Authorization");
    vi.stubEnv("VITE_WS_AUTH_TOKEN", "id");
    expect(getWebSocketUrl(auth)).toBe(
      "wss://abc123.execute-api.us-east-2.amazonaws.com/prod?Authorization=ID.TOKEN",
    );
  });

  it("throws a helpful error when VITE_WS_API_ID is missing", () => {
    vi.stubEnv("VITE_WS_API_ID", "");
    expect(() => getWebSocketBaseUrl()).toThrowError(/VITE_WS_API_ID/);
  });
});

describe("keepalive configuration", () => {
  it("defaults to a ping every 4 minutes", () => {
    expect(getKeepAliveConfig()).toEqual({ intervalMs: 240_000, message: { action: "ping" } });
  });

  it("reads interval and action from the env, and 0 disables it", () => {
    vi.stubEnv("VITE_WS_KEEPALIVE_SECONDS", "30");
    vi.stubEnv("VITE_WS_KEEPALIVE_ACTION", "heartbeat");
    expect(getKeepAliveConfig()).toEqual({ intervalMs: 30_000, message: { action: "heartbeat" } });

    vi.stubEnv("VITE_WS_KEEPALIVE_SECONDS", "0");
    expect(getKeepAliveConfig().intervalMs).toBe(0);
    vi.stubEnv("VITE_WS_KEEPALIVE_SECONDS", "abc");
    expect(getKeepAliveConfig().intervalMs).toBe(0);
  });
});

describe("keepalive", () => {
  const keepAlive = { intervalMs: 1000, message: { action: "ping" } };

  it("sends the keepalive frame periodically while open and stops when closed", async () => {
    const client = createClient(() => "wss://test", { keepAlive });
    client.connect();
    await flush();
    const socket = FakeSocket.last();
    vi.useFakeTimers(); // before open(): the keepalive interval starts on open
    socket.open();

    vi.advanceTimersByTime(3000);
    expect(socket.sent).toEqual([{ action: "ping" }, { action: "ping" }, { action: "ping" }]);

    socket.drop();
    vi.advanceTimersByTime(5000);
    expect(socket.sent).toHaveLength(3);
  });

  it("ignores `pong` replies silently", async () => {
    const client = createClient(() => "wss://test", { keepAlive });
    client.connect();
    await flush();
    FakeSocket.last().open();
    FakeSocket.last().receive({ type: "pong" });
    expect(console.warn).not.toHaveBeenCalled();
    expect(client.getStatus()).toBe("open");
  });

  it("forces a close (and therefore a reconnect) when the keepalive cannot be sent", async () => {
    const client = createClient(() => "wss://test", { keepAlive });
    client.connect();
    await flush();
    const socket = FakeSocket.last();
    vi.useFakeTimers();
    socket.open();
    // Simulate a half-dead socket: still "open" but sends fail.
    socket.send = () => {
      throw new Error("socket is dead");
    };

    vi.advanceTimersByTime(1000);
    expect(client.getStatus()).toBe("reconnecting");
  });
});

describe("connection lifecycle", () => {
  it("resolves the URL, opens a socket and reports status changes", async () => {
    const statuses: SocketStatus[] = [];
    const client = createClient(async () => "wss://test/de?token=t1");
    client.subscribe((s) => statuses.push(s));

    client.connect();
    client.connect(); // no-op while the first connect is in progress
    expect(client.getStatus()).toBe("connecting");
    await flush();

    expect(FakeSocket.instances).toHaveLength(1);
    expect(FakeSocket.last().url).toBe("wss://test/de?token=t1");
    FakeSocket.last().open();

    expect(client.getStatus()).toBe("open");
    expect(statuses).toEqual(["connecting", "open"]);
  });

  it("reconnects with a freshly resolved URL after the connection drops", async () => {
    let version = 1;
    const client = createClient(async () => `wss://test/de?token=t${version}`);
    client.connect();
    await flush();
    FakeSocket.last().open();

    version = 2;
    FakeSocket.last().drop();
    expect(client.getStatus()).toBe("reconnecting");

    await new Promise((r) => setTimeout(r, 30));
    expect(FakeSocket.instances).toHaveLength(2);
    expect(FakeSocket.last().url).toBe("wss://test/de?token=t2");
    FakeSocket.last().open();
    expect(client.getStatus()).toBe("open");
  });

  it("stops and reports `closed` when the URL cannot be resolved (e.g. session expired)", async () => {
    const client = createClient(async () => {
      throw new Error("Sessão expirada.");
    });

    await expect(client.sendPrompt("x")).rejects.toThrow("Sessão expirada.");
    await new Promise((r) => setTimeout(r, 30));

    expect(client.getStatus()).toBe("closed");
    expect(FakeSocket.instances).toHaveLength(0);
  });

  it("reconnectNow() skips the backoff timer and is a no-op while open", async () => {
    const client = createClient(() => "wss://test", { reconnectDelayMs: 60_000 });
    client.connect();
    await flush();
    FakeSocket.last().open();
    client.reconnectNow();
    expect(FakeSocket.instances).toHaveLength(1);

    FakeSocket.last().drop();
    expect(client.getStatus()).toBe("reconnecting");
    client.reconnectNow();
    await flush();
    expect(FakeSocket.instances).toHaveLength(2);
  });

  it("notifies onAuthError when the session cannot be refreshed and stops retrying", async () => {
    const onAuthError = vi.fn();
    const client = createClient(
      async () => {
        throw new Error("Sessão expirada.");
      },
      { onAuthError },
    );
    client.connect();
    await flush();

    expect(onAuthError).toHaveBeenCalledTimes(1);
    expect(onAuthError.mock.calls[0]?.[0]).toBeInstanceOf(SocketError);
    expect(client.getStatus()).toBe("closed");
    await new Promise((r) => setTimeout(r, 30));
    expect(FakeSocket.instances).toHaveLength(0);
  });

  it("close() stops reconnecting and rejects pending requests", async () => {
    const client = createClient();
    client.connect();
    await flush();
    FakeSocket.last().open();

    const pending = client.sendPrompt("x");
    await flush();
    client.close();

    await expect(pending).rejects.toBeInstanceOf(SocketError);
    expect(client.getStatus()).toBe("closed");
    await new Promise((r) => setTimeout(r, 30));
    expect(FakeSocket.instances).toHaveLength(1);
  });

  it("close() while the handshake is in progress waits for it to finish (no Firefox noise)", async () => {
    const client = createClient();
    client.connect();
    await flush();
    const socket = FakeSocket.last();
    expect(socket.readyState).toBe(WebSocket.CONNECTING);

    client.close();
    expect(client.getStatus()).toBe("closed");
    expect(socket.readyState).toBe(WebSocket.CONNECTING); // not closed mid-handshake

    socket.open();
    expect(socket.readyState).toBe(WebSocket.CLOSED); // closed right after opening
    expect(client.getStatus()).toBe("closed");
  });

  it("close() during URL resolution cancels the connection", async () => {
    const client = createClient(async () => {
      await flush();
      return "wss://late";
    });
    client.connect();
    client.close();
    await new Promise((r) => setTimeout(r, 10));

    expect(FakeSocket.instances).toHaveLength(0);
    expect(client.getStatus()).toBe("closed");
  });
});

describe("sendPrompt", () => {
  async function openClient() {
    const client = createClient();
    client.connect();
    await flush();
    const socket = FakeSocket.last();
    socket.open();
    return { client, socket };
  }

  it("sends the prompt frame and resolves with the result after `accepted`", async () => {
    const { client, socket } = await openClient();
    const onAccepted = vi.fn();

    const promise = client.sendPrompt("Criar API de tarefas", { onAccepted });
    await flush();
    expect(socket.sent).toEqual([{ action: "prompt", prompt: "Criar API de tarefas" }]);

    socket.receive({ type: "accepted", request_id: "req-1" });
    expect(onAccepted).toHaveBeenCalledWith("req-1");

    socket.receive({ type: "result", request_id: "req-1", result: mockResultado });
    await expect(promise).resolves.toEqual({ requestId: "req-1", result: mockResultado });
  });

  it("ignores results for unknown request ids", async () => {
    const { client, socket } = await openClient();
    const promise = client.sendPrompt("x", { timeoutMs: 50 });
    await flush();
    socket.receive({ type: "accepted", request_id: "req-1" });
    socket.receive({ type: "result", request_id: "someone-else", result: mockResultado });

    await expect(promise).rejects.toThrow(/Tempo esgotado/);
  });

  it("accepts a result that arrives before `accepted` when it is the only request", async () => {
    const { client, socket } = await openClient();
    const promise = client.sendPrompt("x");
    await flush();
    socket.receive({ type: "result", request_id: "req-1", result: mockResultado });
    await expect(promise).resolves.toEqual({ requestId: "req-1", result: mockResultado });
  });

  it("rejects with the server error message", async () => {
    const { client, socket } = await openClient();
    const promise = client.sendPrompt("x");
    await flush();
    socket.receive({ type: "accepted", request_id: "req-1" });
    socket.receive({ type: "error", request_id: "req-1", message: "Prompt inválido" });
    await expect(promise).rejects.toThrow("Prompt inválido");
  });

  it("times out when no result arrives", async () => {
    const { client } = await openClient();
    await expect(client.sendPrompt("slow", { timeoutMs: 10 })).rejects.toThrow(/Tempo esgotado/);
  });

  it("rejects in-flight requests when the connection drops", async () => {
    const { client, socket } = await openClient();
    const promise = client.sendPrompt("x");
    await flush();
    socket.drop();
    await expect(promise).rejects.toThrow(/encerrada/);
  });

  it("waits for the connection to open before sending", async () => {
    const client = createClient();
    const promise = client.sendPrompt("queued");
    await flush();

    const socket = FakeSocket.last();
    expect(socket.sent).toHaveLength(0);
    socket.open();
    await flush();
    expect(socket.sent).toEqual([{ action: "prompt", prompt: "queued" }]);

    socket.receive({ type: "accepted", request_id: "r" });
    socket.receive({ type: "result", request_id: "r", result: mockResultado });
    await expect(promise).resolves.toEqual({ requestId: "r", result: mockResultado });
  });

  it("matches `accepted` frames to requests in FIFO order", async () => {
    const { client, socket } = await openClient();
    const first = client.sendPrompt("first");
    const second = client.sendPrompt("second");
    await flush();

    socket.receive({ type: "accepted", request_id: "A" });
    socket.receive({ type: "accepted", request_id: "B" });
    socket.receive({
      type: "result",
      request_id: "B",
      result: { ...mockResultado, analysis_date: "B" },
    });
    socket.receive({
      type: "result",
      request_id: "A",
      result: { ...mockResultado, analysis_date: "A" },
    });

    await expect(first).resolves.toMatchObject({ requestId: "A", result: { analysis_date: "A" } });
    await expect(second).resolves.toMatchObject({ requestId: "B", result: { analysis_date: "B" } });
  });

  it("ignores malformed frames without breaking the connection", async () => {
    const { client, socket } = await openClient();
    socket.receiveRaw("not json");
    socket.receive({ foo: "bar" });
    socket.receive({ type: "unknown-type" });
    expect(client.getStatus()).toBe("open");
    expect(console.warn).toHaveBeenCalledTimes(3);
  });

  describe("cancellation (AbortSignal)", () => {
    it("rejects with AbortError and sends nothing when the signal is already aborted", async () => {
      const { client, socket } = await openClient();
      const controller = new AbortController();
      controller.abort();
      await expect(client.sendPrompt("x", { signal: controller.signal })).rejects.toBeInstanceOf(
        AbortError,
      );
      expect(socket.sent).toHaveLength(0);
    });

    it("cancelled before `accepted`: keeps its queue slot so the next prompt gets the right id", async () => {
      const { client, socket } = await openClient();
      const first = new AbortController();
      const onAcceptedFirst = vi.fn();
      const p1 = client.sendPrompt("first", { signal: first.signal, onAccepted: onAcceptedFirst });
      await flush();

      first.abort();
      await expect(p1).rejects.toBeInstanceOf(AbortError);

      // User immediately sends another prompt, before the server acknowledged the first one.
      const onAcceptedSecond = vi.fn();
      const p2 = client.sendPrompt("second", { onAccepted: onAcceptedSecond });
      await flush();
      expect(socket.sent.map((m) => (m as { prompt: string }).prompt)).toEqual(["first", "second"]);

      // Server acknowledges in order: A belongs to the cancelled prompt, B to the new one.
      socket.receive({ type: "accepted", request_id: "A" });
      socket.receive({ type: "accepted", request_id: "B" });
      expect(onAcceptedFirst).not.toHaveBeenCalled();
      expect(onAcceptedSecond).toHaveBeenCalledWith("B");

      // The stale result for A is discarded; B resolves the second prompt.
      socket.receive({
        type: "result",
        request_id: "A",
        result: { ...mockResultado, analysis_date: "A" },
      });
      socket.receive({
        type: "result",
        request_id: "B",
        result: { ...mockResultado, analysis_date: "B" },
      });
      await expect(p2).resolves.toMatchObject({ requestId: "B", result: { analysis_date: "B" } });
    });

    it("cancelled after `accepted`: its late result and errors are ignored", async () => {
      const { client, socket } = await openClient();
      const controller = new AbortController();
      const p1 = client.sendPrompt("first", { signal: controller.signal });
      await flush();
      socket.receive({ type: "accepted", request_id: "A" });

      controller.abort();
      await expect(p1).rejects.toBeInstanceOf(AbortError);

      const p2 = client.sendPrompt("second");
      await flush();
      socket.receive({ type: "accepted", request_id: "B" });
      socket.receive({ type: "error", request_id: "A", message: "too late" });
      socket.receive({ type: "result", request_id: "A", result: mockResultado });
      socket.receive({ type: "result", request_id: "B", result: mockResultado });

      await expect(p2).resolves.toEqual({ requestId: "B", result: mockResultado });
      expect(console.warn).not.toHaveBeenCalled();
    });

    it("does not attribute an out-of-order result to a cancelled request", async () => {
      const { client, socket } = await openClient();
      const controller = new AbortController();
      const p1 = client.sendPrompt("first", { signal: controller.signal });
      await flush();
      controller.abort();
      await expect(p1).rejects.toBeInstanceOf(AbortError);

      const p2 = client.sendPrompt("second", { timeoutMs: 30 });
      await flush();
      // A result with an unknown id while a cancelled prompt still awaits `accepted`: ambiguous, dropped.
      socket.receive({ type: "result", request_id: "X", result: mockResultado });
      await expect(p2).rejects.toThrow(/Tempo esgotado/);
    });

    it("a generic server error is assigned to the first active (non-cancelled) request", async () => {
      const { client, socket } = await openClient();
      const controller = new AbortController();
      const p1 = client.sendPrompt("first", { signal: controller.signal });
      await flush();
      controller.abort();
      await expect(p1).rejects.toBeInstanceOf(AbortError);

      const p2 = client.sendPrompt("second");
      await flush();
      socket.receive({ type: "error", message: "quota exceeded" });
      await expect(p2).rejects.toThrow("quota exceeded");
    });
  });

  describe("strict validation of server frames", () => {
    it("fails the request immediately when the result carries unexpected keys", async () => {
      const { client, socket } = await openClient();
      const promise = client.sendPrompt("x");
      await flush();
      socket.receive({ type: "accepted", request_id: "r1" });
      socket.receive({
        type: "result",
        request_id: "r1",
        result: { ...mockResultado, debug_info: { tokens: 12 } },
      });

      await expect(promise).rejects.toThrow(
        /Resposta inválida do servidor \(result\).*Unrecognized key/,
      );
      expect(client.getStatus()).toBe("open");
    });

    it("fails the request when the result payload is missing fields", async () => {
      const { client, socket } = await openClient();
      const promise = client.sendPrompt("x");
      await flush();
      socket.receive({ type: "accepted", request_id: "r1" });
      socket.receive({ type: "result", request_id: "r1", result: { analysis_date: "2026-11-02" } });

      await expect(promise).rejects.toThrow(/result\.mermaid_diagram/);
    });

    it("fails the request when the `accepted` frame is malformed", async () => {
      const { client, socket } = await openClient();
      const promise = client.sendPrompt("x");
      await flush();
      socket.receive({ type: "accepted", request_id: "r1", connectionId: "abc" });

      await expect(promise).rejects.toThrow(/Resposta inválida do servidor \(accepted\)/);
    });

    it("does not touch other requests when an invalid frame targets an unknown id", async () => {
      const { client, socket } = await openClient();
      const promise = client.sendPrompt("x");
      await flush();
      socket.receive({ type: "accepted", request_id: "r1" });
      socket.receive({ type: "result", request_id: "other", result: { bad: true } });
      socket.receive({ type: "error", request_id: "other", code: 500 });

      socket.receive({ type: "result", request_id: "r1", result: mockResultado });
      await expect(promise).resolves.toEqual({ requestId: "r1", result: mockResultado });
    });

    it("never sends an empty prompt", async () => {
      const { client, socket } = await openClient();
      await expect(client.sendPrompt("")).rejects.toThrow();
      expect(socket.sent).toHaveLength(0);
    });
  });
});
