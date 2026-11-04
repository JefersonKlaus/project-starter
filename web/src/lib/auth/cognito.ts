// ============================================================================
// Amazon Cognito client (src/lib/auth/cognito.ts)
// ----------------------------------------------------------------------------
// Talks directly to the public Cognito Identity Provider API
// (https://cognito-idp.<region>.amazonaws.com/) using the JSON 1.1 protocol,
// with no dependency on the AWS SDK. Covers the portal login flow:
//
//   1. signIn()              -> InitiateAuth (USER_PASSWORD_AUTH)
//   2. completeNewPassword() -> RespondToAuthChallenge (NEW_PASSWORD_REQUIRED)
//   3. refreshTokens()       -> InitiateAuth (REFRESH_TOKEN_AUTH)
//   4. globalSignOut()       -> GlobalSignOut
//   5. changePassword()      -> ChangePassword (signed-in user)
//
// Requirements on the User Pool App Client:
//   - no "client secret" (browser apps cannot keep it safe);
//   - ALLOW_USER_PASSWORD_AUTH and ALLOW_REFRESH_TOKEN_AUTH flows enabled.
// ============================================================================

import type { AuthSession } from "./session";

// ----------------------------------------------------------------------------
// Configuration from environment variables
// ----------------------------------------------------------------------------

export interface CognitoConfig {
  clientId: string;
  region: string;
}

/**
 * Reads `VITE_COGNITO_CLIENT_ID` and `VITE_COGNITO_REGION`.
 * Throws a descriptive error when either of them is missing.
 */
export function getCognitoConfig(): CognitoConfig {
  const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID?.trim();
  const region = import.meta.env.VITE_COGNITO_REGION?.trim();

  const missing = [!clientId && "VITE_COGNITO_CLIENT_ID", !region && "VITE_COGNITO_REGION"].filter(
    Boolean,
  );

  if (missing.length > 0 || !clientId || !region) {
    throw new CognitoError(
      "ConfigurationError",
      `Configuração do Cognito ausente: defina ${missing.join(" e ")} (veja o arquivo .env).`,
    );
  }

  return { clientId, region };
}

// ----------------------------------------------------------------------------
// Errors
// ----------------------------------------------------------------------------

/** Error returned by Cognito (or by the network/configuration layer). */
export class CognitoError extends Error {
  /** Exception code, e.g. "NotAuthorizedException". */
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "CognitoError";
    this.code = code;
  }
}

/** User-facing messages (pt-BR, matching the rest of the UI) for the most common Cognito codes. */
const FRIENDLY_MESSAGES: Record<string, string> = {
  NotAuthorizedException: "E-mail ou senha incorretos.",
  UserNotFoundException: "E-mail ou senha incorretos.",
  UserNotConfirmedException: "Usuário ainda não confirmado. Contate o administrador.",
  PasswordResetRequiredException:
    "É necessário redefinir a senha. Contate o administrador para receber uma nova senha temporária.",
  InvalidPasswordException:
    "A nova senha não atende à política do sistema (tamanho mínimo, maiúsculas, números e símbolos).",
  InvalidParameterException: "Dados inválidos. Verifique os campos e tente novamente.",
  TooManyRequestsException: "Muitas tentativas. Aguarde alguns instantes e tente novamente.",
  LimitExceededException: "Limite de tentativas excedido. Aguarde alguns instantes.",
  ResourceNotFoundException:
    "App client do Cognito não encontrado. Verifique VITE_COGNITO_CLIENT_ID e VITE_COGNITO_REGION.",
  InvalidUserPoolConfigurationException: "Configuração do User Pool inválida.",
  ExpiredCodeException: "A sessão expirou. Faça login novamente.",
  NetworkError: "Não foi possível conectar ao serviço de autenticação. Verifique sua conexão.",
};

/** Turns any error into a readable message to display on screen. */
export function describeAuthError(error: unknown): string {
  if (error instanceof CognitoError) {
    return FRIENDLY_MESSAGES[error.code] ?? error.message;
  }
  if (error instanceof Error && error.message) return error.message;
  return "Ocorreu um erro inesperado. Tente novamente.";
}

// ----------------------------------------------------------------------------
// Transport (Cognito JSON 1.1 protocol)
// ----------------------------------------------------------------------------

interface AuthenticationResult {
  AccessToken: string;
  IdToken: string;
  RefreshToken?: string;
  ExpiresIn: number;
  TokenType: string;
}

interface AuthResponse {
  ChallengeName?: string;
  Session?: string;
  ChallengeParameters?: Record<string, string>;
  AuthenticationResult?: AuthenticationResult;
}

async function cognitoRequest<T>(
  config: CognitoConfig,
  action: string,
  body: Record<string, unknown>,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`https://cognito-idp.${config.region}.amazonaws.com/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": `AWSCognitoIdentityProviderService.${action}`,
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new CognitoError("NetworkError", FRIENDLY_MESSAGES["NetworkError"] ?? "Network error");
  }

  const text = await response.text();
  let data: Record<string, unknown> = {};
  if (text) {
    try {
      data = JSON.parse(text) as Record<string, unknown>;
    } catch {
      data = {};
    }
  }

  if (!response.ok) {
    // The code comes in `__type` (sometimes prefixed with the Java namespace,
    // e.g. "com.amazonaws...#NotAuthorizedException") or in the x-amzn-ErrorType header.
    const rawType =
      (typeof data["__type"] === "string" && data["__type"]) ||
      response.headers.get("x-amzn-ErrorType") ||
      `HttpError${response.status}`;
    const code = rawType.split("#").pop()?.split(":")[0] ?? rawType;
    const message =
      (typeof data["message"] === "string" && data["message"]) ||
      (typeof data["Message"] === "string" && data["Message"]) ||
      `Falha na autenticação (${response.status}).`;
    throw new CognitoError(code, message);
  }

  return data as T;
}

// ----------------------------------------------------------------------------
// Token helpers
// ----------------------------------------------------------------------------

/** Decodes a JWT payload without validating the signature (only used to read claims). */
export function decodeJwtPayload(token: string): Record<string, unknown> {
  const part = token.split(".")[1];
  if (!part) return {};
  try {
    const base64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
    const json = atob(padded);
    // atob returns "latin1" bytes; re-decode as UTF-8 so accented names survive.
    const bytes = Uint8Array.from(json, (c) => c.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes)) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function toSession(
  result: AuthenticationResult,
  fallbackEmail: string,
  previousRefreshToken?: string,
): AuthSession {
  const claims = decodeJwtPayload(result.IdToken);
  const email = typeof claims["email"] === "string" ? claims["email"] : fallbackEmail;
  const refreshToken = result.RefreshToken ?? previousRefreshToken;

  return {
    accessToken: result.AccessToken,
    idToken: result.IdToken,
    ...(refreshToken ? { refreshToken } : {}),
    expiresAt: Date.now() + result.ExpiresIn * 1000,
    email,
  };
}

// ----------------------------------------------------------------------------
// Login flow
// ----------------------------------------------------------------------------

/** Data needed to complete the NEW_PASSWORD_REQUIRED challenge. */
export interface NewPasswordChallenge {
  kind: "NEW_PASSWORD_REQUIRED";
  /** Opaque challenge session token returned by Cognito (valid for ~3 minutes). */
  session: string;
  /** Internal username Cognito expects in RespondToAuthChallenge. */
  username: string;
  /** E-mail typed by the user (for display and as a fallback). */
  email: string;
  /**
   * Required User Pool attributes that are still unset (e.g. ["name"]).
   * They must be sent together with the new password.
   */
  requiredAttributes: string[];
}

export type SignInResult = { kind: "SUCCESS"; session: AuthSession } | NewPasswordChallenge;

/**
 * Step 1 — simple login with e-mail and password.
 * Returns the authenticated session or the NEW_PASSWORD_REQUIRED challenge
 * (user created by an administrator with a temporary password).
 */
export async function signIn(email: string, password: string): Promise<SignInResult> {
  const config = getCognitoConfig();
  const normalizedEmail = email.trim().toLowerCase();

  const data = await cognitoRequest<AuthResponse>(config, "InitiateAuth", {
    AuthFlow: "USER_PASSWORD_AUTH",
    ClientId: config.clientId,
    AuthParameters: {
      USERNAME: normalizedEmail,
      PASSWORD: password,
    },
  });

  if (data.AuthenticationResult) {
    return { kind: "SUCCESS", session: toSession(data.AuthenticationResult, normalizedEmail) };
  }

  if (data.ChallengeName === "NEW_PASSWORD_REQUIRED" && data.Session) {
    const params = data.ChallengeParameters ?? {};
    return {
      kind: "NEW_PASSWORD_REQUIRED",
      session: data.Session,
      username: params["USER_ID_FOR_SRP"] ?? normalizedEmail,
      email: normalizedEmail,
      requiredAttributes: parseRequiredAttributes(params["requiredAttributes"]),
    };
  }

  throw new CognitoError(
    "UnsupportedChallenge",
    `Desafio de autenticação não suportado pelo portal: ${data.ChallengeName ?? "desconhecido"}.`,
  );
}

/**
 * Step 2 — sets the new password in response to the NEW_PASSWORD_REQUIRED challenge.
 * `attributes` must contain the challenge's `requiredAttributes` (e.g. { name: "..." }).
 */
export async function completeNewPassword(
  challenge: NewPasswordChallenge,
  newPassword: string,
  attributes: Record<string, string> = {},
): Promise<AuthSession> {
  const config = getCognitoConfig();

  const challengeResponses: Record<string, string> = {
    USERNAME: challenge.username,
    NEW_PASSWORD: newPassword,
  };
  for (const [name, value] of Object.entries(attributes)) {
    challengeResponses[`userAttributes.${name}`] = value;
  }

  const data = await cognitoRequest<AuthResponse>(config, "RespondToAuthChallenge", {
    ChallengeName: "NEW_PASSWORD_REQUIRED",
    ClientId: config.clientId,
    Session: challenge.session,
    ChallengeResponses: challengeResponses,
  });

  if (!data.AuthenticationResult) {
    throw new CognitoError(
      "UnsupportedChallenge",
      `O Cognito solicitou um novo desafio não suportado: ${data.ChallengeName ?? "desconhecido"}.`,
    );
  }

  return toSession(data.AuthenticationResult, challenge.email);
}

/** Renews the access/id tokens using the current session's refresh token. */
export async function refreshTokens(session: AuthSession): Promise<AuthSession> {
  if (!session.refreshToken) {
    throw new CognitoError("NotAuthorizedException", "Sessão sem refresh token.");
  }
  const config = getCognitoConfig();

  const data = await cognitoRequest<AuthResponse>(config, "InitiateAuth", {
    AuthFlow: "REFRESH_TOKEN_AUTH",
    ClientId: config.clientId,
    AuthParameters: { REFRESH_TOKEN: session.refreshToken },
  });

  if (!data.AuthenticationResult) {
    throw new CognitoError("NotAuthorizedException", "Não foi possível renovar a sessão.");
  }

  return toSession(data.AuthenticationResult, session.email, session.refreshToken);
}

/** Invalidates all of the user's tokens in Cognito (best-effort). */
export async function globalSignOut(session: AuthSession): Promise<void> {
  const config = getCognitoConfig();
  await cognitoRequest<Record<string, never>>(config, "GlobalSignOut", {
    AccessToken: session.accessToken,
  });
}

/**
 * Changes the password of the signed-in user. Cognito validates the current
 * password and applies the User Pool policy to the new one; the session
 * (access token) must still be valid.
 */
export async function changePassword(
  session: AuthSession,
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  const config = getCognitoConfig();
  await cognitoRequest<Record<string, never>>(config, "ChangePassword", {
    AccessToken: session.accessToken,
    PreviousPassword: currentPassword,
    ProposedPassword: newPassword,
  });
}

// ----------------------------------------------------------------------------
// Internals
// ----------------------------------------------------------------------------

/**
 * `requiredAttributes` arrives as a JSON string, e.g. '["userAttributes.name"]'.
 * Returns only the attribute names, without the prefix.
 */
function parseRequiredAttributes(raw: string | undefined): string[] {
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item): item is string => typeof item === "string")
      .map((item) => item.replace(/^userAttributes\./, ""));
  } catch {
    return [];
  }
}
