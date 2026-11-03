import { useState } from "react";

import { baixarRepositorioZip, type ResultadoGeracao } from "@/lib/infra-api";

/** Builds the .zip of a generation result and triggers the browser download. */
export function useProjectDownload() {
  const [downloading, setDownloading] = useState(false);

  async function download(result: ResultadoGeracao) {
    if (downloading) return;
    setDownloading(true);
    try {
      await baixarRepositorioZip(result);
    } finally {
      setDownloading(false);
    }
  }

  return { downloading, download };
}
