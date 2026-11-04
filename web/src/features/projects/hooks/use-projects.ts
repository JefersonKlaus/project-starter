import { useEffect, useState } from "react";

import { listarProjetos, type Projeto } from "@/lib/infra-api";

/** Loads the list of projects shown on the Projetos page. */
export function useProjects() {
  const [projects, setProjects] = useState<Projeto[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    listarProjetos()
      .then((list) => {
        if (active) setProjects(list);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return { projects, loading };
}
