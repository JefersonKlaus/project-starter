import { useSubmitState } from "./use-submit-state";
import { changePassword, CognitoError, describeAuthError } from "@/lib/auth/cognito";
import { ensureValidSession } from "@/lib/auth/session";

function describeError(error: unknown): string {
  // In this context NotAuthorized means the current password is wrong, not the e-mail.
  if (error instanceof CognitoError && error.code === "NotAuthorizedException") {
    return "Senha atual incorreta.";
  }
  return describeAuthError(error);
}

/** Changes the signed-in user's password in Cognito. */
export function useChangePassword() {
  const { status, submitting, run, fail, reset } = useSubmitState(describeError);

  const submit = (currentPassword: string, newPassword: string) =>
    run(async () => {
      // Refreshes the access token if needed; ChangePassword requires a valid one.
      const session = await ensureValidSession();
      if (!session) throw new Error("Sessão expirada. Faça login novamente.");
      await changePassword(session, currentPassword, newPassword);
    }, "Senha alterada com sucesso.");

  return { status, submitting, submit, fail, reset };
}
