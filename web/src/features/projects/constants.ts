import type { ProvedorGit, StatusGit, StatusProjeto } from "@/lib/infra-api";

/** Badge label + style for each project status. */
export const PROJECT_STATUS: Record<StatusProjeto, { label: string; className: string }> = {
  local: { label: "Local", className: "bg-muted text-muted-foreground" },
  publicando: { label: "Publicando", className: "bg-amber-100 text-amber-800" },
  producao: { label: "Produção", className: "bg-emerald-100 text-emerald-800" },
};

/** Badge label + style for each Git synchronization state. */
export const GIT_STATUS: Record<StatusGit, { label: string; className: string }> = {
  nao_sincronizado: { label: "Não sincronizado", className: "bg-muted text-muted-foreground" },
  sincronizando: { label: "Sincronizando", className: "bg-sky-100 text-sky-800" },
  sincronizado: { label: "Sincronizado", className: "bg-emerald-100 text-emerald-800" },
};

export const PROVIDER_LABEL: Record<ProvedorGit, string> = {
  github: "GitHub",
  gitlab: "GitLab",
};
