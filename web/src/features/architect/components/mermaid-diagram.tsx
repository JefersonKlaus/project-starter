import { useEffect, useRef, useState } from "react";

/** Renders a Mermaid diagram (client-side only; the library is loaded lazily). */
export function MermaidDiagram({ code }: { code: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    setFailed(false);
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, theme: "neutral" });
        const id = `mmd-${Math.random().toString(36).slice(2)}`;
        const { svg } = await mermaid.render(id, code);
        if (active && ref.current) ref.current.innerHTML = svg;
      } catch {
        if (active) setFailed(true);
      }
    })();
    return () => {
      active = false;
    };
  }, [code]);

  if (failed) {
    return (
      <pre className="overflow-auto rounded-lg bg-background p-3 text-xs text-muted-foreground">
        {code}
      </pre>
    );
  }
  return (
    <div ref={ref} className="flex justify-center overflow-auto rounded-lg bg-background p-3" />
  );
}
