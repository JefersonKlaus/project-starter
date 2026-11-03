import { CloudCog, Loader2, LogOut, UserRound } from "lucide-react";

import { ConnectionStatus } from "./connection-status";
import { useSignOut } from "@/hooks/use-sign-out";
import type { SocketStatus } from "@/lib/architect-socket";
import { cn } from "@/lib/utils";

export interface AppHeaderProps {
  email: string;
  connectionStatus: SocketStatus;
  onReconnect: () => void;
}

/** Brand, connection indicator, signed-in user and sign-out. */
export function AppHeader({ email, connectionStatus, onReconnect }: AppHeaderProps) {
  const { signingOut, signOut } = useSignOut();

  return (
    <header className="border-b border-border">
      <div className="mx-auto flex max-w-7xl items-center gap-3 px-6 py-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary">
          <CloudCog className="h-5 w-5 text-primary-foreground" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-foreground">
            Arquiteto de Infraestrutura IA
          </h1>
          <p className="text-xs text-muted-foreground">
            MVP — AWS Serverless · Terraform · Regras corporativas (RAG)
          </p>
        </div>

        <div className="ml-auto flex items-center gap-4">
          <ConnectionStatus status={connectionStatus} onReconnect={onReconnect} />
          <span
            className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:flex"
            title={email}
          >
            <UserRound className="h-3.5 w-3.5" />
            <span className="max-w-[220px] truncate">{email}</span>
          </span>
          <button
            onClick={signOut}
            disabled={signingOut}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-xs font-medium text-foreground transition hover:bg-accent",
              "disabled:cursor-not-allowed disabled:opacity-50",
            )}
          >
            {signingOut ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <LogOut className="h-3.5 w-3.5" />
            )}
            Sair
          </button>
        </div>
      </div>
    </header>
  );
}
