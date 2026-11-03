import { FileCode2, Loader2 } from "lucide-react";

import type { GenerationPhase } from "../hooks/use-generation";

/** Empty / loading state of the result panel. */
export function GenerationPlaceholder({ phase }: { phase: GenerationPhase | null }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 py-16 text-center">
      {phase ? (
        <>
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">
            {phase.name === "processing"
              ? "Solicitação aceita. Gerando arquitetura e código Terraform..."
              : "Enviando solicitação..."}
          </p>
          {phase.name === "processing" && (
            <p className="font-mono text-[11px] text-muted-foreground">
              request_id: {phase.requestId}
            </p>
          )}
        </>
      ) : (
        <>
          <FileCode2 className="h-8 w-8 text-muted-foreground" />
          <p className="max-w-sm text-sm text-muted-foreground">
            Descreva o problema e clique em <strong>Gerar Arquitetura e Terraform</strong> para ver
            os recursos, o diagrama e o código aqui.
          </p>
        </>
      )}
    </div>
  );
}
