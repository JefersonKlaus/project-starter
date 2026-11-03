// ============================================================================
// WebSocket message contracts (src/lib/architect-messages.ts)
// ----------------------------------------------------------------------------
// Zod schemas for every frame exchanged with the generation backend. All
// object schemas are `.strict()`: a frame carrying any key that is not part of
// the contract is rejected, so an unexpected backend change (or a spoofed
// message) never reaches the UI.
//
// The TypeScript types used across the app are derived from these schemas, so
// the contract has a single source of truth.
// ============================================================================

import { z } from "zod";

// ----------------------------------------------------------------------------
// Generation result (`result` field of the "result" frame)
// ----------------------------------------------------------------------------

export const servicoAwsSchema = z
  .object({
    /** AWS service name, e.g. "AWS Lambda", "Amazon DynamoDB". */
    service: z.string().min(1),
    /** Descriptive resource name, e.g. "Create Item Lambda". */
    resource_name: z.string().min(1),
  })
  .strict();

/**
 * Generated code: first key = language/folder (e.g. "terraform", "python"),
 * second key = file name (e.g. "main.tf"), value = file content.
 */
export const arquivosPorLinguagemSchema = z.record(
  z.string().min(1),
  z.record(z.string().min(1), z.string()),
);

export const resultadoGeracaoSchema = z
  .object({
    /** Date/time of the analysis returned by the backend. */
    analysis_date: z.string().min(1),
    /** Architecture diagram in Mermaid syntax. */
    mermaid_diagram: z.string(),
    /** AWS services that make up the architecture. */
    aws_services: z.array(servicoAwsSchema),
    /** Generated source code, organized by language/folder. */
    generated_code: arquivosPorLinguagemSchema,
    /** Paths of the files used as references by the RAG. */
    rag_references: z.array(z.string()),
  })
  .strict();

export type ServicoAws = z.infer<typeof servicoAwsSchema>;
export type ArquivosPorLinguagem = z.infer<typeof arquivosPorLinguagemSchema>;
export type ResultadoGeracao = z.infer<typeof resultadoGeracaoSchema>;

// ----------------------------------------------------------------------------
// Server -> client frames
// ----------------------------------------------------------------------------

const requestId = z.string().min(1);

/** First reply to a prompt: the backend acknowledged it and assigned an id. */
export const acceptedMessageSchema = z
  .object({ type: z.literal("accepted"), request_id: requestId })
  .strict();

/** Final reply carrying the generated architecture. */
export const resultMessageSchema = z
  .object({ type: z.literal("result"), request_id: requestId, result: resultadoGeracaoSchema })
  .strict();

/** Failure reported by the backend for a request (or for the connection). */
export const errorMessageSchema = z
  .object({
    type: z.literal("error"),
    request_id: requestId.optional(),
    message: z.string().optional(),
    error: z.string().optional(),
  })
  .strict();

/** Keepalive reply. */
export const pongMessageSchema = z.object({ type: z.literal("pong") }).strict();

export const serverMessageSchema = z.discriminatedUnion("type", [
  acceptedMessageSchema,
  resultMessageSchema,
  errorMessageSchema,
  pongMessageSchema,
]);

export type AcceptedMessage = z.infer<typeof acceptedMessageSchema>;
export type ResultMessage = z.infer<typeof resultMessageSchema>;
export type ErrorMessage = z.infer<typeof errorMessageSchema>;
export type PongMessage = z.infer<typeof pongMessageSchema>;
export type ServerMessage = z.infer<typeof serverMessageSchema>;

// ----------------------------------------------------------------------------
// Client -> server frames
// ----------------------------------------------------------------------------

export const promptMessageSchema = z
  .object({ action: z.literal("prompt"), prompt: z.string().min(1) })
  .strict();

export type PromptMessage = z.infer<typeof promptMessageSchema>;

// ----------------------------------------------------------------------------
// Parsing helpers
// ----------------------------------------------------------------------------

/**
 * Loose look at an incoming frame, used only to correlate an *invalid* message
 * with the pending request it was meant for (so that request can be failed
 * instead of waiting for its timeout).
 */
const envelopeSchema = z.object({
  type: z.string().optional(),
  request_id: z.string().optional(),
});

export type ParsedServerMessage =
  | { ok: true; message: ServerMessage }
  | { ok: false; reason: string; type: string | undefined; requestId: string | undefined };

/** Formats Zod issues as a short, readable list: `result.aws_services.0.service: Required`. */
export function formatIssues(error: z.ZodError): string {
  return error.issues
    .slice(0, 5)
    .map((issue) =>
      issue.path.length ? `${issue.path.join(".")}: ${issue.message}` : issue.message,
    )
    .join("; ");
}

/** Parses and strictly validates a raw WebSocket frame. */
export function parseServerMessage(raw: unknown): ParsedServerMessage {
  if (typeof raw !== "string") {
    return { ok: false, reason: "frame is not text", type: undefined, requestId: undefined };
  }

  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return { ok: false, reason: "frame is not valid JSON", type: undefined, requestId: undefined };
  }

  const parsed = serverMessageSchema.safeParse(data);
  if (parsed.success) return { ok: true, message: parsed.data };

  const envelope = envelopeSchema.safeParse(data);
  return {
    ok: false,
    reason: formatIssues(parsed.error),
    type: envelope.success ? envelope.data.type : undefined,
    requestId: envelope.success ? envelope.data.request_id : undefined,
  };
}
