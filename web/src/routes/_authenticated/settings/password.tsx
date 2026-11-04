import { createFileRoute } from "@tanstack/react-router";
import { KeyRound } from "lucide-react";

import { ChangePasswordForm } from "@/features/settings";
import { ContentPage } from "@/features/shell";

export const Route = createFileRoute("/_authenticated/settings/password")({
  staticData: { title: "Alterar senha" },
  head: () => ({
    meta: [
      { title: "Alterar senha — Arquiteto de Infraestrutura IA" },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: PasswordPage,
});

/** Settings: change the signed-in user's Cognito password. */
function PasswordPage() {
  const { session } = Route.useRouteContext();

  return (
    <ContentPage
      icon={KeyRound}
      title="Alterar senha"
      description="A senha é validada e alterada diretamente no Amazon Cognito."
    >
      <ChangePasswordForm email={session.email} />
    </ContentPage>
  );
}
