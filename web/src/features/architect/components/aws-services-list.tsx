import type { ServicoAws } from "@/lib/infra-api";

export function AwsServicesList({ services }: { services: ServicoAws[] }) {
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Serviços AWS
      </h3>
      <ul className="mt-2 space-y-1 text-sm text-card-foreground">
        {services.map((s) => (
          <li key={s.resource_name} className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
            <span>
              <strong>{s.resource_name}</strong>{" "}
              <span className="text-muted-foreground">({s.service})</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
