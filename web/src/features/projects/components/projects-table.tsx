import { Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Projeto } from "@/lib/infra-api";
import { cn } from "@/lib/utils";

import { GIT_STATUS, PROJECT_STATUS, PROVIDER_LABEL } from "../constants";

export interface ProjectsTableProps {
  projects: Projeto[];
  loading: boolean;
}

/** Projects with their publication status and Git synchronization state. */
export function ProjectsTable({ projects, loading }: ProjectsTableProps) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Carregando projetos...
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Nenhum projeto ainda. Gere o primeiro em <strong>Novo Projeto</strong>.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Nome</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Repositório</TableHead>
            <TableHead>Git</TableHead>
            <TableHead>Provider</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {projects.map((project) => {
            const status = PROJECT_STATUS[project.status];
            const git = GIT_STATUS[project.git];
            return (
              <TableRow key={project.id}>
                <TableCell className="font-medium">{project.nome}</TableCell>
                <TableCell>
                  <Badge variant="outline" className={cn("border-transparent", status.className)}>
                    {status.label}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {project.repositorio ?? <span className="text-muted-foreground">—</span>}
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className={cn("border-transparent", git.className)}>
                    {git.label}
                  </Badge>
                </TableCell>
                <TableCell>
                  {project.provider ? (
                    PROVIDER_LABEL[project.provider]
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
