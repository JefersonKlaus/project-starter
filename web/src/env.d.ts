/// <reference types="vite/client" />

// Environment variables exposed to the browser by Vite (VITE_ prefix).
// Actual values live in the single `.env` file at the project root.
interface ImportMetaEnv {
  /** Cognito User Pool app client ID (required). */
  readonly VITE_COGNITO_CLIENT_ID?: string;
  /** AWS region where the User Pool lives, e.g. "us-east-1" (required). */
  readonly VITE_COGNITO_REGION?: string;
  /**
   * API id of the generation WebSocket API (required).
   * Final URL: wss://<id>.execute-api.us-east-2.amazonaws.com/<stage>?<param>=<jwt>
   */
  readonly VITE_WS_API_ID?: string;
  /** Stage name of the WebSocket API (optional, default "dev"). */
  readonly VITE_WS_STAGE?: string;
  /** Query-string parameter that carries the Cognito JWT on $connect (optional, default "token"). */
  readonly VITE_WS_AUTH_PARAM?: string;
  /** Which Cognito token to send: "access" (default) or "id". */
  readonly VITE_WS_AUTH_TOKEN?: string;
  /** Seconds between keepalive messages (optional, default 240; 0 disables). */
  readonly VITE_WS_KEEPALIVE_SECONDS?: string;
  /** `action` of the keepalive message (optional, default "ping"). */
  readonly VITE_WS_KEEPALIVE_ACTION?: string;
  /**
   * Base URL of the backend REST API (API Gateway HTTP/REST with Cognito authorizer),
   * e.g. "https://abc123.execute-api.us-east-2.amazonaws.com/dev". Required by the
   * settings screen (Git provider connection).
   */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
