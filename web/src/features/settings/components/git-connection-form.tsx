import { Loader2, Send } from "lucide-react";
import { useState, type FormEvent } from "react";

import { PasswordInput } from "@/components/password-input";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import type { ProvedorGit } from "@/lib/infra-api";

import { GIT_PROVIDERS } from "../constants";
import { useGitConnection } from "../hooks/use-git-connection";
import { StatusAlert } from "./status-alert";

const PROVIDER_IDS = Object.keys(GIT_PROVIDERS) as ProvedorGit[];

function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:";
  } catch {
    return false;
  }
}

/** Form that hands the GitHub/GitLab connection data to the backend. */
export function GitConnectionForm() {
  const { status, submitting, submit, fail, reset } = useGitConnection();
  const [provider, setProvider] = useState<ProvedorGit>("github");
  const [serverUrl, setServerUrl] = useState(GIT_PROVIDERS.github.defaultServerUrl);
  const [username, setUsername] = useState("");
  const [token, setToken] = useState("");

  const disabled = submitting;
  const canSubmit = !disabled && serverUrl.trim() !== "" && token.trim() !== "";

  function handleProviderChange(next: ProvedorGit) {
    // Keep a custom (self-hosted) URL; only swap the default one.
    if (serverUrl.trim() === GIT_PROVIDERS[provider].defaultServerUrl) {
      setServerUrl(GIT_PROVIDERS[next].defaultServerUrl);
    }
    setProvider(next);
    reset();
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;

    if (!isHttpUrl(serverUrl.trim())) {
      fail("Informe a URL completa do servidor, por exemplo https://gitlab.minhaempresa.com.");
      return;
    }

    const ok = await submit({ provider, serverUrl: serverUrl.trim(), username, token });
    if (ok) setToken(""); // never keep the secret around longer than needed
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <StatusAlert status={status} />

      <fieldset className="space-y-1.5" disabled={disabled}>
        <legend className="text-sm font-medium leading-none">Provedor</legend>
        <RadioGroup
          value={provider}
          onValueChange={(value) => handleProviderChange(value as ProvedorGit)}
          className="flex gap-6 pt-1"
          aria-label="Provedor"
        >
          {PROVIDER_IDS.map((id) => (
            <div key={id} className="flex items-center gap-2">
              <RadioGroupItem id={`provider-${id}`} value={id} />
              <Label htmlFor={`provider-${id}`} className="cursor-pointer font-normal">
                {GIT_PROVIDERS[id].label}
              </Label>
            </div>
          ))}
        </RadioGroup>
      </fieldset>

      <div className="space-y-1.5">
        <Label htmlFor="git-server-url">URL do servidor</Label>
        <Input
          id="git-server-url"
          type="url"
          inputMode="url"
          autoComplete="off"
          placeholder={GIT_PROVIDERS[provider].defaultServerUrl}
          value={serverUrl}
          onChange={(e) => setServerUrl(e.target.value)}
          disabled={disabled}
          required
        />
        <p className="text-xs text-muted-foreground">
          Altere apenas para GitHub Enterprise ou GitLab self-hosted.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="git-username">Usuário ou organização (opcional)</Label>
        <Input
          id="git-username"
          autoComplete="off"
          placeholder={provider === "github" ? "minha-org" : "meu-grupo"}
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          disabled={disabled}
        />
        <p className="text-xs text-muted-foreground">
          Conta que será dona dos repositórios criados pelo portal.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="git-token">Token de acesso pessoal</Label>
        <PasswordInput
          id="git-token"
          autoComplete="off"
          placeholder={provider === "github" ? "ghp_…" : "glpat-…"}
          value={token}
          onChange={(e) => setToken(e.target.value)}
          disabled={disabled}
          required
        />
        <p className="text-xs text-muted-foreground">{GIT_PROVIDERS[provider].tokenHint}</p>
      </div>

      <Button type="submit" disabled={!canSubmit}>
        {submitting ? <Loader2 className="animate-spin" /> : <Send />}
        {submitting ? "Enviando..." : "Enviar dados de conexão"}
      </Button>
    </form>
  );
}
