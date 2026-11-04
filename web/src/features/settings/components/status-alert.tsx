import { AlertCircle, CheckCircle2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import type { SubmitStatus } from "../hooks/use-submit-state";

/** Shows the outcome of a form submission (nothing while idle/submitting). */
export function StatusAlert({ status }: { status: SubmitStatus }) {
  if (status.kind === "error") {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>{status.message}</AlertDescription>
      </Alert>
    );
  }
  if (status.kind === "success") {
    return (
      <Alert className="border-emerald-500/40 [&>svg]:text-emerald-600">
        <CheckCircle2 className="h-4 w-4" />
        <AlertDescription>{status.message}</AlertDescription>
      </Alert>
    );
  }
  return null;
}
