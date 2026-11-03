import { AlertCircle } from "lucide-react";

/** Small destructive notice used under the prompt form. */
export function InlineError({ message }: { message: string }) {
  return (
    <p className="mt-3 flex items-start gap-2 rounded-lg border border-destructive/50 bg-destructive/5 px-3 py-2 text-xs text-destructive">
      <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      {message}
    </p>
  );
}
