import { useEffect, useState } from "react";

import { buscarRegrasCorporativas, type RegraCorporativa } from "@/lib/infra-api";

/** Loads the corporate rules (RAG) shown in the left panel. */
export function useCorporateRules() {
  const [rules, setRules] = useState<RegraCorporativa[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    buscarRegrasCorporativas()
      .then((r) => {
        if (active) setRules(r);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return { rules, loading };
}
