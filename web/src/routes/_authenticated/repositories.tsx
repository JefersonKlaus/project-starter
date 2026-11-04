import { createFileRoute } from "@tanstack/react-router";
import { GitBranch } from "lucide-react";

import { PlaceholderPage } from "@/features/shell";

export const Route = createFileRoute("/_authenticated/repositories")({
  staticData: { title: "Repositórios" },
  head: () => ({
    meta: [
      { title: "Repositórios — Arquiteto de Infraestrutura IA" },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: RepositoriesPage,
});

/** Repositories linked to the account. */
function RepositoriesPage() {
  return (
    <PlaceholderPage
      icon={GitBranch}
      title="Repositórios"
      description="Visualize e gerencie os repositórios vinculados à sua conta."
    />
  );
}
