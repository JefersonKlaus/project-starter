import { CalendarDays, Database, Download, Loader2, Workflow } from "lucide-react";
import type { Ref } from "react";

import { AwsServicesList } from "./aws-services-list";
import { GeneratedCodeViewer } from "./generated-code-viewer";
import { GenerationPlaceholder } from "./generation-placeholder";
import { MermaidDiagram } from "./mermaid-diagram";
import { RagReferences } from "./rag-references";
import { useGeneratedFiles } from "../hooks/use-generated-files";
import type { GenerationPhase } from "../hooks/use-generation";
import { useProjectDownload } from "../hooks/use-project-download";
import type { ResultadoGeracao } from "@/lib/infra-api";
import { cn } from "@/lib/utils";

export interface GenerationResultCardProps {
  result: ResultadoGeracao | null;
  phase: GenerationPhase | null;
  /** Attached to the section so the page can scroll to it when a result arrives. */
  ref?: Ref<HTMLElement>;
}

/** Right column: services, diagram, generated code, RAG references and download. */
export function GenerationResultCard({ result, phase, ref }: GenerationResultCardProps) {
  const { files, selected, select } = useGeneratedFiles(result);
  const { downloading, download } = useProjectDownload();

  return (
    <section ref={ref} className="scroll-mt-6">
      <div className="flex h-full flex-col rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold uppercase tracking-wide text-card-foreground">
              Resultado da Geração
            </h2>
          </div>
          {result && (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <CalendarDays className="h-3.5 w-3.5" />
              {result.analysis_date}
            </span>
          )}
        </div>

        {!result ? (
          <GenerationPlaceholder phase={phase} />
        ) : (
          <div className="mt-4 flex flex-1 flex-col gap-5">
            <AwsServicesList services={result.aws_services} />

            <div>
              <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <Workflow className="h-3.5 w-3.5" /> Diagrama da Arquitetura
              </h3>
              <div className="mt-2 overflow-hidden rounded-lg border border-border">
                <MermaidDiagram code={result.mermaid_diagram} />
              </div>
            </div>

            <GeneratedCodeViewer files={files} selected={selected} onSelect={select} />
            <RagReferences references={result.rag_references} />

            <button
              onClick={() => download(result)}
              disabled={downloading}
              className={cn(
                "mt-auto inline-flex w-full items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-semibold uppercase tracking-wide transition",
                "bg-emerald-600 text-white hover:bg-emerald-700",
                "disabled:cursor-not-allowed disabled:opacity-50",
              )}
            >
              {downloading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              {downloading ? "Preparando..." : "Baixar Projeto Gerado (.zip)"}
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
