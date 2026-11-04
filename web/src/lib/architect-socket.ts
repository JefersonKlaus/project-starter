// ============================================================================
// Architecture generator WebSocket client (src/lib/architect-socket.ts)
// ----------------------------------------------------------------------------
// Talks to the API Gateway WebSocket API that runs the AI generation.
//
//   URL:  wss://<VITE_WS_API_ID>.execute-api.us-east-2.amazonaws.com/dev?token=<jwt>
//         (region is fixed; the API id comes from the env; the stage defaults
//         to "dev" and can be overridden with VITE_WS_STAGE)
//
// Authentication: browsers cannot set headers on the WebSocket handshake, so
// the Cognito JWT is sent as a query-string parameter on `$connect`. The
// backend's Lambda authorizer must read it from
// `route.request.querystring.<VITE_WS_AUTH_PARAM>` (default: "token").
//
// Resilience:
//   - Keepalive: browsers cannot send WebSocket ping frames and API Gateway
//     drops connections idle for 10 minutes, so an application-level message
//     ({ "action": "ping" } by default) is sent periodically while open.
//     The backend may answer { "type": "pong" } (ignored) or route it to
//     `$default`; any reply is harmless.
//   - Reconnect: when the connection closes for any reason other than
//     `close()`, a new connection is attempted with exponential backoff and
//     jitter. The URL is resolved again before each attempt, so a refreshed
//     Cognito token (REFRESH_TOKEN_AUTH) is used when the previous one expired.
//
// Protocol (JSON text frames):
//
//   client -> server   { "action": "prompt", "prompt": "<text>" }
//   server -> client   { "type": "accepted", "request_id": "<id>" }      (1st reply)
//   server -> client   { "type": "result",   "request_id": "<id>", "result": {...} }
//   server -> client   { "type": "error",    "request_id"?: "<id>", "message"?: "..." }
//   server -> client   { "type": "pong" }                                 (keepalive)
//
// Every incoming frame is validated with the strict Zod schemas in
// `architect-messages.ts`; a frame that does not match the contract exactly
// is never processed, and the request it belongs to fails right away.
//
// The class is framework-agnostic; React integration lives in
// `architect-socket-context.tsx`.
// ============================================================================

import {
  parseServerMessage,
  promptMessageSchema,
  type PromptMessage,
  type ResultadoGeracao,
  type ServerMessage,
} from "./architect-messages";

export type { PromptMessage, ServerMessage };

// ----------------------------------------------------------------------------
// Configuration
// ----------------------------------------------------------------------------

const WS_REGION = "us-east-2";
const DEFAULT_WS_STAGE = "dev";
const DEFAULT_AUTH_PARAM = "token";
/** API Gateway idle timeout is 10 minutes; ping well before that. */
const DEFAULT_KEEPALIVE_SECONDS = 240;
const DEFAULT_KEEPALIVE_ACTION = "ping";

export interface WebSocketAuth {
  /** Cognito access token (default) or id token, depending on VITE_WS_AUTH_TOKEN. */
  accessToken: string;
  idToken: string;
}

/** Base URL (without credentials) built from `VITE_WS_API_ID`. Throws when the variable is missing. */
export function getWebSocketBaseUrl(): string {
  const apiId = import.meta.env.VITE_WS_API_ID?.trim();
  if (!apiId) {
    throw new Error("Configuração ausente: defina VITE_WS_API_ID (veja o arquivo .env).");
  }
  const stage = (import.meta.env.VITE_WS_STAGE?.trim() || DEFAULT_WS_STAGE).replace(
    /^\/+|\/+$/g,
    "",
  );
  return `wss://${apiId}.execute-api.${WS_REGION}.amazonaws.com/${stage}`;
}

/**
 * Full connection URL including the Cognito token as a query-string parameter.
 * Built at every (re)connect so a refreshed token is always used.
 */
export function getWebSocketUrl(auth: WebSocketAuth): string {
  const url = new URL(getWebSocketBaseUrl());
  const param = import.meta.env.VITE_WS_AUTH_PARAM?.trim() || DEFAULT_AUTH_PARAM;
  const useIdToken = import.meta.env.VITE_WS_AUTH_TOKEN?.trim().toLowerCase() === "id";
  url.searchParams.set(param, useIdToken ? auth.idToken : auth.accessToken);
  return url.toString();
}

export interface KeepAliveConfig {
  /** Interval between keepalive messages; 0 disables keepalive. */
  intervalMs: number;
  /** Frame sent as keepalive. */
  message: Record<string, unknown>;
}

/** Keepalive settings from `VITE_WS_KEEPALIVE_SECONDS` / `VITE_WS_KEEPALIVE_ACTION`. */
export function getKeepAliveConfig(): KeepAliveConfig {
  const raw = import.meta.env.VITE_WS_KEEPALIVE_SECONDS?.trim();
  const seconds = raw === undefined || raw === "" ? DEFAULT_KEEPALIVE_SECONDS : Number(raw);
  const action = import.meta.env.VITE_WS_KEEPALIVE_ACTION?.trim() || DEFAULT_KEEPALIVE_ACTION;
  return {
    intervalMs: Number.isFinite(seconds) && seconds > 0 ? seconds * 1000 : 0,
    message: { action },
  };
}

// ----------------------------------------------------------------------------
// Client
// ----------------------------------------------------------------------------

export type SocketStatus = "idle" | "connecting" | "open" | "reconnecting" | "closed";

/** Resolves the connection URL right before each connection attempt. */
export type UrlResolver = () => string | Promise<string>;

export class SocketError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SocketError";
  }
}

export interface SendPromptOptions {
  /** Called as soon as the server acknowledges the request with its `request_id`. */
  onAccepted?: (requestId: string) => void;
  /** Max time to wait for the final result (default: 10 minutes). */
  timeoutMs?: number;
  /**
   * Cancels the request on the client: the promise rejects with an
   * `AbortError` and whatever the server later sends for this request is
   * discarded. (The backend keeps processing; no cancel frame is sent.)
   */
  signal?: AbortSignal;
}

/** Resolved value of `sendPrompt`: the result together with the id it belongs to. */
export interface PromptResponse {
  requestId: string;
  result: ResultadoGeracao;
}

/** Thrown when a request is cancelled through its `AbortSignal`. */
export class AbortError extends Error {
  constructor(message = "Solicitação cancelada.") {
    super(message);
    this.name = "AbortError";
  }
}

export function isAbortError(error: unknown): error is AbortError {
  return error instanceof Error && error.name === "AbortError";
}

interface PendingRequest {
  requestId: string | null;
  resolve: (response: PromptResponse) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
  onAccepted: ((requestId: string) => void) | undefined;
  /**
   * Set when the caller aborted the request. A cancelled request that has not
   * been acknowledged yet stays in the queue so the server's `accepted` for it
   * is consumed by it (and not mis-assigned to the next prompt); its result is
   * then discarded.
   */
  cancelled: boolean;
}

/** How many discarded request ids to remember (results for them are ignored). */
const MAX_DISCARDED_IDS = 50;

/** Minimal subset of the WebSocket API used by the client (allows a fake in tests). */
export type SocketLike = Pick<WebSocket, "send" | "close" | "readyState"> & {
  onopen: ((ev: Event) => void) | null;
  onmessage: ((ev: MessageEvent) => void) | null;
  onclose: ((ev: CloseEvent) => void) | null;
  onerror: ((ev: Event) => void) | null;
};

export interface ArchitectSocketOptions {
  /** Socket factory; defaults to the browser's `WebSocket`. */
  createSocket?: (url: string) => SocketLike;
  /** Base delay for reconnection backoff (default 1s, doubles up to `maxReconnectDelayMs`). */
  reconnectDelayMs?: number;
  maxReconnectDelayMs?: number;
  defaultTimeoutMs?: number;
  /** Keepalive settings; defaults to `getKeepAliveConfig()`. */
  keepAlive?: KeepAliveConfig;
  /**
   * Called when the connection URL could not be resolved (e.g. the Cognito
   * session expired and could not be refreshed). Reconnection stops; the app
   * should send the user back to the login screen.
   */
  onAuthError?: (error: Error) => void;
}

const DEFAULT_TIMEOUT_MS = 10 * 60 * 1000;
/** WebSocket.readyState value while the handshake is in progress. */
const READY_STATE_CONNECTING = 0;

/** Hides the token when logging the connection URL. */
function redactUrl(url: string): string {
  try {
    const u = new URL(url);
    for (const key of [...u.searchParams.keys()]) u.searchParams.set(key, "***");
    return u.toString();
  } catch {
    return url;
  }
}

function debug(...args: unknown[]) {
  if (import.meta.env.DEV) console.debug("[architect-socket]", ...args);
}

export class ArchitectSocket {
  private socket: SocketLike | null = null;
  private status: SocketStatus = "idle";
  private readonly listeners = new Set<(status: SocketStatus) => void>();
  private readonly pending: PendingRequest[] = [];
  /** Ids of cancelled requests whose server replies must be ignored. */
  private readonly discardedIds: string[] = [];
  private readonly openWaiters: Array<{ resolve: () => void; reject: (e: Error) => void }> = [];
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private closedByUser = false;
  /** Non-null while the URL is being resolved (before the socket object exists). */
  private connectToken: object | null = null;
  private keepAliveTimer: ReturnType<typeof setInterval> | null = null;

  private readonly createSocket: (url: string) => SocketLike;
  private readonly reconnectDelayMs: number;
  private readonly maxReconnectDelayMs: number;
  private readonly defaultTimeoutMs: number;
  private readonly keepAlive: KeepAliveConfig;
  private readonly onAuthError: ((error: Error) => void) | undefined;

  constructor(
    private readonly resolveUrl: UrlResolver,
    options: ArchitectSocketOptions = {},
  ) {
    this.createSocket = options.createSocket ?? ((u) => new WebSocket(u));
    this.reconnectDelayMs = options.reconnectDelayMs ?? 1000;
    this.maxReconnectDelayMs = options.maxReconnectDelayMs ?? 30_000;
    this.defaultTimeoutMs = options.defaultTimeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.keepAlive = options.keepAlive ?? getKeepAliveConfig();
    this.onAuthError = options.onAuthError;
  }

  // ---- status -------------------------------------------------------------

  getStatus(): SocketStatus {
    return this.status;
  }

  /** Subscribes to status changes. Returns the unsubscribe function. */
  subscribe(listener: (status: SocketStatus) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private setStatus(status: SocketStatus) {
    if (this.status === status) return;
    this.status = status;
    for (const listener of this.listeners) listener(status);
  }

  // ---- connection lifecycle ----------------------------------------------

  /** Opens the connection (no-op if already open/connecting). */
  connect(): void {
    this.closedByUser = false;
    // A socket object exists while connecting or open; `onclose` clears it.
    if (this.socket || this.connectToken) return;
    this.clearReconnectTimer();
    this.setStatus(this.reconnectAttempts > 0 ? "reconnecting" : "connecting");

    const token = {};
    this.connectToken = token;
    Promise.resolve()
      .then(() => this.resolveUrl())
      .then(
        (url) => {
          if (this.connectToken !== token) return; // close() was called meanwhile
          this.connectToken = null;
          this.openSocket(url);
        },
        (error: unknown) => {
          if (this.connectToken !== token) return;
          this.connectToken = null;
          // Could not build the URL (e.g. session expired and refresh failed):
          // retrying would fail the same way, so stop and let the app react.
          const reason = error instanceof Error ? error.message : "Falha ao preparar a conexão.";
          const authError = new SocketError(reason);
          this.failAll(authError);
          this.setStatus("closed");
          this.onAuthError?.(authError);
        },
      );
  }

  private openSocket(url: string): void {
    debug("connecting to", redactUrl(url));
    const socket = this.createSocket(url);
    this.socket = socket;

    socket.onopen = () => {
      if (this.socket !== socket) return;
      debug("connected");
      this.reconnectAttempts = 0;
      this.setStatus("open");
      this.startKeepAlive();
      const waiters = this.openWaiters.splice(0);
      for (const w of waiters) w.resolve();
    };

    socket.onmessage = (event) => {
      if (this.socket !== socket) return;
      this.handleMessage(event.data);
    };

    socket.onerror = () => {
      // The browser always follows an error with a close event; handled there.
    };

    socket.onclose = (event) => {
      if (this.socket !== socket) return;
      // 1000 = normal, 1001 = going away, 1006 = abnormal (handshake failure,
      // network drop, or the server closing without a close frame).
      debug("closed", { code: event?.code, reason: event?.reason, wasClean: event?.wasClean });
      this.socket = null;
      this.stopKeepAlive();
      this.failAll(new SocketError("A conexão com o servidor foi encerrada."));

      if (this.closedByUser) {
        this.setStatus("closed");
        return;
      }
      this.scheduleReconnect();
    };
  }

  /** Closes the connection and stops reconnecting. Pending requests are rejected. */
  close(): void {
    this.closedByUser = true;
    this.connectToken = null;
    this.clearReconnectTimer();
    this.stopKeepAlive();
    const socket = this.socket;
    this.socket = null;
    this.failAll(new SocketError("Conexão encerrada."));
    this.setStatus("closed");
    if (socket) {
      socket.onmessage = socket.onclose = socket.onerror = null;
      if (socket.readyState === READY_STATE_CONNECTING) {
        // Closing a socket mid-handshake makes Firefox log
        // "can't establish a connection to the server" even though nothing is
        // wrong. Let the handshake finish, then close quietly.
        socket.onopen = () => {
          try {
            socket.close();
          } catch {
            // ignore
          }
        };
        return;
      }
      socket.onopen = null;
      try {
        socket.close();
      } catch {
        // ignore
      }
    }
  }

  /**
   * Reconnects right away if the connection is not open (used on `online` /
   * tab-visible events). Pending backoff timers are skipped.
   */
  reconnectNow(): void {
    if (this.status === "open" || this.socket || this.connectToken) return;
    this.connect();
  }

  private scheduleReconnect() {
    // Exponential backoff with jitter to avoid thundering herds after an outage.
    const base = Math.min(
      this.reconnectDelayMs * 2 ** this.reconnectAttempts,
      this.maxReconnectDelayMs,
    );
    const delay = Math.round(base * (0.8 + Math.random() * 0.4));
    this.reconnectAttempts += 1;
    this.setStatus("reconnecting");
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.closedByUser) this.connect();
    }, delay);
  }

  private clearReconnectTimer() {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  // ---- keepalive ----------------------------------------------------------

  private startKeepAlive() {
    this.stopKeepAlive();
    if (this.keepAlive.intervalMs <= 0) return;
    this.keepAliveTimer = setInterval(() => this.sendKeepAlive(), this.keepAlive.intervalMs);
  }

  private stopKeepAlive() {
    if (this.keepAliveTimer !== null) {
      clearInterval(this.keepAliveTimer);
      this.keepAliveTimer = null;
    }
  }

  private sendKeepAlive() {
    const socket = this.socket;
    if (!socket || this.status !== "open") return;
    try {
      socket.send(JSON.stringify(this.keepAlive.message));
    } catch {
      // The socket is dead but `close` has not fired yet: force it so the
      // normal reconnection path kicks in.
      this.stopKeepAlive();
      try {
        socket.close();
      } catch {
        // ignore
      }
    }
  }

  /** Resolves when the socket is open; connects first if needed. */
  private waitForOpen(): Promise<void> {
    if (this.status === "open" && this.socket) return Promise.resolve();
    // No connection in progress (idle/closed, or waiting for a reconnect timer): connect now.
    if (!this.socket && !this.connectToken) this.connect();
    return new Promise((resolve, reject) => {
      this.openWaiters.push({ resolve, reject });
    });
  }

  // ---- requests -----------------------------------------------------------

  /**
   * Sends `{ action: "prompt", prompt }` and resolves with the generation result
   * and the `request_id` it belongs to. The promise rejects on server error,
   * timeout, connection drop, or when `options.signal` is aborted.
   */
  async sendPrompt(prompt: string, options: SendPromptOptions = {}): Promise<PromptResponse> {
    if (options.signal?.aborted) throw new AbortError();
    await this.waitForOpen();
    if (options.signal?.aborted) throw new AbortError();
    const socket = this.socket;
    if (!socket) throw new SocketError("Conexão indisponível.");

    return new Promise<PromptResponse>((resolve, reject) => {
      const timeoutMs = options.timeoutMs ?? this.defaultTimeoutMs;
      const request: PendingRequest = {
        requestId: null,
        resolve,
        reject,
        onAccepted: options.onAccepted,
        cancelled: false,
        timer: setTimeout(() => {
          this.removePending(request);
          reject(new SocketError("Tempo esgotado aguardando a resposta do servidor."));
        }, timeoutMs),
      };
      this.pending.push(request);

      options.signal?.addEventListener("abort", () => this.cancel(request), { once: true });

      const message: PromptMessage = promptMessageSchema.parse({ action: "prompt", prompt });
      try {
        socket.send(JSON.stringify(message));
      } catch (error) {
        this.removePending(request);
        reject(error instanceof Error ? error : new SocketError("Falha ao enviar a mensagem."));
      }
    });
  }

  /** Aborts a request locally; see `PendingRequest.cancelled`. */
  private cancel(request: PendingRequest) {
    if (!this.pending.includes(request) || request.cancelled) return;
    request.cancelled = true;
    request.reject(new AbortError());

    if (request.requestId !== null) {
      // Already acknowledged: nothing else to correlate, just ignore its replies.
      this.discard(request.requestId);
      this.removePending(request);
      return;
    }
    // Not acknowledged yet: keep it queued (its timeout still removes it) so the
    // next `accepted` frame is attributed to it and not to a newer prompt.
    debug("request cancelled before `accepted`; keeping its queue slot");
  }

  private discard(requestId: string) {
    this.discardedIds.push(requestId);
    if (this.discardedIds.length > MAX_DISCARDED_IDS) this.discardedIds.shift();
  }

  private isDiscarded(requestId: string | undefined): boolean {
    return requestId !== undefined && this.discardedIds.includes(requestId);
  }

  private handleMessage(data: unknown) {
    const parsed = parseServerMessage(data);
    if (!parsed.ok) {
      this.handleInvalidMessage(parsed.type, parsed.requestId, parsed.reason);
      return;
    }
    const message: ServerMessage = parsed.message;

    switch (message.type) {
      case "pong":
        return; // keepalive reply
      case "accepted": {
        // The prompt message carries no client id, so the first un-acknowledged
        // request (FIFO, cancelled ones included) is the one this `accepted`
        // belongs to.
        const request = this.pending.find((p) => p.requestId === null);
        if (!request) return;
        request.requestId = message.request_id;
        if (request.cancelled) {
          // Its `accepted` arrived after the user gave up: remember the id so
          // the eventual result is dropped, and free the slot.
          this.discard(message.request_id);
          this.removePending(request);
          return;
        }
        request.onAccepted?.(message.request_id);
        return;
      }
      case "result": {
        if (this.isDiscarded(message.request_id)) {
          debug("result ignored (request was cancelled):", message.request_id);
          return;
        }
        const request = this.findByRequestId(message.request_id);
        if (!request) {
          console.warn("[architect-socket] Resultado sem requisição pendente:", message.request_id);
          return;
        }
        this.removePending(request);
        request.resolve({ requestId: message.request_id, result: message.result });
        return;
      }
      case "error": {
        if (this.isDiscarded(message.request_id)) return;
        const request = this.findByRequestId(message.request_id) ?? this.firstActive();
        const text = message.message ?? message.error ?? "O servidor retornou um erro.";
        if (!request) {
          console.warn("[architect-socket] Erro do servidor sem requisição pendente:", text);
          return;
        }
        this.removePending(request);
        request.reject(new SocketError(text));
        return;
      }
    }
  }

  /**
   * A frame that failed strict validation. If it can be tied to a pending
   * request (by `request_id`, or the single request still waiting for
   * `accepted`), that request fails immediately with a descriptive error;
   * otherwise the frame is logged and dropped.
   */
  private handleInvalidMessage(
    type: string | undefined,
    requestId: string | undefined,
    reason: string,
  ) {
    console.warn(
      `[architect-socket] Mensagem inválida do servidor (${type ?? "sem tipo"}): ${reason}`,
    );
    if (type !== "accepted" && type !== "result" && type !== "error") return;
    if (this.isDiscarded(requestId)) return;

    const request =
      this.findByRequestId(requestId) ??
      (type === "accepted" ? this.pending.find((p) => p.requestId === null) : undefined);
    if (!request || request.cancelled) return;

    this.removePending(request);
    request.reject(new SocketError(`Resposta inválida do servidor (${type}): ${reason}`));
  }

  private findByRequestId(requestId: string | undefined): PendingRequest | undefined {
    if (!requestId) return undefined;
    const byId = this.pending.find((p) => p.requestId === requestId);
    if (byId) return byId;
    // Fallback: a single active request still waiting for `accepted` (frames
    // arrived out of order). Not used while a cancelled request is also waiting
    // for its `accepted`, because the attribution would be ambiguous.
    const waiting = this.pending.filter((p) => p.requestId === null);
    const single = waiting.length === 1 ? waiting[0] : undefined;
    return single && !single.cancelled ? single : undefined;
  }

  private firstActive(): PendingRequest | undefined {
    return this.pending.find((p) => !p.cancelled);
  }

  private removePending(request: PendingRequest) {
    clearTimeout(request.timer);
    const index = this.pending.indexOf(request);
    if (index >= 0) this.pending.splice(index, 1);
  }

  private failAll(error: Error) {
    const requests = this.pending.splice(0);
    for (const r of requests) {
      clearTimeout(r.timer);
      r.reject(error);
    }
    const waiters = this.openWaiters.splice(0);
    for (const w of waiters) w.reject(error);
  }
}
