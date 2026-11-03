## project-starter web portal

This project is the web portal of `project-starter`. It provides the interface
for interacting with the AI resources, while the back-end and processing
services are maintained separately.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
cp .env.example .env.local   # fill in your Cognito settings
npm run dev
```

## Project structure

```
src/
├── routes/                 # TanStack file-based routes — thin: route config + page composition
│   ├── login.tsx
│   ├── _authenticated.tsx  # auth guard + WebSocket provider
│   └── _authenticated/index.tsx
├── features/               # one folder per business feature (feature-sliced)
│   └── architect/
│       ├── hooks/          # behaviour: use-generation, use-corporate-rules, use-generated-files, use-project-download
│       ├── components/     # presentation: prompt-form, generation-result-card, app-header, ...
│       ├── constants.ts
│       └── index.ts        # public surface of the feature
├── lib/                    # framework-agnostic infrastructure: auth/, architect-socket, schemas, infra-api
├── hooks/                  # app-wide React hooks (use-sign-out, use-mobile)
├── components/ui/          # shadcn primitives
└── test/                   # shared test helpers and route tests
```

Rules of thumb: `routes/` only wires things together; `features/*/hooks` hold
state and side effects; `features/*/components` are presentational (props in,
events out); `lib/` has no React and is unit-tested in isolation.

## Tests

Unit and component tests run on [Vitest](https://vitest.dev) with
[Testing Library](https://testing-library.com) in a jsdom environment
(`vitest.config.ts`). No AWS access is needed: Cognito is exercised through a
scripted `fetch`, and the WebSocket through an in-memory fake socket.

```sh
npm test               # run once
npm run test:watch     # watch mode
npm run test:coverage  # with V8 coverage report (coverage/)
```

| Location                               | Covers                                                                               |
| -------------------------------------- | ------------------------------------------------------------------------------------ |
| `src/lib/auth/*.test.ts`               | Cognito client (login, `NEW_PASSWORD_REQUIRED`, refresh, errors) and session storage |
| `src/lib/architect-socket*.test.ts(x)` | WebSocket URL/auth, reconnection, prompt → accepted → result, React provider         |
| `src/lib/infra-api.test.ts`            | Corporate rules and the zip download                                                 |
| `src/test/routes/*.test.tsx`           | Login screen (both steps), authenticated guard, main page                            |

Route tests live in `src/test/routes/` on purpose: any file inside
`src/routes/` would be treated as a route by the TanStack Router generator.
Shared helpers (fixtures, fake socket, router mock) are in `src/test/`.

## Authentication (Amazon Cognito)

Login is the first screen of the portal (`/login`). Every other page lives in
`src/routes/_authenticated/` and requires a valid session; without one the user
is redirected to the login page and sent back to the original page after
authenticating.

Two-step flow:

1. **Simple login** — e-mail + password (`InitiateAuth` / `USER_PASSWORD_AUTH`).
2. **New password** — when Cognito answers `NEW_PASSWORD_REQUIRED` (user
   created by an administrator with a temporary password), the screen switches
   to the new-password step (`RespondToAuthChallenge`). Required User Pool
   attributes that are still unset (e.g. `name`) are requested in the same step.

Environment variables (see `.env.example`):

| Variable                    | Description                                                      |
| --------------------------- | ---------------------------------------------------------------- |
| `VITE_COGNITO_CLIENT_ID`    | User Pool app client ID                                          |
| `VITE_COGNITO_REGION`       | User Pool region (e.g. `us-east-1`)                              |
| `VITE_WS_API_ID`            | API id of the generation WebSocket API (see section below)       |
| `VITE_WS_STAGE`             | Stage of the WebSocket API (optional, default `dev`)             |
| `VITE_WS_AUTH_PARAM`        | Query-string name for the JWT on `$connect` (default `token`)    |
| `VITE_WS_AUTH_TOKEN`        | `access` (default) or `id` token                                 |
| `VITE_WS_KEEPALIVE_SECONDS` | Seconds between keepalive messages (default `240`, `0` disables) |
| `VITE_WS_KEEPALIVE_ACTION`  | `action` of the keepalive message (default `ping`)               |

Cognito App Client requirements: **no client secret**, with the
`ALLOW_USER_PASSWORD_AUTH` and `ALLOW_REFRESH_TOKEN_AUTH` flows enabled. Users
are identified by e-mail (use e-mail as the username or as an alias in the pool).

Tokens are stored in `localStorage` and refreshed automatically with the refresh
token. For authenticated backend calls use `getAuthHeaders()` from
`src/lib/auth/session.ts` (sends `Authorization: Bearer <idToken>`).

## Architecture generation (WebSocket)

Right after login the portal opens a WebSocket connection to the generation
backend and keeps it alive (with automatic reconnection) while the user is in
the authenticated area. The connection is closed on logout.

URL structure — region is fixed (`us-east-2`); the API id is required and the
stage defaults to `dev`:

```
wss://<VITE_WS_API_ID>.execute-api.us-east-2.amazonaws.com/<VITE_WS_STAGE>?token=<cognito access token>
```

### Authentication on `$connect`

Browsers cannot set headers on the WebSocket handshake, so the Cognito JWT is
sent as a **query-string parameter** (default name `token`, configurable with
`VITE_WS_AUTH_PARAM`). The Cognito **access token** is sent by default; set
`VITE_WS_AUTH_TOKEN=id` to send the id token instead. The URL is rebuilt before
every (re)connection so a refreshed token is always used.

The API Gateway `$connect` route must use a **Lambda REQUEST authorizer** whose
identity source is `route.request.querystring.token` (or whatever name you set).
A `401 Unauthorized` during the handshake means that authorizer rejected the
request (missing/invalid token, wrong parameter name, or wrong token type).

Protocol (JSON text frames):

```jsonc
// client -> server (textarea submit)
{ "action": "prompt", "prompt": "<text typed by the user>" }

// server -> client, first reply
{ "type": "accepted", "request_id": "<id>" }

// server -> client, final reply
{ "type": "result", "request_id": "<id>", "result": { /* ResultadoGeracao */ } }
```

### Keepalive and reconnection

- **Keepalive** — browsers cannot send WebSocket ping frames and API Gateway
  closes connections idle for 10 minutes, so the client sends
  `{ "action": "ping" }` every 4 minutes while connected. Tune with
  `VITE_WS_KEEPALIVE_SECONDS` (0 disables) and `VITE_WS_KEEPALIVE_ACTION`.
  The backend may reply `{ "type": "pong" }` (ignored) or route the message to
  `$default`; any reply is harmless. If the keepalive cannot be sent the socket
  is closed so the reconnection path kicks in.
- **Reconnection** — whenever the connection drops (network change, API
  Gateway's 2-hour limit, server restart) the client reconnects with
  exponential backoff and jitter (1 s → 30 s). It also reconnects immediately
  when the browser fires `online` or the tab becomes visible again. Requests
  in flight during a drop are rejected with a clear message.
- **Session refresh** — the URL is rebuilt before every attempt with
  `ensureValidSession()`, so an expired Cognito access token is refreshed via
  `REFRESH_TOKEN_AUTH` before connecting. If the refresh itself fails, the
  local session is cleared and the user is sent back to `/login`.

### Message validation (Zod, strict)

Every frame received from the backend is validated with the Zod schemas in
`src/lib/architect-messages.ts` before it is processed. All object schemas use
`.strict()`, so a frame is accepted **only** if it matches the contract exactly:
required fields present, correct types, and **no unknown keys** — at every
level, including each entry of `aws_services` and the `result` payload
(`analysis_date`, `mermaid_diagram`, `aws_services`, `generated_code`,
`rag_references`). The TypeScript types used by the UI are derived from these
schemas, so there is a single source of truth.

When a frame fails validation it is never processed. If it can be tied to an
in-flight request (by `request_id`, or the request still waiting for
`accepted`), that request fails immediately with
`Resposta inválida do servidor (<type>): <field>: <issue>` instead of waiting
for the timeout; otherwise the frame is logged and dropped. Adding a new field
to a backend message therefore requires updating the schema first.

### Request correlation and cancellation

The `prompt` frame carries no client-side id, so the client attributes each
`accepted` frame to the oldest prompt still waiting for one (FIFO, as the
backend answers in order); from then on every frame is matched strictly by
`request_id`. `sendPrompt` resolves with `{ requestId, result }`, and the page
shows a result **only if its `request_id` equals the id of the last prompt the
user is waiting for** — anything else is discarded.

The **Cancelar** button aborts the in-flight prompt through an `AbortSignal`
and immediately releases the form. No cancel frame is sent to the backend, so
it keeps working on the old prompt; to keep the correlation correct:

- cancelled before `accepted`: the request keeps its queue slot until its
  `accepted` arrives (otherwise that id would be attributed to the next
  prompt), then the id is remembered and its result dropped;
- cancelled after `accepted`: its id is remembered and any `result`/`error`
  for it is ignored.

A `{ "type": "error", "message": "..." }` frame rejects the in-flight request,
and requests time out after 10 minutes.
