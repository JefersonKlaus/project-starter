// ============================================================================
// Backend access layer (src/lib/infra-api.ts)
// ----------------------------------------------------------------------------
// THIS IS WHERE THE FRONTEND TALKS TO YOUR BACKEND.
//
// Each function below runs independently and asynchronously.
// ============================================================================

import JSZip from "jszip";

import type { ResultadoGeracao } from "./architect-messages";
import { ensureValidSession } from "./auth/session";

// ===== API response contract (resultado_arquitetura.json) =====
// The contract is defined once, as strict Zod schemas, in `architect-messages.ts`;
// the types are re-exported here for the UI.
export type { ArquivosPorLinguagem, ResultadoGeracao, ServicoAws } from "./architect-messages";

export interface RegraCorporativa {
  /** Human-readable rule description, e.g. "CloudWatch logs ativados". */
  descricao: string;
  /** Whether the rule must be applied when generating the architecture. */
  ativa: boolean;
}

// ----------------------------------------------------------------------------
// 1) FETCH CORPORATE RULES
// ----------------------------------------------------------------------------
// Responsible for: fetching from the backend the list of corporate rules (RAG)
//                  displayed in the left panel.
// ----------------------------------------------------------------------------
export async function buscarRegrasCorporativas(): Promise<RegraCorporativa[]> {
  // Returns the system's default rules. Once a rules endpoint exists, swap this for a fetch.
  return [
    { descricao: "Tags Obrigatórias (env=prod)", ativa: true },
    { descricao: "CloudWatch logs ativados", ativa: true },
    { descricao: "DynamoDB PITR ativado", ativa: true },
  ];
}

// ----------------------------------------------------------------------------
// 2) GENERATE ARCHITECTURE
// ----------------------------------------------------------------------------
// Generation happens over the WebSocket API — see `src/lib/architect-socket.ts`
// (`ArchitectSocket.sendPrompt`). The response follows the `ResultadoGeracao`
// contract above.
// ----------------------------------------------------------------------------

// ----------------------------------------------------------------------------
// 3) DOWNLOAD REPOSITORY ZIP
// ----------------------------------------------------------------------------
// Builds the .zip file in memory from the code and diagram returned by the AI
// and triggers the download in the browser.
// ----------------------------------------------------------------------------
export async function baixarRepositorioZip(resultado: ResultadoGeracao): Promise<void> {
  const zip = new JSZip();

  // Creates the subfolders (terraform, python, etc.) and adds the matching files
  for (const [linguagem, arquivos] of Object.entries(resultado.generated_code)) {
    const pasta = zip.folder(linguagem) ?? zip;
    for (const [nome, conteudo] of Object.entries(arquivos)) {
      pasta.file(nome, conteudo);
    }
  }

  // Adds the Mermaid diagram at the zip root
  zip.file("diagram.mmd", resultado.mermaid_diagram);

  // Generates the .zip file and starts the download
  const blob = await zip.generateAsync({ type: "blob" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "repositorio-gerado.zip";
  a.click();
  URL.revokeObjectURL(url);
}

// ----------------------------------------------------------------------------
// 4) GIT PROVIDER CONNECTION (GitHub / GitLab)
// ----------------------------------------------------------------------------
// The portal does NOT talk to GitHub/GitLab itself. The form only hands the
// connection data to the backend, which stores it and establishes the
// connection later. Nothing (in particular the token) is kept in the browser.
//
//   POST {VITE_API_BASE_URL}/integrations/git-provider
//   Authorization: Bearer <Cognito id token>
//   { "provider": "github" | "gitlab",
//     "server_url": "https://github.com",      // or a self-hosted instance
//     "username": "org-or-user",              // optional
//     "token": "<personal access token>" }
//   -> 2xx on success (body ignored); any other status is reported as an error.
// ----------------------------------------------------------------------------

export type ProvedorGit = "github" | "gitlab";

export interface ConexaoGit {
  provider: ProvedorGit;
  /** Base URL of the server (github.com / gitlab.com or a self-hosted instance). */
  serverUrl: string;
  /** Account or organization/group that owns the repositories (optional). */
  username?: string;
  /** Personal access token, forwarded to the backend as-is. */
  token: string;
}

/** Error returned by the backend REST API (or by the network/configuration layer). */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Reads `VITE_API_BASE_URL` (without trailing slash). Throws when it is missing. */
export function getApiBaseUrl(): string {
  const raw = import.meta.env.VITE_API_BASE_URL?.trim();
  if (!raw) {
    throw new ApiError(
      0,
      "Configuração do backend ausente: defina VITE_API_BASE_URL (veja o arquivo .env).",
    );
  }
  return raw.replace(/\/+$/, "");
}

/** Sends the Git provider connection data to the backend (see contract above). */
export async function salvarConexaoGit(conexao: ConexaoGit): Promise<void> {
  const baseUrl = getApiBaseUrl();
  const session = await ensureValidSession();
  if (!session) throw new ApiError(401, "Sessão expirada. Faça login novamente.");

  const username = conexao.username?.trim();
  const body = {
    provider: conexao.provider,
    server_url: conexao.serverUrl.trim().replace(/\/+$/, ""),
    ...(username ? { username } : {}),
    token: conexao.token,
  };

  let response: Response;
  try {
    response = await fetch(`${baseUrl}/integrations/git-provider`, {
      method: "POST",
      headers: { Authorization: `Bearer ${session.idToken}`, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Não foi possível conectar ao backend. Verifique sua conexão.");
  }

  if (!response.ok) {
    throw new ApiError(response.status, await describeHttpError(response));
  }
}

/** Prefers the backend's `message` (or `error`) field; falls back to a generic text by status. */
async function describeHttpError(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as Record<string, unknown>;
    const message = data["message"] ?? data["error"];
    if (typeof message === "string" && message) return message;
  } catch {
    // Not JSON (e.g. API Gateway HTML error page).
  }
  if (response.status === 401 || response.status === 403) {
    return "Sem permissão para salvar a conexão. Faça login novamente.";
  }
  return `Falha ao enviar os dados da conexão (HTTP ${response.status}).`;
}

// ----------------------------------------------------------------------------
// 5) PROJECTS
// ----------------------------------------------------------------------------
// Projects generated by the portal and their publication state. Returns mock
// data until a projects endpoint exists — then swap the body for a fetch.
// ----------------------------------------------------------------------------

/** Where the project currently lives. */
export type StatusProjeto = "local" | "publicando" | "producao";

/** Synchronization state between the portal and the Git repository. */
export type StatusGit = "nao_sincronizado" | "sincronizando" | "sincronizado";

export interface Projeto {
  id: string;
  nome: string;
  status: StatusProjeto;
  /** `owner/name` in the provider; null while the project only exists in the portal. */
  repositorio: string | null;
  git: StatusGit;
  /** Provider that hosts the repository; null while there is none. */
  provider: ProvedorGit | null;
}

export async function listarProjetos(): Promise<Projeto[]> {
  return [
    {
      id: "prj-001",
      nome: "API de Pedidos",
      status: "producao",
      repositorio: "empresa/api-pedidos",
      git: "sincronizado",
      provider: "github",
    },
    {
      id: "prj-002",
      nome: "Processador de Webhooks",
      status: "publicando",
      repositorio: "empresa/webhooks-processor",
      git: "sincronizando",
      provider: "gitlab",
    },
    {
      id: "prj-003",
      nome: "Chat Backend",
      status: "local",
      repositorio: null,
      git: "nao_sincronizado",
      provider: null,
    },
    {
      id: "prj-004",
      nome: "Relatórios Financeiros",
      status: "producao",
      repositorio: "financeiro/relatorios-etl",
      git: "nao_sincronizado",
      provider: "gitlab",
    },
    {
      id: "prj-005",
      nome: "Notificações Push",
      status: "local",
      repositorio: "empresa/notificacoes-push",
      git: "sincronizado",
      provider: "github",
    },
  ];
}
