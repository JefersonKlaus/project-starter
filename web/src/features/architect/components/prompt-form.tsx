import { Loader2, RefreshCcw, XCircle } from "lucide-react";

import { InlineError } from "./inline-error";
import { PROMPT_MAX_LENGTH } from "../constants";
import { cn } from "@/lib/utils";

export interface PromptFormProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
  isGenerating: boolean;
  /** Error from the last generation attempt. */
  error: string | null;
  /** Configuration problem that prevents any generation (e.g. missing env var). */
  configError: string | null;
}

/** Problem description textarea with the generate / cancel actions. */
export function PromptForm({
  value,
  onChange,
  onSubmit,
  onCancel,
  isGenerating,
  error,
  configError,
}: PromptFormProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-card-foreground">
        Descreva o problema de infraestrutura{" "}
        <span className="text-muted-foreground">(AWS Serverless)</span>
      </h2>
      <div className="relative mt-3">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value.slice(0, PROMPT_MAX_LENGTH))}
          placeholder="Ex.: Criar uma API simples para um backend de chat que recebe uma mensagem via webhook, envia para uma fila SQS para processamento assíncrono e armazena os metadados no DynamoDB. Deve ser serverless."
          rows={6}
          disabled={isGenerating}
          className="w-full resize-none rounded-lg border border-input bg-background p-3 pb-8 text-sm text-foreground outline-none transition focus:border-primary focus:ring-2 focus:ring-ring/30 disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-70"
        />
        <span className="pointer-events-none absolute bottom-2 right-3 text-xs text-muted-foreground">
          {value.length}/{PROMPT_MAX_LENGTH}
        </span>
      </div>

      {configError && <InlineError message={configError} />}
      {error && <InlineError message={error} />}

      <button
        onClick={onSubmit}
        disabled={!value.trim() || isGenerating || !!configError}
        className={cn(
          "mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-semibold uppercase tracking-wide transition",
          "bg-primary text-primary-foreground hover:bg-primary/90",
          "disabled:cursor-not-allowed disabled:opacity-50",
        )}
      >
        {isGenerating ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <RefreshCcw className="h-4 w-4" />
        )}
        {isGenerating ? "Gerando..." : "Gerar Arquitetura e Terraform"}
      </button>

      {isGenerating && (
        <button
          type="button"
          onClick={onCancel}
          className={cn(
            "mt-2 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-input bg-background px-4 py-2.5 text-sm font-semibold uppercase tracking-wide text-foreground transition",
            "hover:border-destructive/50 hover:bg-destructive/5 hover:text-destructive",
          )}
        >
          <XCircle className="h-4 w-4" />
          Cancelar
        </button>
      )}
    </div>
  );
}
