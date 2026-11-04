import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { isRedirect } from "@tanstack/react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { navigateMock, pageOf, resetRouterMock, routerState } from "@/test/router-mock";
import { makeSession } from "@/test/fixtures";
import type { SocketStatus } from "@/lib/architect-socket";

// Hoisted above the imports, so the helper must be imported inside the factory.
vi.mock("@tanstack/react-router", async (importOriginal) => {
  const { mockReactRouterModule } = await import("@/test/router-mock");
  return mockReactRouterModule(importOriginal as () => Promise<Record<string, unknown>>);
});
vi.mock("@/lib/auth/session", () => ({
  ensureValidSession: vi.fn(),
  clearSession: vi.fn(),
  signOut: vi.fn(async () => {}),
}));

const socketMock = {
  status: "open" as SocketStatus,
  configError: null as string | null,
  sendPrompt: vi.fn(),
  reconnect: vi.fn(),
};
let capturedOnSessionExpired: ((error: Error) => void) | undefined;
vi.mock("@/lib/architect-socket-context", () => ({
  useArchitectSocket: () => socketMock,
  ArchitectSocketProvider: ({
    children,
    onSessionExpired,
  }: {
    children: React.ReactNode;
    onSessionExpired?: (error: Error) => void;
  }) => {
    capturedOnSessionExpired = onSessionExpired;
    return <>{children}</>;
  },
}));

import { clearSession, ensureValidSession, signOut } from "@/lib/auth/session";
import { Route } from "@/routes/_authenticated";

type BeforeLoad = (ctx: { location: { href: string } }) => Promise<{ session: unknown }>;
const beforeLoad = Route.options.beforeLoad as unknown as BeforeLoad;
const Layout = pageOf(Route);

beforeEach(() => {
  resetRouterMock();
  routerState.context = { session: makeSession({ email: "ana@empresa.com" }) };
  routerState.matches = [{ staticData: {} }, { staticData: { title: "Novo Projeto" } }];
  socketMock.status = "open";
  socketMock.reconnect.mockReset();
});

describe("_authenticated guard", () => {
  it("is rendered only on the client (session lives in localStorage)", () => {
    expect(Route.options.ssr).toBe(false);
  });

  it("provides the session to child routes when authenticated", async () => {
    const session = makeSession();
    vi.mocked(ensureValidSession).mockResolvedValue(session);
    await expect(beforeLoad({ location: { href: "/" } })).resolves.toEqual({ session });
  });

  it("redirects to /login when there is no valid session", async () => {
    vi.mocked(ensureValidSession).mockResolvedValue(null);
    const thrown = await beforeLoad({ location: { href: "/" } }).catch((e: unknown) => e);
    expect(isRedirect(thrown)).toBe(true);
    expect((thrown as { options: { to: string; search: unknown } }).options).toMatchObject({
      to: "/login",
      search: {},
    });
  });

  it("remembers the requested page so the user returns to it after login", async () => {
    vi.mocked(ensureValidSession).mockResolvedValue(null);
    const thrown = await beforeLoad({ location: { href: "/projetos/7?tab=code" } }).catch(
      (e: unknown) => e,
    );
    expect((thrown as { options: { search: unknown } }).options.search).toEqual({
      redirect: "/projetos/7?tab=code",
    });
  });
});

describe("_authenticated layout", () => {
  it("drops the session and returns to the login page when the WebSocket reports an expired session", () => {
    render(<Layout />);
    expect(capturedOnSessionExpired).toBeTypeOf("function");

    capturedOnSessionExpired?.(new Error("Sessão expirada."));

    expect(clearSession).toHaveBeenCalled();
    expect(navigateMock).toHaveBeenCalledWith({ to: "/login", replace: true });
  });
});

describe("sidebar", () => {
  const nav = () => within(screen.getByRole("navigation", { name: "Navegação principal" }));

  it("shows the brand and links to every page, grouped", () => {
    render(<Layout />);
    const sidebar = nav();

    expect(screen.getByRole("link", { name: /Arquiteto de Infraestrutura IA/ })).toHaveAttribute(
      "href",
      "/",
    );
    const links = sidebar.getAllByRole("link").map((a) => [a.textContent, a.getAttribute("href")]);
    expect(links).toEqual([
      ["Novo Projeto", "/"],
      ["Projetos", "/projects"],
      ["Repositórios", "/repositories"],
      ["Conexão com provedor Git", "/settings/git-provider"],
      ["Alterar senha", "/settings/password"],
    ]);
    expect(sidebar.getByText("Gerenciar")).toBeInTheDocument();
    expect(sidebar.getByText("Configurações")).toBeInTheDocument();
  });

  it("highlights the link of the current page", () => {
    routerState.pathname = "/settings/password";
    render(<Layout />);
    const sidebar = nav();

    expect(sidebar.getByRole("link", { name: /Alterar senha/ })).toHaveAttribute(
      "data-active",
      "true",
    );
    expect(sidebar.getByRole("link", { name: /Novo Projeto/ })).toHaveAttribute(
      "data-active",
      "false",
    );
  });

  it("can be collapsed and expanded from the header", async () => {
    render(<Layout />);
    const user = userEvent.setup();
    const sidebar = () => document.querySelector('[data-side="left"]') as HTMLElement;
    expect(sidebar()).toHaveAttribute("data-state", "expanded");

    await user.click(screen.getByRole("button", { name: "Alternar menu lateral" }));
    expect(sidebar()).toHaveAttribute("data-state", "collapsed");

    await user.click(screen.getByRole("button", { name: "Alternar menu lateral" }));
    expect(sidebar()).toHaveAttribute("data-state", "expanded");
  });

  it("signs out from the footer and goes back to the login page", async () => {
    render(<Layout />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Sair" }));

    expect(signOut).toHaveBeenCalled();
    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith({ to: "/login", replace: true }));
  });
});

describe("header", () => {
  it("shows the title of the deepest matched route", () => {
    routerState.matches = [
      { staticData: {} },
      { staticData: { title: "Pai" } },
      { staticData: { title: "Projetos" } },
    ];
    render(<Layout />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Projetos");
  });

  it("shows only the connection status and the signed-in e-mail (no menu)", () => {
    render(<Layout />);
    const header = within(screen.getByRole("banner"));
    expect(header.getByText("Conectado")).toBeInTheDocument();
    expect(header.getByText("ana@empresa.com")).toBeInTheDocument();
    expect(header.queryByRole("button", { name: /Menu do usuário|Sair/ })).not.toBeInTheDocument();
  });

  it("offers to reconnect when the socket is down", async () => {
    socketMock.status = "closed";
    render(<Layout />);
    await userEvent.setup().click(screen.getByRole("button", { name: /Desconectado/ }));
    expect(socketMock.reconnect).toHaveBeenCalled();
  });
});
