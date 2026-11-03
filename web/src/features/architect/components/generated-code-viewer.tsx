import { FileCode2, FolderGit2 } from "lucide-react";

import type { GeneratedFile } from "../hooks/use-generated-files";
import { cn } from "@/lib/utils";

export interface GeneratedCodeViewerProps {
  files: GeneratedFile[];
  selected: GeneratedFile | null;
  onSelect: (key: string) => void;
}

/** File tabs + content of the selected generated file. */
export function GeneratedCodeViewer({ files, selected, onSelect }: GeneratedCodeViewerProps) {
  return (
    <div>
      <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        <FolderGit2 className="h-3.5 w-3.5" /> Código Gerado
      </h3>
      <div className="mt-2 overflow-hidden rounded-lg border border-border">
        <div className="flex flex-wrap border-b border-border bg-muted">
          {files.map((file) => (
            <button
              key={file.key}
              onClick={() => onSelect(file.key)}
              className={cn(
                "flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs font-medium transition",
                selected?.key === file.key
                  ? "border-primary bg-background text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              <FileCode2 className="h-3.5 w-3.5" />
              {file.name}
            </button>
          ))}
        </div>
        {selected && (
          <pre className="max-h-80 overflow-auto bg-background p-4 text-xs leading-relaxed text-foreground">
            <code>{selected.content}</code>
          </pre>
        )}
      </div>
    </div>
  );
}
