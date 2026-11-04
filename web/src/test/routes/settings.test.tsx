import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { pageOf, resetRouterMock, routerState } from "@/test/router-mock";
import { makeSession } from "@/test/fixtures";

// Hoisted above the imports, so the helper must be imported inside the factory.
vi.mock("@tanstack/react-router", async (importOriginal) => {
  const { mockReactRouterModule } = await import("@/test/router-mock");
  return mockReactRouterModule(importOriginal as () => Promise<Record<string, unknown>>);
});
vi.mock("@/lib/auth/cognito", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/auth/cognito")>()),
  changePassword: vi.fn(),
}));
vi.mock("@/lib/auth/session", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/auth/session")>()),
  ensureValidSession: vi.fn(),
}));
vi.mock("@/lib/infra-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/infra-api")>()),
  salvarConexaoGit: vi.fn(),
}));

import { isRedirect } from "@tanstack/react-router";

import { changePassword, CognitoError } from "@/lib/auth/cognito";
import { ensureValidSession } from "@/lib/auth/session";
import { ApiError, salvarConexaoGit } from "@/lib/infra-api";
import { Route as GitProviderRoute } from "@/routes/_authenticated/settings/git-provider";
import { Route as SettingsIndexRoute } from "@/routes/_authenticated/settings/index";
import { Route as PasswordRoute } from "@/routes/_authenticated/settings/password";

const GitProviderPage = pageOf(GitProviderRoute);
const PasswordPage = pageOf(PasswordRoute);
const session = makeSession({ email: "ana@empresa.com" });

beforeEach(() => {
  resetRouterMock();
  routerState.context = { session };
  vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com/dev");
  vi.mocked(ensureValidSession).mockResolvedValue(session);
  vi.mocked(salvarConexaoGit).mockResolvedValue(undefined);
  vi.mocked(changePassword).mockResolvedValue(undefined);
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.clearAllMocks();
});

describe("routes", () => {
  it("declare the header titles", () => {
    expect(GitProviderRoute.options.staticData).toEqual({ title: "Conexão com provedor Git" });
    expect(PasswordRoute.options.staticData).toEqual({ title: "Alterar senha" });
  });

  it("render the standard page card with the title and description", () => {
    render(<GitProviderPage />);
    expect(
      screen.getByRole("heading", { level: 2, name: "Conexão com provedor Git" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/publicar \(push\) e integrar/)).toBeInTheDocument();
  });

  it("/settings redirects to the first settings page", () => {
    const beforeLoad = SettingsIndexRoute.options.beforeLoad as () => void;
    const thrown = ((): unknown => {
      try {
        beforeLoad();
        return undefined;
      } catch (e) {
        return e;
      }
    })();
    expect(isRedirect(thrown)).toBe(true);
    expect((thrown as { options: { to: string } }).options.to).toBe("/settings/git-provider");
  });
});

// ----------------------------------------------------------------------------
// Git provider connection
// ----------------------------------------------------------------------------

describe("Git provider connection", () => {
  const form = () => within(document.querySelector("form") as HTMLElement);
  const sendButton = () => form().getByRole("button", { name: /Enviar dados de conexão/ });

  it("defaults to GitHub with its public URL and disables sending until a token is typed", () => {
    render(<GitProviderPage />);
    expect(form().getByRole("radio", { name: "GitHub" })).toBeChecked();
    expect(form().getByLabelText("URL do servidor")).toHaveValue("https://github.com");
    expect(sendButton()).toBeDisabled();
  });

  it("swaps the default URL when the provider changes but keeps a custom one", async () => {
    render(<GitProviderPage />);
    const user = userEvent.setup();
    const url = () => form().getByLabelText("URL do servidor");

    await user.click(form().getByRole("radio", { name: "GitLab" }));
    expect(url()).toHaveValue("https://gitlab.com");

    await user.clear(url());
    await user.type(url(), "https://gitlab.empresa.com");
    await user.click(form().getByRole("radio", { name: "GitHub" }));
    expect(url()).toHaveValue("https://gitlab.empresa.com");
  });

  it("sends the connection data to the backend and clears the token on success", async () => {
    render(<GitProviderPage />);
    const user = userEvent.setup();

    await user.click(form().getByRole("radio", { name: "GitLab" }));
    await user.type(form().getByLabelText("Usuário ou organização (opcional)"), "meu-grupo");
    await user.type(form().getByLabelText("Token de acesso pessoal"), "glpat-abc");
    await user.click(sendButton());

    expect(salvarConexaoGit).toHaveBeenCalledWith({
      provider: "gitlab",
      serverUrl: "https://gitlab.com",
      username: "meu-grupo",
      token: "glpat-abc",
    });
    expect(await form().findByText(/Dados enviados/)).toBeInTheDocument();
    expect(form().getByLabelText("Token de acesso pessoal")).toHaveValue("");
    expect(form().getByLabelText("Usuário ou organização (opcional)")).toHaveValue("meu-grupo");
  });

  it("rejects an invalid server URL without calling the backend", async () => {
    render(<GitProviderPage />);
    const user = userEvent.setup();
    const url = form().getByLabelText("URL do servidor");

    await user.clear(url);
    await user.type(url, "gitlab.empresa.com");
    await user.type(form().getByLabelText("Token de acesso pessoal"), "glpat-abc");
    await user.click(sendButton());

    expect(form().getByRole("alert")).toHaveTextContent(/URL completa/);
    expect(salvarConexaoGit).not.toHaveBeenCalled();
  });

  it("shows the backend error and keeps the form editable", async () => {
    vi.mocked(salvarConexaoGit).mockRejectedValue(new ApiError(422, "Token inválido."));
    render(<GitProviderPage />);
    const user = userEvent.setup();

    await user.type(form().getByLabelText("Token de acesso pessoal"), "ghp_bad");
    await user.click(sendButton());

    expect(await form().findByRole("alert")).toHaveTextContent("Token inválido.");
    expect(form().getByLabelText("Token de acesso pessoal")).toHaveValue("ghp_bad");
    expect(sendButton()).toBeEnabled();
  });
});

// ----------------------------------------------------------------------------
// Change password
// ----------------------------------------------------------------------------

describe("change password", () => {
  const form = () => within(document.querySelector("form") as HTMLElement);
  const saveButton = () => form().getByRole("button", { name: /Alterar senha|Salvando/ });

  async function fill(current: string, next: string, confirm = next) {
    const user = userEvent.setup();
    await user.type(form().getByLabelText("Senha atual"), current);
    await user.type(form().getByLabelText("Nova senha"), next);
    await user.type(form().getByLabelText("Confirmar nova senha"), confirm);
    return user;
  }

  it("keeps the button disabled until the new password reaches the minimum length", async () => {
    render(<PasswordPage />);
    await fill("Current1!", "Short1!");
    expect(saveButton()).toBeDisabled();
  });

  it("validates that both passwords match before calling Cognito", async () => {
    render(<PasswordPage />);
    const user = await fill("Current1!", "NewSecret1!", "Different1!");
    await user.click(saveButton());

    expect(form().getByRole("alert")).toHaveTextContent("As senhas não coincidem.");
    expect(changePassword).not.toHaveBeenCalled();
  });

  it("requires the new password to differ from the current one", async () => {
    render(<PasswordPage />);
    const user = await fill("SamePass1!", "SamePass1!");
    await user.click(saveButton());

    expect(form().getByRole("alert")).toHaveTextContent(/diferente da senha atual/);
    expect(changePassword).not.toHaveBeenCalled();
  });

  it("changes the password with a fresh session and clears the fields", async () => {
    const fresh = makeSession({ accessToken: "fresh-access-token" });
    vi.mocked(ensureValidSession).mockResolvedValue(fresh);
    render(<PasswordPage />);
    const user = await fill("Current1!", "NewSecret1!");
    await user.click(saveButton());

    await waitFor(() =>
      expect(changePassword).toHaveBeenCalledWith(fresh, "Current1!", "NewSecret1!"),
    );
    expect(await form().findByText("Senha alterada com sucesso.")).toBeInTheDocument();
    expect(form().getByLabelText("Senha atual")).toHaveValue("");
    expect(form().getByLabelText("Nova senha")).toHaveValue("");
    expect(form().getByLabelText("Confirmar nova senha")).toHaveValue("");
  });

  it("explains a wrong current password", async () => {
    vi.mocked(changePassword).mockRejectedValue(
      new CognitoError("NotAuthorizedException", "Incorrect username or password."),
    );
    render(<PasswordPage />);
    const user = await fill("Wrong1!", "NewSecret1!");
    await user.click(saveButton());

    expect(await form().findByRole("alert")).toHaveTextContent("Senha atual incorreta.");
    expect(form().getByLabelText("Senha atual")).toHaveValue("Wrong1!");
  });

  it("shows Cognito password-policy errors", async () => {
    vi.mocked(changePassword).mockRejectedValue(
      new CognitoError("InvalidPasswordException", "Password did not conform with policy"),
    );
    render(<PasswordPage />);
    const user = await fill("Current1!", "weakweak");
    await user.click(saveButton());

    expect(await form().findByRole("alert")).toHaveTextContent(/política do sistema/);
  });

  it("asks the user to log in again when the session cannot be refreshed", async () => {
    vi.mocked(ensureValidSession).mockResolvedValue(null);
    render(<PasswordPage />);
    const user = await fill("Current1!", "NewSecret1!");
    await user.click(saveButton());

    expect(await form().findByRole("alert")).toHaveTextContent(/Sessão expirada/);
    expect(changePassword).not.toHaveBeenCalled();
  });
});
