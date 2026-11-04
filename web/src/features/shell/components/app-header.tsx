import { UserRound } from "lucide-react";

import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { ConnectionStatus } from "@/features/architect";
import type { SocketStatus } from "@/lib/architect-socket";

export interface AppHeaderProps {
  /** Title of the current page (from the route's `staticData`). */
  title?: string | undefined;
  email: string;
  connectionStatus: SocketStatus;
  onReconnect: () => void;
}

/** Sidebar toggle, page title, connection indicator and the signed-in user's e-mail. */
export function AppHeader({ title, email, connectionStatus, onReconnect }: AppHeaderProps) {
  return (
    <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center gap-3 border-b border-border bg-background px-4 md:px-6">
      <SidebarTrigger className="-ml-1" aria-label="Alternar menu lateral" />
      <Separator orientation="vertical" className="mr-1 h-4" />
      {title && <h1 className="truncate text-base font-semibold text-foreground">{title}</h1>}

      <div className="ml-auto flex items-center gap-4">
        <ConnectionStatus status={connectionStatus} onReconnect={onReconnect} />
        <span
          className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:flex"
          title={email}
        >
          <UserRound className="h-3.5 w-3.5" />
          <span className="max-w-[220px] truncate">{email}</span>
        </span>
      </div>
    </header>
  );
}
