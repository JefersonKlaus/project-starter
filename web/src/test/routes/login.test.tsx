import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { isRedirect } from "@tanstack/react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { navigateMock, pageOf, resetRouterMock, routerState } from "@/test/router-mock";
import { makeSession } from "@/test/fixtures";
import type { NewPasswordChallenge } from "@/lib/auth/cognito";

// Hoisted above the imports, so the helper must be imported inside the factory.
vi.mock("@tanstack/react-router", async (importOriginal) => {
  const { mockReactRouterModule } = await import("@/test/router-mock");
  return mockReactRouterModule(importOriginal as () => Promise<Record<string, unknown>>);
});
vi.mock("@/lib/auth/cognito", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/auth/cognito")>()),
  signIn: vi.fn(),
  completeNewPassword: vi.fn(),
}));
vi.mock("@/lib/auth/session", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/auth/session")>()),
  ensureValidSession: vi.fn(),
  saveSession: vi.fn(),
}));

import { CognitoError, completeNewPassword, signIn } from "@/lib/auth/cognito";
import { ensureValidSession, saveSession } from "@/lib/auth/session";
import { Route } from "@/routes/login";

const LoginPage = pageOf(Route);

const challenge: NewPasswordChallenge = {
  kind: "NEW_PASSWORD_REQUIRED",
  session: "challenge-session",
  username: "uuid-123",
  email: "novo@empresa.com",
  requiredAttributes: [],
};

beforeEach(() => {
  resetRouterMock();
  vi.mocked(ensureValidSession).mockResolvedValue(null);
});

afterEach(() => {
  vi.clearAllMocks();
});

async function fillCredentials(email = "ana@empresa.com", password = "Secret123!") {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("E-mail"), email);
  await user.type(screen.getByLabelText("Senha"), password);
  return user;
}

describe("route guard (beforeLoad)", () => {
  const beforeLoad = Route.options.beforeLoad as (ctx: {
    search: { redirect?: string };
  }) => Promise<void>;

  it("lets unauthenticated users see the page", async () => {
    await expect(beforeLoad({ search: {} })).resolves.toBeUndefined();
  });

  it("redirects authenticated users away from the login page", async () => {
    vi.mocked(ensureValidSession).mockResolvedValue(makeSession());
    const thrown = await beforeLoad({ search: { redirect: "/relatorios" } }).catch(
      (e: unknown) => e,
    );
    expect(isRedirect(thrown)).toBe(true);
    expect((thrown as { options: { to: string } }).options.to).toBe("/relatorios");
  });

  it("ignores external redirect targets (open redirect protection)", async () => {
    vi.mocked(ensureValidSession).mockResolvedValue(makeSession());
    const thrown = await beforeLoad({ search: { redirect: "https://evil.example" } }).catch(
      (e: unknown) => e,
    );
    expect((thrown as { options: { to: string } }).options.to).toBe("/");
    const thrown2 = await beforeLoad({ search: { redirect: "//evil.example" } }).catch(
      (e: unknown) => e,
    );
    expect((thrown2 as { options: { to: string } }).options.to).toBe("/");
  });

  it("only accepts a string `redirect` search param", () => {
    const validate = Route.options.validateSearch as (s: Record<string, unknown>) => {
      redirect?: string;
    };
    expect(validate({ redirect: "/x" })).toEqual({ redirect: "/x" });
    expect(validate({ redirect: 42 })).toEqual({});
    expect(validate({})).toEqual({});
  });
});

describe("step 1 — credentials", () => {
  it("renders the login form with the submit button disabled until filled", () => {
    render(<LoginPage />);
    expect(screen.getByRole("heading", { name: "Entrar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Entrar" })).toBeDisabled();
  });

  it("signs in, stores the session and navigates home", async () => {
    const session = makeSession();
    vi.mocked(signIn).mockResolvedValue({ kind: "SUCCESS", session });
    render(<LoginPage />);

    const user = await fillCredentials();
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(signIn).toHaveBeenCalledWith("ana@empresa.com", "Secret123!");
    await waitFor(() => expect(saveSession).toHaveBeenCalledWith(session));
    expect(navigateMock).toHaveBeenCalledWith({ to: "/", replace: true });
  });

  it("returns to the originally requested page after login", async () => {
    routerState.search = { redirect: "/projetos/1" };
    vi.mocked(signIn).mockResolvedValue({ kind: "SUCCESS", session: makeSession() });
    render(<LoginPage />);

    const user = await fillCredentials();
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    await waitFor(() =>
      expect(navigateMock).toHaveBeenCalledWith({ to: "/projetos/1", replace: true }),
    );
  });

  it("shows a friendly error message on wrong credentials", async () => {
    vi.mocked(signIn).mockRejectedValue(
      new CognitoError("NotAuthorizedException", "Incorrect username or password."),
    );
    render(<LoginPage />);

    const user = await fillCredentials();
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("E-mail ou senha incorretos.");
    expect(saveSession).not.toHaveBeenCalled();
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it("toggles password visibility", async () => {
    render(<LoginPage />);
    const user = userEvent.setup();
    const password = screen.getByLabelText("Senha");
    expect(password).toHaveAttribute("type", "password");
    await user.click(screen.getByRole("button", { name: "Mostrar senha" }));
    expect(password).toHaveAttribute("type", "text");
  });
});

describe("step 2 — NEW_PASSWORD_REQUIRED", () => {
  async function reachStepTwo(c: NewPasswordChallenge = challenge) {
    vi.mocked(signIn).mockResolvedValue(c);
    render(<LoginPage />);
    const user = await fillCredentials(c.email, "Temp123!");
    await user.click(screen.getByRole("button", { name: "Entrar" }));
    await screen.findByRole("heading", { name: "Definir nova senha" });
    return user;
  }

  it("switches to the new-password screen when Cognito asks for it", async () => {
    await reachStepTwo();
    expect(screen.getByText(/primeiro acesso/)).toHaveTextContent("novo@empresa.com");
    expect(screen.getByLabelText("Nova senha")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirmar nova senha")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Salvar senha e entrar" })).toBeDisabled();
  });

  it("completes the challenge, stores the session and navigates home", async () => {
    const session = makeSession({ email: "novo@empresa.com" });
    vi.mocked(completeNewPassword).mockResolvedValue(session);
    const user = await reachStepTwo();

    await user.type(screen.getByLabelText("Nova senha"), "NewSecret123!");
    await user.type(screen.getByLabelText("Confirmar nova senha"), "NewSecret123!");
    await user.click(screen.getByRole("button", { name: "Salvar senha e entrar" }));

    expect(completeNewPassword).toHaveBeenCalledWith(challenge, "NewSecret123!", {});
    await waitFor(() => expect(saveSession).toHaveBeenCalledWith(session));
    expect(navigateMock).toHaveBeenCalledWith({ to: "/", replace: true });
  });

  it("validates that both passwords match before calling Cognito", async () => {
    const user = await reachStepTwo();
    await user.type(screen.getByLabelText("Nova senha"), "NewSecret123!");
    await user.type(screen.getByLabelText("Confirmar nova senha"), "Different123!");
    await user.click(screen.getByRole("button", { name: "Salvar senha e entrar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("As senhas não coincidem.");
    expect(completeNewPassword).not.toHaveBeenCalled();
  });

  it("asks for required attributes and sends them with the new password", async () => {
    vi.mocked(completeNewPassword).mockResolvedValue(makeSession());
    const user = await reachStepTwo({ ...challenge, requiredAttributes: ["name"] });

    const submit = screen.getByRole("button", { name: "Salvar senha e entrar" });
    await user.type(screen.getByLabelText("Nova senha"), "NewSecret123!");
    await user.type(screen.getByLabelText("Confirmar nova senha"), "NewSecret123!");
    expect(submit).toBeDisabled(); // name still missing

    await user.type(screen.getByLabelText("Nome completo"), "  Novo Usuário ");
    await user.click(submit);

    expect(completeNewPassword).toHaveBeenCalledWith(
      expect.objectContaining({ requiredAttributes: ["name"] }),
      "NewSecret123!",
      { name: "Novo Usuário" },
    );
  });

  it("shows Cognito password-policy errors", async () => {
    vi.mocked(completeNewPassword).mockRejectedValue(
      new CognitoError("InvalidPasswordException", "Password did not conform with policy"),
    );
    const user = await reachStepTwo();
    await user.type(screen.getByLabelText("Nova senha"), "NewSecret123!");
    await user.type(screen.getByLabelText("Confirmar nova senha"), "NewSecret123!");
    await user.click(screen.getByRole("button", { name: "Salvar senha e entrar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/política/);
  });

  it("can go back to the credentials step", async () => {
    const user = await reachStepTwo();
    await user.click(screen.getByRole("button", { name: "Voltar para o login" }));
    expect(screen.getByRole("heading", { name: "Entrar" })).toBeInTheDocument();
  });
});
