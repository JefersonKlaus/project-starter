export function RagReferences({ references }: { references: string[] }) {
  if (references.length === 0) return null;
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Referências RAG utilizadas
      </h3>
      <ul className="mt-2 space-y-1">
        {references.map((ref) => (
          <li
            key={ref}
            className="truncate rounded-md bg-muted px-2 py-1 font-mono text-[11px] text-muted-foreground"
            title={ref}
          >
            {ref}
          </li>
        ))}
      </ul>
    </div>
  );
}
