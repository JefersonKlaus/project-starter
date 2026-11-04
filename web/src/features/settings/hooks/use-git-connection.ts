import { useSubmitState } from "./use-submit-state";
import { ApiError, salvarConexaoGit, type ConexaoGit } from "@/lib/infra-api";

function describeError(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return "Ocorreu um erro inesperado. Tente novamente.";
}

/** Sends the Git provider connection data to the backend. */
export function useGitConnection() {
  const { status, submitting, run, fail, reset } = useSubmitState(describeError);

  const submit = (conexao: ConexaoGit) =>
    run(
      () => salvarConexaoGit(conexao),
      "Dados enviados. A conexão com o provedor será estabelecida pelo backend.",
    );

  return { status, submitting, submit, fail, reset };
}
