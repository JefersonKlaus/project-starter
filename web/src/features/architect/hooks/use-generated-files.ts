import { useEffect, useMemo, useState } from "react";

import type { ResultadoGeracao } from "@/lib/infra-api";

export interface GeneratedFile {
  /** Unique key: `<language>/<file name>`. */
  key: string;
  language: string;
  name: string;
  content: string;
}

/** Flattens `generated_code` into a list and tracks the selected file tab. */
export function useGeneratedFiles(result: ResultadoGeracao | null) {
  const files = useMemo<GeneratedFile[]>(() => {
    if (!result) return [];
    return Object.entries(result.generated_code).flatMap(([language, list]) =>
      Object.entries(list).map(([name, content]) => ({
        key: `${language}/${name}`,
        language,
        name,
        content,
      })),
    );
  }, [result]);

  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  // A new result always starts on its first file.
  useEffect(() => {
    setSelectedKey(null);
  }, [result]);

  const selected = files.find((f) => f.key === selectedKey) ?? files[0] ?? null;

  return { files, selected, select: setSelectedKey };
}
