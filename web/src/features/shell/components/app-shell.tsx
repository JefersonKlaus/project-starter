import { useMatches } from "@tanstack/react-router";
import type { CSSProperties, ReactNode } from "react";

import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { useArchitectSocket } from "@/lib/architect-socket-context";

import { AppHeader } from "./app-header";
import { AppSidebar } from "./app-sidebar";

export interface AppShellProps {
  email: string;
  children: ReactNode;
}

/** Wide enough for the full brand name; the icon-only width keeps the primitive's default. */
const SIDEBAR_STYLE = { "--sidebar-width": "18rem" } as CSSProperties;

/** Chrome shared by every authenticated page: sidebar + header around the page content. */
export function AppShell({ email, children }: AppShellProps) {
  const socket = useArchitectSocket();
  // Deepest matched route that declares a title wins.
  const title = useMatches({
    select: (matches) =>
      matches
        .map((match) => match.staticData.title)
        .filter(Boolean)
        .at(-1),
  });

  return (
    <SidebarProvider style={SIDEBAR_STYLE}>
      <AppSidebar />
      <SidebarInset>
        <AppHeader
          title={title}
          email={email}
          connectionStatus={socket.status}
          onReconnect={socket.reconnect}
        />
        {children}
      </SidebarInset>
    </SidebarProvider>
  );
}
