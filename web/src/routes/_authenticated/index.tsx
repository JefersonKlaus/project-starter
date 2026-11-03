import { createFileRoute } from "@tanstack/react-router";
import { useRef, useState } from "react";

import {
  AppHeader,
  CorporateRulesCard,
  GenerationResultCard,
  PromptForm,
  useCorporateRules,
  useGeneration,
} from "@/features/architect";
import { useArchitectSocket } from "@/lib/architect-socket-context";

export const Route = createFileRoute("/_authenticated/")({
  head: () => ({
    meta: [
      { title: "Arquiteto de Infraestrutura IA" },
      {
        name: "description",
        content:
          "Descreva seu problema de infraestrutura AWS serverless e gere a arquitetura com Terraform, aplicando regras corporativas automaticamente.",
      },
      { property: "og:title", content: "Arquiteto de Infraestrutura IA" },
      {
        property: "og:description",
        content:
          "Gere arquiteturas AWS serverless e código Terraform com regras corporativas aplicadas.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: ArchitectPage,
});

/** Home page: prompt on the left, generation result on the right. */
function ArchitectPage() {
  const { session } = Route.useRouteContext();
  const socket = useArchitectSocket();
  const [prompt, setPrompt] = useState("");
  const resultRef = useRef<HTMLElement>(null);

  const { rules, loading: loadingRules } = useCorporateRules();
  const generation = useGeneration({
    onResult: () => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
  });

  return (
    <div className="min-h-screen bg-background">
      <AppHeader
        email={session.email}
        connectionStatus={socket.status}
        onReconnect={socket.reconnect}
      />

      <main className="mx-auto grid max-w-7xl gap-6 px-6 py-8 lg:grid-cols-[1fr_1.2fr]">
        <section className="space-y-6">
          <PromptForm
            value={prompt}
            onChange={setPrompt}
            onSubmit={() => void generation.generate(prompt)}
            onCancel={generation.cancel}
            isGenerating={generation.isGenerating}
            error={generation.error}
            configError={socket.configError}
          />
          <CorporateRulesCard rules={rules} loading={loadingRules} />
        </section>

        <GenerationResultCard ref={resultRef} result={generation.result} phase={generation.phase} />
      </main>
    </div>
  );
}
