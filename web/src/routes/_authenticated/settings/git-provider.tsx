import { createFileRoute } from "@tanstack/react-router";
import { Plug } from "lucide-react";

import { GitConnectionForm } from "@/features/settings";
import { ContentPage } from "@/features/shell";

export const Route = createFileRoute("/_authenticated/settings/git-provider")({
  staticData: { title: "Conexão com provedor Git" },
  head: () => ({
    meta: [
      { title: "Conexão com provedor Git — Arquiteto de Infraestrutura IA" },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: GitProviderPage,
});

/** Settings: hand the GitHub/GitLab connection data to the backend. */
function GitProviderPage() {
  return (
    <ContentPage
      icon={Plug}
      title="Conexão com provedor Git"
      description="Configure o acesso ao GitHub ou GitLab para que o portal possa publicar (push) e integrar os projetos gerados com os seus repositórios."
    >
      <GitConnectionForm />
    </ContentPage>
  );
}
