import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  CognitoError,
  completeNewPassword,
  decodeJwtPayload,
  describeAuthError,
  getCognitoConfig,
  globalSignOut,
  refreshTokens,
  signIn,
  type NewPasswordChallenge,
} from "./cognito";
import { fakeJwt, makeSession } from "@/test/fixtures";

interface RecordedCall {
  url: string;
  target: string | undefined;
  body: Record<string, unknown>;
}

const calls: RecordedCall[] = [];
let responses: Array<{ status?: number; body: unknown }> = [];

/** Replaces global fetch with a scripted Cognito endpoint. */
function scriptFetch(...queue: Array<{ status?: number; body: unknown }>) {
  responses = queue;
}

beforeEach(() => {
  calls.length = 0;
  responses = [];
  vi.stubEnv("VITE_COGNITO_CLIENT_ID", "test-client-id");
  vi.stubEnv("VITE_COGNITO_REGION", "us-east-1");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit) => {
      const headers = init.headers as Record<string, string>;
      calls.push({
        url,
        target: headers["X-Amz-Target"],
        body: JSON.parse(String(init.body)) as Record<string, unknown>,
      });
      const next = responses.shift();
      if (!next) throw new Error("fetch called without a scripted response");
      return new Response(JSON.stringify(next.body), {
        status: next.status ?? 200,
        headers: { "content-type": "application/x-amz-json-1.1" },
      });
    }),
  );
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

const authResult = (email: string, extra: Record<string, unknown> = {}) => ({
  AuthenticationResult: {
    AccessToken: "access",
    IdToken: fakeJwt({ email }),
    RefreshToken: "refresh",
    ExpiresIn: 3600,
    TokenType: "Bearer",
    ...extra,
  },
});

describe("getCognitoConfig", () => {
  it("reads client id and region from the environment", () => {
    expect(getCognitoConfig()).toEqual({ clientId: "test-client-id", region: "us-east-1" });
  });

  it("throws a descriptive ConfigurationError when a variable is missing", () => {
    vi.stubEnv("VITE_COGNITO_CLIENT_ID", "");
    expect(() => getCognitoConfig()).toThrowError(/VITE_COGNITO_CLIENT_ID/);
    try {
      getCognitoConfig();
    } catch (error) {
      expect(error).toBeInstanceOf(CognitoError);
      expect((error as CognitoError).code).toBe("ConfigurationError");
    }
  });
});

describe("signIn", () => {
  it("calls InitiateAuth with USER_PASSWORD_AUTH on the regional endpoint", async () => {
    scriptFetch({ body: authResult("ana@empresa.com") });

    const result = await signIn("  Ana@Empresa.com ", "Secret123!");

    expect(calls).toHaveLength(1);
    expect(calls[0]?.url).toBe("https://cognito-idp.us-east-1.amazonaws.com/");
    expect(calls[0]?.target).toBe("AWSCognitoIdentityProviderService.InitiateAuth");
    expect(calls[0]?.body).toEqual({
      AuthFlow: "USER_PASSWORD_AUTH",
      ClientId: "test-client-id",
      AuthParameters: { USERNAME: "ana@empresa.com", PASSWORD: "Secret123!" },
    });
    expect(result.kind).toBe("SUCCESS");
    if (result.kind !== "SUCCESS") throw new Error("unreachable");
    expect(result.session.email).toBe("ana@empresa.com");
    expect(result.session.refreshToken).toBe("refresh");
    expect(result.session.expiresAt).toBeGreaterThan(Date.now() + 3500 * 1000);
  });

  it("returns the NEW_PASSWORD_REQUIRED challenge with parsed required attributes", async () => {
    scriptFetch({
      body: {
        ChallengeName: "NEW_PASSWORD_REQUIRED",
        Session: "session-token",
        ChallengeParameters: {
          USER_ID_FOR_SRP: "uuid-123",
          requiredAttributes: '["userAttributes.name","userAttributes.given_name"]',
          userAttributes: "{}",
        },
      },
    });

    const result = await signIn("novo@empresa.com", "Temp123!");

    expect(result).toEqual<NewPasswordChallenge>({
      kind: "NEW_PASSWORD_REQUIRED",
      session: "session-token",
      username: "uuid-123",
      email: "novo@empresa.com",
      requiredAttributes: ["name", "given_name"],
    });
  });

  it("falls back to the e-mail as username when USER_ID_FOR_SRP is absent", async () => {
    scriptFetch({ body: { ChallengeName: "NEW_PASSWORD_REQUIRED", Session: "s" } });
    const result = await signIn("novo@empresa.com", "Temp123!");
    expect(result).toMatchObject({ username: "novo@empresa.com", requiredAttributes: [] });
  });

  it("maps Cognito exceptions to CognitoError with a friendly message", async () => {
    scriptFetch({
      status: 400,
      body: { __type: "NotAuthorizedException", message: "Incorrect username or password." },
    });

    const error = await signIn("x@y.com", "bad").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(CognitoError);
    expect((error as CognitoError).code).toBe("NotAuthorizedException");
    expect(describeAuthError(error)).toBe("E-mail ou senha incorretos.");
  });

  it("strips the Java namespace prefix from error codes", async () => {
    scriptFetch({
      status: 400,
      body: {
        __type: "com.amazonaws.cognito#UserNotFoundException",
        message: "User does not exist.",
      },
    });
    const error = await signIn("x@y.com", "bad").catch((e: unknown) => e);
    expect((error as CognitoError).code).toBe("UserNotFoundException");
  });

  it("rejects unsupported challenges (e.g. MFA)", async () => {
    scriptFetch({ body: { ChallengeName: "SOFTWARE_TOKEN_MFA", Session: "s" } });
    await expect(signIn("x@y.com", "p")).rejects.toMatchObject({ code: "UnsupportedChallenge" });
  });

  it("wraps network failures in a NetworkError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    const error = await signIn("x@y.com", "p").catch((e: unknown) => e);
    expect((error as CognitoError).code).toBe("NetworkError");
    expect(describeAuthError(error)).toMatch(/conectar/);
  });
});

describe("completeNewPassword", () => {
  const challenge: NewPasswordChallenge = {
    kind: "NEW_PASSWORD_REQUIRED",
    session: "session-token",
    username: "uuid-123",
    email: "novo@empresa.com",
    requiredAttributes: ["name"],
  };

  it("responds to the challenge with the new password and required attributes", async () => {
    scriptFetch({ body: authResult("novo@empresa.com") });

    const session = await completeNewPassword(challenge, "NewSecret123!", {
      name: "Novo Usuário",
    });

    expect(calls[0]?.target).toBe("AWSCognitoIdentityProviderService.RespondToAuthChallenge");
    expect(calls[0]?.body).toEqual({
      ChallengeName: "NEW_PASSWORD_REQUIRED",
      ClientId: "test-client-id",
      Session: "session-token",
      ChallengeResponses: {
        USERNAME: "uuid-123",
        NEW_PASSWORD: "NewSecret123!",
        "userAttributes.name": "Novo Usuário",
      },
    });
    expect(session.email).toBe("novo@empresa.com");
    expect(session.accessToken).toBe("access");
  });

  it("surfaces password policy violations", async () => {
    scriptFetch({
      status: 400,
      body: { __type: "InvalidPasswordException", message: "Password did not conform with policy" },
    });
    const error = await completeNewPassword(challenge, "weak").catch((e: unknown) => e);
    expect((error as CognitoError).code).toBe("InvalidPasswordException");
    expect(describeAuthError(error)).toMatch(/política/);
  });

  it("rejects when Cognito answers with yet another challenge", async () => {
    scriptFetch({ body: { ChallengeName: "SMS_MFA", Session: "s2" } });
    await expect(completeNewPassword(challenge, "NewSecret123!")).rejects.toMatchObject({
      code: "UnsupportedChallenge",
    });
  });
});

describe("refreshTokens", () => {
  it("uses REFRESH_TOKEN_AUTH and keeps the previous refresh token when omitted", async () => {
    scriptFetch({ body: authResult("ana@empresa.com", { RefreshToken: undefined }) });

    const session = await refreshTokens(makeSession({ refreshToken: "old-refresh" }));

    expect(calls[0]?.body).toEqual({
      AuthFlow: "REFRESH_TOKEN_AUTH",
      ClientId: "test-client-id",
      AuthParameters: { REFRESH_TOKEN: "old-refresh" },
    });
    expect(session.refreshToken).toBe("old-refresh");
    expect(session.accessToken).toBe("access");
  });

  it("fails when the session has no refresh token", async () => {
    const session = makeSession();
    delete session.refreshToken;
    await expect(refreshTokens(session)).rejects.toBeInstanceOf(CognitoError);
    expect(calls).toHaveLength(0);
  });
});

describe("globalSignOut", () => {
  it("sends the access token to GlobalSignOut", async () => {
    scriptFetch({ body: {} });
    await globalSignOut(makeSession({ accessToken: "the-access-token" }));
    expect(calls[0]?.target).toBe("AWSCognitoIdentityProviderService.GlobalSignOut");
    expect(calls[0]?.body).toEqual({ AccessToken: "the-access-token" });
  });
});

describe("decodeJwtPayload", () => {
  it("decodes base64url payloads including UTF-8 characters", () => {
    expect(decodeJwtPayload(fakeJwt({ email: "a@b.com", name: "José Ação" }))).toEqual({
      email: "a@b.com",
      name: "José Ação",
    });
  });

  it("returns an empty object for malformed tokens", () => {
    expect(decodeJwtPayload("not-a-jwt")).toEqual({});
    expect(decodeJwtPayload("a.%%%.c")).toEqual({});
  });
});

describe("describeAuthError", () => {
  it("falls back to the raw message for unknown codes and generic errors", () => {
    expect(describeAuthError(new CognitoError("SomethingElse", "raw message"))).toBe("raw message");
    expect(describeAuthError(new Error("boom"))).toBe("boom");
    expect(describeAuthError("???")).toMatch(/inesperado/);
  });
});
