// ============================================================================
// Backend access layer (src/lib/infra-api.ts)
// ----------------------------------------------------------------------------
// THIS IS WHERE THE FRONTEND TALKS TO YOUR BACKEND.
//
// Each function below runs independently and asynchronously.
// ============================================================================

import JSZip from "jszip";

import type { ResultadoGeracao } from "./architect-messages";

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
