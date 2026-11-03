import type { AuthSession } from "@/lib/auth/session";
import type { ResultadoGeracao } from "@/lib/infra-api";

/** Builds an unsigned JWT with the given claims (enough for payload decoding). */
export function fakeJwt(claims: Record<string, unknown>): string {
  const payload = Buffer.from(JSON.stringify(claims)).toString("base64url");
  return `header.${payload}.signature`;
}

export function makeSession(overrides: Partial<AuthSession> = {}): AuthSession {
  return {
    accessToken: "access-token",
    idToken: fakeJwt({ email: "ana@empresa.com" }),
    refreshToken: "refresh-token",
    expiresAt: Date.now() + 60 * 60 * 1000,
    email: "ana@empresa.com",
    ...overrides,
  };
}

/** Mirrors the shape of the `result` frame sent by the generation backend. */
export const mockResultado: ResultadoGeracao = {
  analysis_date: "2026-11-02",
  mermaid_diagram: "graph LR\n    API[API Gateway] --> CreateTask[create_task.py]",
  aws_services: [
    { service: "AWS Lambda", resource_name: "create_task" },
    { service: "Amazon API Gateway", resource_name: "TodoApi" },
    { service: "Amazon DynamoDB", resource_name: "TasksTable" },
  ],
  generated_code: {
    terraform: {
      "main.tf": 'provider "aws" {\n  region = var.region\n}',
      "variables.tf": 'variable "region" {}',
    },
    python: {
      "create_task.py": "import os\nimport json",
    },
  },
  rag_references: ["lambda_create/ai/machine.py"],
};
