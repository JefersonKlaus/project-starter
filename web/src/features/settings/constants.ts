import type { ProvedorGit } from "@/lib/infra-api";

/** Cognito's minimum policy; the real User Pool policy is enforced server-side. */
export const MIN_PASSWORD_LENGTH = 8;

export interface GitProviderInfo {
  label: string;
  /** Public SaaS URL, pre-filled and editable for self-hosted/enterprise instances. */
  defaultServerUrl: string;
  /** Where the user creates the token and which scopes it needs. */
  tokenHint: string;
}

export const GIT_PROVIDERS: Record<ProvedorGit, GitProviderInfo> = {
  github: {
    label: "GitHub",
    defaultServerUrl: "https://github.com",
    tokenHint: "Personal access token com escopo repo (Settings → Developer settings).",
  },
  gitlab: {
    label: "GitLab",
    defaultServerUrl: "https://gitlab.com",
    tokenHint:
      "Personal access token com escopos api e write_repository (Preferências → Access Tokens).",
  },
};
