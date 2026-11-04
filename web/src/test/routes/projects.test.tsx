import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { pageOf, resetRouterMock } from "@/test/router-mock";
import type { Projeto } from "@/lib/infra-api";

// Hoisted above the imports, so the helper must be imported inside the factory.
vi.mock("@tanstack/react-router", async (importOriginal) => {
  const { mockReactRouterModule } = await import("@/test/router-mock");
  return mockReactRouterModule(importOriginal as () => Promise<Record<string, unknown>>);
});
vi.mock("@/lib/infra-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/infra-api")>()),
  listarProjetos: vi.fn(),
}));

import { listarProjetos } from "@/lib/infra-api";
import { Route } from "@/routes/_authenticated/projects";

const ProjectsPage = pageOf(Route);

const projetos: Projeto[] = [
  {
    id: "p1",
    nome: "API de Pedidos",
    status: "producao",
    repositorio: "empresa/api-pedidos",
    git: "sincronizado",
    provider: "github",
  },
  {
    id: "p2",
    nome: "Webhooks",
    status: "publicando",
    repositorio: "empresa/webhooks",
    git: "sincronizando",
    provider: "gitlab",
  },
  {
    id: "p3",
    nome: "Chat Backend",
    status: "local",
    repositorio: null,
    git: "nao_sincronizado",
    provider: null,
  },
];

beforeEach(() => {
  resetRouterMock();
  vi.mocked(listarProjetos).mockResolvedValue(projetos);
});

describe("projects page", () => {
  it("declares the header title", () => {
    expect(Route.options.staticData).toEqual({ title: "Projetos" });
  });

  it("shows a loading state and then the table with the expected columns", async () => {
    render(<ProjectsPage />);
    expect(screen.getByText("Carregando projetos...")).toBeInTheDocument();

    const table = await screen.findByRole("table");
    const headers = within(table)
      .getAllByRole("columnheader")
      .map((th) => th.textContent);
    expect(headers).toEqual(["Nome", "Status", "Repositório", "Git", "Provider"]);
    expect(screen.queryByText("Carregando projetos...")).not.toBeInTheDocument();
  });

  it("renders one row per project with human-readable status, git state and provider", async () => {
    render(<ProjectsPage />);
    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row").slice(1); // skip the header row
    const cells = rows.map((row) =>
      within(row)
        .getAllByRole("cell")
        .map((td) => td.textContent),
    );

    expect(cells).toEqual([
      ["API de Pedidos", "Produção", "empresa/api-pedidos", "Sincronizado", "GitHub"],
      ["Webhooks", "Publicando", "empresa/webhooks", "Sincronizando", "GitLab"],
      ["Chat Backend", "Local", "—", "Não sincronizado", "—"],
    ]);
  });

  it("explains how to create the first project when the list is empty", async () => {
    vi.mocked(listarProjetos).mockResolvedValue([]);
    render(<ProjectsPage />);
    expect(await screen.findByText(/Nenhum projeto ainda/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
