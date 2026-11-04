import { KeyRound, Loader2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { PasswordInput } from "@/components/password-input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

import { MIN_PASSWORD_LENGTH } from "../constants";
import { useChangePassword } from "../hooks/use-change-password";
import { StatusAlert } from "./status-alert";

export interface ChangePasswordFormProps {
  /** Signed-in user's e-mail (lets the browser's password manager link the new password). */
  email: string;
}

/** Form that changes the signed-in user's Cognito password. */
export function ChangePasswordForm({ email }: ChangePasswordFormProps) {
  const { status, submitting, submit, fail } = useChangePassword();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const canSubmit =
    !submitting &&
    currentPassword.length > 0 &&
    newPassword.length >= MIN_PASSWORD_LENGTH &&
    confirmPassword.length > 0;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;

    if (newPassword !== confirmPassword) {
      fail("As senhas não coincidem.");
      return;
    }
    if (newPassword === currentPassword) {
      fail("A nova senha deve ser diferente da senha atual.");
      return;
    }

    const ok = await submit(currentPassword, newPassword);
    if (ok) {
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <StatusAlert status={status} />

      {/* The browser uses this hidden field to associate the new password with the account. */}
      <input type="hidden" name="username" autoComplete="username" value={email} readOnly />

      <div className="space-y-1.5">
        <Label htmlFor="current-password">Senha atual</Label>
        <PasswordInput
          id="current-password"
          autoComplete="current-password"
          placeholder="••••••••"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          disabled={submitting}
          required
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="new-password">Nova senha</Label>
        <PasswordInput
          id="new-password"
          autoComplete="new-password"
          placeholder="••••••••"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          disabled={submitting}
          required
        />
        <p className="text-xs text-muted-foreground">
          Mínimo de {MIN_PASSWORD_LENGTH} caracteres. A política do User Pool pode exigir
          maiúsculas, minúsculas, números e símbolos.
        </p>
      </div>

      <div className="space-y-1.5">
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

      <Button type="submit" disabled={!canSubmit}>
        {submitting ? <Loader2 className="animate-spin" /> : <KeyRound />}
        {submitting ? "Salvando..." : "Alterar senha"}
      </Button>
    </form>
  );
}
