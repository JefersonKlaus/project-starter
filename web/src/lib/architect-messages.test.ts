import { describe, expect, it } from "vitest";

import {
  formatIssues,
  parseServerMessage,
  promptMessageSchema,
  resultadoGeracaoSchema,
  serverMessageSchema,
} from "./architect-messages";
import { mockResultado } from "@/test/fixtures";

const frame = (obj: unknown) => JSON.stringify(obj);

describe("resultadoGeracaoSchema (strict)", () => {
  it("accepts the backend's result contract", () => {
    expect(resultadoGeracaoSchema.safeParse(mockResultado).success).toBe(true);
  });

  it("rejects unknown top-level keys", () => {
    const r = resultadoGeracaoSchema.safeParse({ ...mockResultado, extra: 1 });
    expect(r.success).toBe(false);
    if (!r.success) expect(formatIssues(r.error)).toMatch(/Unrecognized key/);
  });

  it("rejects unknown keys inside aws_services entries", () => {
    const r = resultadoGeracaoSchema.safeParse({
      ...mockResultado,
      aws_services: [{ service: "AWS Lambda", resource_name: "x", arn: "arn:..." }],
    });
    expect(r.success).toBe(false);
    if (!r.success) expect(formatIssues(r.error)).toMatch(/^aws_services\.0: Unrecognized key/);
  });

  it("rejects missing fields and wrong types", () => {
    const { rag_references: _omit, ...missing } = mockResultado;
    expect(resultadoGeracaoSchema.safeParse(missing).success).toBe(false);

    const wrongType = { ...mockResultado, generated_code: { terraform: { "main.tf": 42 } } };
    const r = resultadoGeracaoSchema.safeParse(wrongType);
    expect(r.success).toBe(false);
    if (!r.success) expect(formatIssues(r.error)).toMatch(/generated_code\.terraform\.main\.tf/);
  });
});

describe("serverMessageSchema (strict)", () => {
  it.each([
    ["accepted", { type: "accepted", request_id: "r1" }],
    ["result", { type: "result", request_id: "r1", result: mockResultado }],
    ["error (full)", { type: "error", request_id: "r1", message: "boom", error: "E" }],
    ["error (minimal)", { type: "error" }],
    ["pong", { type: "pong" }],
  ])("accepts a valid %s frame", (_name, message) => {
    expect(serverMessageSchema.safeParse(message).success).toBe(true);
  });

  it.each([
    ["unknown type", { type: "progress", request_id: "r1" }],
    ["accepted with extra key", { type: "accepted", request_id: "r1", connectionId: "c" }],
    ["accepted without request_id", { type: "accepted" }],
    ["accepted with empty request_id", { type: "accepted", request_id: "" }],
    ["result with extra key", { type: "result", request_id: "r1", result: mockResultado, ts: 1 }],
    ["result with invalid payload", { type: "result", request_id: "r1", result: { foo: 1 } }],
    ["error with extra key", { type: "error", code: 500 }],
    ["pong with extra key", { type: "pong", at: 1 }],
    ["missing type", { request_id: "r1" }],
  ])("rejects %s", (_name, message) => {
    expect(serverMessageSchema.safeParse(message).success).toBe(false);
  });
});

describe("parseServerMessage", () => {
  it("returns the typed message for valid frames", () => {
    const parsed = parseServerMessage(frame({ type: "accepted", request_id: "r1" }));
    expect(parsed).toEqual({ ok: true, message: { type: "accepted", request_id: "r1" } });
  });

  it("reports non-text and non-JSON frames", () => {
    expect(parseServerMessage(new ArrayBuffer(2))).toMatchObject({ ok: false, reason: /not text/ });
    expect(parseServerMessage("{oops")).toMatchObject({ ok: false, reason: /not valid JSON/ });
  });

  it("keeps type and request_id of invalid frames so the pending request can be failed", () => {
    const parsed = parseServerMessage(
      frame({ type: "result", request_id: "r9", result: { ...mockResultado, extra: true } }),
    );
    expect(parsed).toMatchObject({ ok: false, type: "result", requestId: "r9" });
    if (!parsed.ok) expect(parsed.reason).toMatch(/result: Unrecognized key/);
  });
});

describe("promptMessageSchema", () => {
  it("accepts the outgoing prompt frame and rejects empty prompts / extra keys", () => {
    expect(promptMessageSchema.safeParse({ action: "prompt", prompt: "x" }).success).toBe(true);
    expect(promptMessageSchema.safeParse({ action: "prompt", prompt: "" }).success).toBe(false);
    expect(promptMessageSchema.safeParse({ action: "prompt", prompt: "x", id: 1 }).success).toBe(
      false,
    );
  });
});
