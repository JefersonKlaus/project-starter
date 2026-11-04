import { Link, useLocation } from "@tanstack/react-router";
import {
  CloudCog,
  FolderKanban,
  GitBranch,
  KeyRound,
  Loader2,
  LogOut,
  Plug,
  Sparkles,
} from "lucide-react";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar";
import { useSignOut } from "@/hooks/use-sign-out";

/** Navigation entries grouped as they appear in the sidebar. */
const NAV_GROUPS = [
  {
    label: null,
    items: [{ to: "/", label: "Novo Projeto", icon: Sparkles }],
  },
  {
    label: "Gerenciar",
    items: [
      { to: "/projects", label: "Projetos", icon: FolderKanban },
      { to: "/repositories", label: "Repositórios", icon: GitBranch },
    ],
  },
  // Pinned to the bottom of the sidebar, right above "Sair".
  {
    label: "Configurações",
    pinBottom: true,
    items: [
      { to: "/settings/git-provider", label: "Conexão com provedor Git", icon: Plug },
      { to: "/settings/password", label: "Alterar senha", icon: KeyRound },
    ],
  },
] as const;

/** Brand, main navigation and sign-out; collapses to icons on desktop, becomes a drawer on mobile. */
export function AppSidebar() {
  const pathname = useLocation({ select: (location) => location.pathname });
  const { signingOut, signOut } = useSignOut();

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild tooltip="Arquiteto de Infraestrutura IA">
              <Link to="/">
                <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                  <CloudCog className="size-4" />
                </div>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">Arquiteto de Infraestrutura IA</span>
                  <span className="truncate text-xs text-muted-foreground">
                    MVP — AWS Serverless · Terraform
                  </span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <nav aria-label="Navegação principal" className="flex flex-1 flex-col">
          {NAV_GROUPS.map((group, index) => (
            <SidebarGroup
              key={group.label ?? index}
              className={"pinBottom" in group && group.pinBottom ? "mt-auto" : undefined}
            >
              {group.label && <SidebarGroupLabel>{group.label}</SidebarGroupLabel>}
              <SidebarGroupContent>
                <SidebarMenu>
                  {group.items.map(({ to, label, icon: Icon }) => (
                    <SidebarMenuItem key={to}>
                      <SidebarMenuButton asChild isActive={pathname === to} tooltip={label}>
                        <Link to={to}>
                          <Icon />
                          <span>{label}</span>
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          ))}
        </nav>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton onClick={() => void signOut()} disabled={signingOut} tooltip="Sair">
              {signingOut ? <Loader2 className="animate-spin" /> : <LogOut />}
              <span>Sair</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  );
}
