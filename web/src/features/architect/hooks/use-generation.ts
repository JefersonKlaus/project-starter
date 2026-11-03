import { useRef, useState } from "react";

import { isAbortError } from "@/lib/architect-socket";
import { useArchitectSocket } from "@/lib/architect-socket-context";
import type { ResultadoGeracao } from "@/lib/infra-api";

/** Phases of a prompt in flight. */
export type GenerationPhase = { name: "sending" } | { name: "processing"; requestId: string };

export interface UseGenerationOptions {
  /** Called right after a result is accepted for display (e.g. to scroll to it). */
  onResult?: (result: ResultadoGeracao) => void;
}

/**
 * Owns the lifecycle of one architecture generation over the WebSocket:
 *
 *   generate() -> { action: "prompt" }  -> "sending"
 *   server     -> { type: "accepted" }   -> "processing" (request_id known)
 *   server     -> { type: "result" }     -> result shown, phase cleared
 *   cancel()   -> AbortSignal            -> phase cleared, late replies ignored
 *
 * Only a result whose `request_id` matches the last prompt the user is waiting
 * for is ever exposed; anything else is dropped.
 */
export function useGeneration({ onResult }: UseGenerationOptions = {}) {
  const socket = useArchitectSocket();
  const [result, setResult] = useState<ResultadoGeracao | null>(null);
  const [phase, setPhase] = useState<GenerationPhase | null>(null);
  const [error, setError] = useState<string | null>(null);

  /** Controller of the prompt currently in flight (lets the user cancel it). */
  const abortRef = useRef<AbortController | null>(null);
  /** `request_id` of the prompt the user is waiting for (set on `accepted`). */
  const currentRequestIdRef = useRef<string | null>(null);

  const isGenerating = phase !== null;

  async function generate(prompt: string) {
    const text = prompt.trim();
    if (!text || isGenerating) return;

    setError(null);
    setResult(null); // back to the loading state
    setPhase({ name: "sending" });

    const controller = new AbortController();
    abortRef.current = controller;
    currentRequestIdRef.current = null;

    try {
      const response = await socket.sendPrompt(text, {
        signal: controller.signal,
        onAccepted: (requestId) => {
          if (controller.signal.aborted) return;
          currentRequestIdRef.current = requestId;
          setPhase({ name: "processing", requestId });
        },
      });

      if (controller.signal.aborted) return;
      if (response.requestId !== currentRequestIdRef.current) {
        console.warn(
          "[portal] Resultado ignorado: request_id diferente do esperado",
          response.requestId,
          currentRequestIdRef.current,
        );
        return;
      }
      setResult(response.result);
      onResult?.(response.result);
    } catch (err) {
      if (isAbortError(err) || controller.signal.aborted) return; // cancelled by the user
      setError(err instanceof Error ? err.message : "Falha ao gerar a arquitetura.");
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        setPhase(null);
      }
    }
  }

  /** Cancels the prompt in flight and releases the form for a new one. */
  function cancel() {
    const controller = abortRef.current;
    if (!controller) return;
    controller.abort();
    abortRef.current = null;
    currentRequestIdRef.current = null;
    setPhase(null);
    setError(null);
  }

  return { result, phase, isGenerating, error, generate, cancel };
}
