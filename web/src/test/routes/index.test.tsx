import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { pageOf, resetRouterMock, routerState } from "@/test/router-mock";
import { makeSession, mockResultado } from "@/test/fixtures";
import { AbortError, type PromptResponse, type SocketStatus } from "@/lib/architect-socket";
import type { ResultadoGeracao } from "@/lib/infra-api";

// Hoisted above the imports, so the helper must be imported inside the factory.
vi.mock("@tanstack/react-router", async (importOriginal) => {
  const { mockReactRouterModule } = await import("@/test/router-mock");
  return mockReactRouterModule(importOriginal as () => Promise<Record<string, unknown>>);
});
vi.mock("mermaid", () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn(async () => ({ svg: "<svg data-testid='diagram' />" })),
  },
}));
vi.mock("@/lib/infra-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/infra-api")>()),
  baixarRepositorioZip: vi.fn(async () => {}),
}));

const socketMock = {
  status: "open" as SocketStatus,
  configError: null as string | null,
  sendPrompt: vi.fn(),
  reconnect: vi.fn(),
};
vi.mock("@/lib/architect-socket-context", () => ({
  useArchitectSocket: () => socketMock,
}));

import { baixarRepositorioZip } from "@/lib/infra-api";
import { Route } from "@/routes/_authenticated/index";

const Index = pageOf(Route);

/** A sendPrompt implementation the test can drive like the server would. */
function deferredPrompt() {
  let resolve!: (r: PromptResponse) => void;
  let reject!: (e: Error) => void;
  let onAccepted: ((id: string) => void) | undefined;
  let signal: AbortSignal | undefined;
  let acceptedId: string | null = null;
  socketMock.sendPrompt.mockImplementation(
    (_prompt: string, options?: { onAccepted?: (id: string) => void; signal?: AbortSignal }) => {
      onAccepted = options?.onAccepted;
      signal = options?.signal;
      return new Promise<PromptResponse>((res, rej) => {
        resolve = res;
        reject = rej;
        signal?.addEventListener("abort", () => rej(new AbortError()), { once: true });
      });
    },
  );
  return {
    accept: (id: string) => {
      acceptedId = id;
      return act(() => onAccepted?.(id));
    },
    /** Resolves with the given result; accepts first (with `id`) if the test did not. */
    resolve: (result: ResultadoGeracao = mockResultado, id?: string) =>
      act(async () => {
        const requestId = id ?? acceptedId ?? "req-auto";
        if (acceptedId === null && id === undefined) onAccepted?.(requestId);
        resolve({ requestId, result });
      }),
    reject: (e: Error) => act(async () => reject(e)),
    get aborted() {
      return signal?.aborted ?? false;
    },
  };
}

const textarea = () => screen.getByPlaceholderText(/Criar uma API simples/);
const generateButton = () =>
  screen.getByRole("button", { name: /Gerar Arquitetura e Terraform|Gerando/ });

beforeEach(() => {
  resetRouterMock();
  routerState.context = { session: makeSession({ email: "ana@empresa.com" }) };
  socketMock.status = "open";
  socketMock.configError = null;
  socketMock.sendPrompt.mockReset();
  socketMock.reconnect.mockReset();
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("prompt submission over the WebSocket", () => {
  it("keeps the button disabled while the textarea is empty", () => {
    render(<Index />);
    expect(generateButton()).toBeDisabled();
  });

  it("blocks the textarea and button while generating, then releases them with the result", async () => {
    const prompt = deferredPrompt();
    render(<Index />);
    const user = userEvent.setup();

    await user.type(textarea(), "Criar API de tarefas");
    await user.click(generateButton());

    expect(socketMock.sendPrompt).toHaveBeenCalledWith(
      "Criar API de tarefas",
      expect.objectContaining({ onAccepted: expect.any(Function) }),
    );
    expect(textarea()).toBeDisabled();
    expect(generateButton()).toBeDisabled();
    expect(screen.getByText("Enviando solicitação...")).toBeInTheDocument();

    await prompt.accept("req-42");
    expect(screen.getByText(/Solicitação aceita/)).toBeInTheDocument();
    expect(screen.getByText(/request_id: req-42/)).toBeInTheDocument();

    await prompt.resolve();
    expect(textarea()).toBeEnabled();
    expect(generateButton()).toBeEnabled();
    expect(screen.getByText("2026-11-02")).toBeInTheDocument();
    expect(screen.getByText("create_task")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Baixar Projeto Gerado (.zip)" }),
    ).toBeInTheDocument();
  });

  it("renders the generated files as tabs and shows the selected one", async () => {
    const prompt = deferredPrompt();
    render(<Index />);
    const user = userEvent.setup();
    await user.type(textarea(), "x");
    await user.click(generateButton());
    await prompt.resolve();

    expect(screen.getByRole("button", { name: "main.tf" })).toBeInTheDocument();
    expect(screen.getByText(/provider "aws"/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "create_task.py" }));
    expect(screen.getByText(/import os/)).toBeInTheDocument();
    expect(screen.getByText("lambda_create/ai/machine.py")).toBeInTheDocument();
  });

  it("goes back to the loading state when another prompt is sent", async () => {
    const prompt = deferredPrompt();
    render(<Index />);
    const user = userEvent.setup();
    await user.type(textarea(), "first");
    await user.click(generateButton());
    await prompt.resolve();
    expect(screen.getByText("2026-11-02")).toBeInTheDocument();

    const second = deferredPrompt();
    await user.clear(textarea());
    await user.type(textarea(), "second");
    await user.click(generateButton());

    expect(screen.queryByText("2026-11-02")).not.toBeInTheDocument();
    expect(screen.getByText("Enviando solicitação...")).toBeInTheDocument();
    expect(textarea()).toBeDisabled();

    await second.resolve({ ...mockResultado, analysis_date: "2027-01-01" });
    expect(screen.getByText("2027-01-01")).toBeInTheDocument();
  });

  it("shows the error and releases the form when generation fails", async () => {
    const prompt = deferredPrompt();
    render(<Index />);
    const user = userEvent.setup();
    await user.type(textarea(), "x");
    await user.click(generateButton());
    await prompt.reject(new Error("Tempo esgotado aguardando a resposta do servidor."));

    expect(
      screen.getByText("Tempo esgotado aguardando a resposta do servidor."),
    ).toBeInTheDocument();
    expect(textarea()).toBeEnabled();
    expect(generateButton()).toBeEnabled();
  });

  it("only shows the result that matches the request_id of the last prompt", async () => {
    const prompt = deferredPrompt();
    render(<Index />);
    const user = userEvent.setup();
    await user.type(textarea(), "x");
    await user.click(generateButton());
    await prompt.accept("req-current");

    // A result for a different (stale) request_id must be ignored.
    await prompt.resolve({ ...mockResultado, analysis_date: "STALE" }, "req-old");
    expect(screen.queryByText("STALE")).not.toBeInTheDocument();
  });

  it("disables generation and explains when the WebSocket is not configured", async () => {
    socketMock.configError = "Configuração ausente: defina VITE_WS_API_ID (veja o arquivo .env).";
    render(<Index />);
    await userEvent.setup().type(textarea(), "x");
    expect(screen.getByText(/VITE_WS_API_ID/)).toBeInTheDocument();
    expect(generateButton()).toBeDisabled();
  });

  it("limits the prompt to 1000 characters", async () => {
    render(<Index />);
    const user = userEvent.setup();
    await user.click(textarea());
    await user.paste("a".repeat(1005));
    expect(textarea()).toHaveValue("a".repeat(1000));
    expect(screen.getByText("1000/1000")).toBeInTheDocument();
  });
});

describe("cancel", () => {
  it("shows a cancel button only while generating", async () => {
    const prompt = deferredPrompt();
    render(<Index />);
    expect(screen.queryByRole("button", { name: "Cancelar" })).not.toBeInTheDocument();

    const user = userEvent.setup();
    await user.type(textarea(), "x");
    await user.click(generateButton());
    expect(screen.getByRole("button", { name: "Cancelar" })).toBeInTheDocument();

    await prompt.resolve();
    expect(screen.queryByRole("button", { name: "Cancelar" })).not.toBeInTheDocument();
  });

  it("aborts the request and releases the form without showing an error", async () => {
    const prompt = deferredPrompt();
    render(<Index />);
    const user = userEvent.setup();
    await user.type(textarea(), "x");
    await user.click(generateButton());
    await prompt.accept("req-1");

    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(prompt.aborted).toBe(true);
    expect(textarea()).toBeEnabled();
    expect(generateButton()).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Cancelar" })).not.toBeInTheDocument();
    expect(screen.queryByText(/cancelad/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Solicitação aceita/)).not.toBeInTheDocument();
  });

  it("ignores the result of a cancelled prompt and shows the one from the next prompt", async () => {
    const first = deferredPrompt();
    render(<Index />);
    const user = userEvent.setup();
    await user.type(textarea(), "first");
    await user.click(generateButton());
    await first.accept("req-1");
    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    const second = deferredPrompt();
    await user.clear(textarea());
    await user.type(textarea(), "second");
    await user.click(generateButton());
    await second.accept("req-2");
    expect(screen.getByText(/request_id: req-2/)).toBeInTheDocument();

    // Late result for the cancelled prompt: never displayed.
    await first.resolve({ ...mockResultado, analysis_date: "OLD" }, "req-1");
    expect(screen.queryByText("OLD")).not.toBeInTheDocument();
    expect(textarea()).toBeDisabled(); // still waiting for req-2

    await second.resolve({ ...mockResultado, analysis_date: "NEW" }, "req-2");
    expect(screen.getByText("NEW")).toBeInTheDocument();
    expect(textarea()).toBeEnabled();
  });
});

describe("download", () => {
  it("downloads the generated project as a zip", async () => {
    const prompt = deferredPrompt();
    render(<Index />);
    const user = userEvent.setup();
    await user.type(textarea(), "x");
    await user.click(generateButton());
    await prompt.resolve();

    const section = screen.getByRole("button", { name: "Baixar Projeto Gerado (.zip)" });
    await user.click(section);
    expect(baixarRepositorioZip).toHaveBeenCalledWith(mockResultado);
    expect(
      within(document.body).queryByText("Baixar Repositório Git Gerado (.zip)"),
    ).not.toBeInTheDocument();
  });
});
