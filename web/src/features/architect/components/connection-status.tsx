import { Wifi, WifiOff } from "lucide-react";

import type { SocketStatus } from "@/lib/architect-socket";
import { cn } from "@/lib/utils";

const STATUS_INFO: Record<SocketStatus, { label: string; color: string }> = {
  idle: { label: "Aguardando", color: "bg-muted-foreground" },
  connecting: { label: "Conectando...", color: "bg-amber-500" },
  reconnecting: { label: "Reconectando...", color: "bg-amber-500" },
  open: { label: "Conectado", color: "bg-emerald-500" },
  closed: { label: "Desconectado", color: "bg-destructive" },
};

/** WebSocket status indicator; acts as a "reconnect" button when offline. */
export function ConnectionStatus({
  status,
  onReconnect,
}: {
  status: SocketStatus;
  onReconnect: () => void;
}) {
  const { label, color } = STATUS_INFO[status];
  const online = status === "open";
  return (
    <button
      type="button"
      onClick={onReconnect}
      disabled={online || status === "connecting"}
      title={online ? "Conexão WebSocket ativa" : "Clique para reconectar"}
      className="hidden items-center gap-1.5 text-xs text-muted-foreground disabled:cursor-default sm:flex"
    >
      {online ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
      <span className={cn("h-2 w-2 rounded-full", color)} />
      {label}
    </button>
  );
}
