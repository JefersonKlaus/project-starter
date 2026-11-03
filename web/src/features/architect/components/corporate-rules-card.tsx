import { CheckCircle2, Loader2, ShieldCheck } from "lucide-react";

import type { RegraCorporativa } from "@/lib/infra-api";

/** Lists the corporate rules (RAG) applied to every generation. */
export function CorporateRulesCard({
  rules,
  loading,
}: {
  rules: RegraCorporativa[];
  loading: boolean;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold uppercase tracking-wide text-card-foreground">
          Regras Corporativas Aplicadas{" "}
          <span className="text-muted-foreground">(RAG Codificado)</span>
        </h2>
      </div>
      <div className="mt-4 space-y-3">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Carregando regras...
          </div>
        ) : (
          rules.map((rule) => (
            <div key={rule.descricao} className="flex items-center gap-2 text-sm">
              <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-500" />
              <span className="text-card-foreground">{rule.descricao}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
