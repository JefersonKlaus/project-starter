import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { AlertCircle, ArrowLeft, CloudCog, KeyRound, Loader2, LogIn } from "lucide-react";

import { PasswordInput } from "@/components/password-input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  completeNewPassword,
  describeAuthError,
  signIn,
  type NewPasswordChallenge,
} from "@/lib/auth/cognito";
import { ensureValidSession, saveSession, type AuthSession } from "@/lib/auth/session";

// Cognito's minimum policy. The real User Pool policy is enforced server-side
// (InvalidPasswordException) — this only avoids a pointless network round-trip.
const MIN_PASSWORD_LENGTH = 8;

/** Only accepts internal relative paths, preventing open redirects. */
function safeRedirect(value: unknown): string {
  return typeof value === "string" && value.startsWith("/") && !value.startsWith("//")
    ? value
    : "/";
}

/** User-facing labels for required User Pool attributes. */
const ATTRIBUTE_LABELS: Record<string, string> = {
  name: "Nome completo",
  given_name: "Nome",
  family_name: "Sobrenome",
  phone_number: "Telefone (ex.: +5511999999999)",
  preferred_username: "Nome de usuário",
};

export const Route = createFileRoute("/login")({
  // The session lives in the browser (localStorage); nothing here makes sense on the server.
  ssr: false,
  validateSearch: (search: Record<string, unknown>): { redirect?: string } =>
    typeof search["redirect"] === "string" ? { redirect: search["redirect"] } : {},
  beforeLoad: async ({ search }) => {
    // An already-authenticated user does not need to see the login screen.
    const session = await ensureValidSession();
    if (session) throw redirect({ to: safeRedirect(search.redirect) });
  },
  head: () => ({
    meta: [
      { title: "Entrar — Arquiteto de Infraestrutura IA" },
      { name: "description", content: "Acesse o portal com sua conta corporativa." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: LoginPage,
});

type Step = { name: "credentials" } | { name: "new-password"; challenge: NewPasswordChallenge };

function LoginPage() {
  const navigate = useNavigate();
  const { redirect: redirectTo } = Route.useSearch();
  const [step, setStep] = useState<Step>({ name: "credentials" });

  async function finishLogin(session: AuthSession) {
    saveSession(session);
    await navigate({ to: safeRedirect(redirectTo), replace: true });
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 px-4 py-10">
      <div className="w-full max-w-md">
        {/* Brand */}
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary shadow-sm">
            <CloudCog className="h-6 w-6 text-primary-foreground" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground">
              Arquiteto de Infraestrutura IA
            </h1>
            <p className="text-xs text-muted-foreground">
              MVP — AWS Serverless · Terraform · Regras corporativas (RAG)
            </p>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
          {step.name === "credentials" ? (
            <CredentialsStep
              onSuccess={finishLogin}
              onNewPasswordRequired={(challenge) => setStep({ name: "new-password", challenge })}
            />
          ) : (
            <NewPasswordStep
              challenge={step.challenge}
              onSuccess={finishLogin}
              onBack={() => setStep({ name: "credentials" })}
            />
          )}
        </div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Autenticação via Amazon Cognito. Acesso restrito a usuários cadastrados.
        </p>
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------------
// Step 1 — e-mail and password
// ----------------------------------------------------------------------------

function CredentialsStep({
  onSuccess,
  onNewPasswordRequired,
}: {
  onSuccess: (session: AuthSession) => Promise<void>;
  onNewPasswordRequired: (challenge: NewPasswordChallenge) => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      const result = await signIn(email, password);
      if (result.kind === "NEW_PASSWORD_REQUIRED") {
        onNewPasswordRequired(result);
        return;
      }
      await onSuccess(result.session);
    } catch (err) {
      setError(describeAuthError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5" noValidate>
      <div>
        <h2 className="text-lg font-semibold text-card-foreground">Entrar</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Use seu e-mail corporativo e senha para acessar o portal.
        </p>
      </div>

      {error && <ErrorAlert message={error} />}

      <div className="space-y-2">
        <Label htmlFor="email">E-mail</Label>
        <Input
          id="email"
          type="email"
          autoComplete="username"
          inputMode="email"
          placeholder="voce@empresa.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={submitting}
          required
          autoFocus
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="password">Senha</Label>
        <PasswordInput
          id="password"
          autoComplete="current-password"
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={submitting}
          required
        />
      </div>

      <Button type="submit" className="w-full" disabled={submitting || !email.trim() || !password}>
        {submitting ? <Loader2 className="animate-spin" /> : <LogIn />}
        {submitting ? "Entrando..." : "Entrar"}
      </Button>
    </form>
  );
}

// ----------------------------------------------------------------------------
// Step 2 — NEW_PASSWORD_REQUIRED
// ----------------------------------------------------------------------------

function NewPasswordStep({
  challenge,
  onSuccess,
  onBack,
}: {
  challenge: NewPasswordChallenge;
  onSuccess: (session: AuthSession) => Promise<void>;
  onBack: () => void;
}) {
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [attributes, setAttributes] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const missingAttribute = challenge.requiredAttributes.some((name) => !attributes[name]?.trim());
  const canSubmit =
    newPassword.length >= MIN_PASSWORD_LENGTH &&
    confirmPassword.length > 0 &&
    !missingAttribute &&
    !submitting;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;
    setError(null);

    if (newPassword !== confirmPassword) {
      setError("As senhas não coincidem.");
      return;
    }

    setSubmitting(true);
    try {
      const trimmedAttributes = Object.fromEntries(
        Object.entries(attributes).map(([k, v]) => [k, v.trim()]),
      );
      const session = await completeNewPassword(challenge, newPassword, trimmedAttributes);
      await onSuccess(session);
    } catch (err) {
      setError(describeAuthError(err));
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5" noValidate>
      <div>
        <div className="flex items-center gap-2">
          <KeyRound className="h-4 w-4 text-primary" />
          <h2 className="text-lg font-semibold text-card-foreground">Definir nova senha</h2>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Este é o seu primeiro acesso com <strong>{challenge.email}</strong>. Por segurança,
          escolha uma nova senha para continuar.
        </p>
      </div>

      {error && <ErrorAlert message={error} />}

      {/* The browser uses this hidden field to associate the new password with the e-mail. */}
      <input type="hidden" name="username" autoComplete="username" value={challenge.email} />

      {challenge.requiredAttributes.map((name) => (
        <div key={name} className="space-y-2">
          <Label htmlFor={`attr-${name}`}>{ATTRIBUTE_LABELS[name] ?? name}</Label>
          <Input
            id={`attr-${name}`}
            type={name === "phone_number" ? "tel" : "text"}
            value={attributes[name] ?? ""}
            onChange={(e) => setAttributes((prev) => ({ ...prev, [name]: e.target.value }))}
            disabled={submitting}
            required
          />
        </div>
      ))}

      <div className="space-y-2">
        <Label htmlFor="new-password">Nova senha</Label>
        <PasswordInput
          id="new-password"
          autoComplete="new-password"
          placeholder="••••••••"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          disabled={submitting}
          required
          autoFocus={challenge.requiredAttributes.length === 0}
        />
        <p className="text-xs text-muted-foreground">
          Mínimo de {MIN_PASSWORD_LENGTH} caracteres. A política do User Pool pode exigir
          maiúsculas, minúsculas, números e símbolos.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="confirm-password">Confirmar nova senha</Label>
        <PasswordInput
          id="confirm-password"
          autoComplete="new-password"
          placeholder="••••••••"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          disabled={submitting}
          required
        />
      </div>

      <Button type="submit" className="w-full" disabled={!canSubmit}>
        {submitting ? <Loader2 className="animate-spin" /> : <KeyRound />}
        {submitting ? "Salvando..." : "Salvar senha e entrar"}
      </Button>

      <Button
        type="button"
        variant="ghost"
        className="w-full"
        onClick={onBack}
        disabled={submitting}
      >
        <ArrowLeft />
        Voltar para o login
      </Button>
    </form>
  );
}

// ----------------------------------------------------------------------------
// Helper components
// ----------------------------------------------------------------------------

function ErrorAlert({ message }: { message: string }) {
  return (
    <Alert variant="destructive">
      <AlertCircle className="h-4 w-4" />
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}
