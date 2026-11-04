import { useCallback, useState } from "react";

export type SubmitStatus =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "success"; message: string }
  | { kind: "error"; message: string };

/**
 * Tracks an async form submission: runs `action`, stores the outcome and
 * turns thrown errors into a message through `describeError`.
 */
export function useSubmitState(describeError: (error: unknown) => string) {
  const [status, setStatus] = useState<SubmitStatus>({ kind: "idle" });

  const run = useCallback(
    async (action: () => Promise<void>, successMessage: string): Promise<boolean> => {
      setStatus({ kind: "submitting" });
      try {
        await action();
        setStatus({ kind: "success", message: successMessage });
        return true;
      } catch (error) {
        setStatus({ kind: "error", message: describeError(error) });
        return false;
      }
    },
    [describeError],
  );

  const fail = useCallback((message: string) => setStatus({ kind: "error", message }), []);
  const reset = useCallback(() => setStatus({ kind: "idle" }), []);

  return { status, submitting: status.kind === "submitting", run, fail, reset };
}
