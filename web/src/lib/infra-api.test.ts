import JSZip from "jszip";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { makeSession, mockResultado } from "@/test/fixtures";

vi.mock("./auth/session", () => ({ ensureValidSession: vi.fn() }));

import { ensureValidSession } from "./auth/session";
import {
  ApiError,
  baixarRepositorioZip,
  buscarRegrasCorporativas,
  getApiBaseUrl,
  listarProjetos,
  salvarConexaoGit,
} from "./infra-api";

describe("buscarRegrasCorporativas", () => {
  it("returns the default active corporate rules", async () => {
    const regras = await buscarRegrasCorporativas();
    expect(regras.length).toBeGreaterThan(0);
    expect(regras.every((r) => r.ativa)).toBe(true);
    expect(regras.map((r) => r.descricao)).toContain("CloudWatch logs ativados");
  });
});

describe("baixarRepositorioZip", () => {
  let blob: Blob | null = null;
  let clicked: HTMLAnchorElement | null = null;

  beforeEach(() => {
    blob = null;
    clicked = null;
    // jsdom does not implement object URLs; capture the blob instead.
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn((b: Blob) => {
        blob = b;
        return "blob:mock-url";
      }),
      revokeObjectURL: vi.fn(),
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicked = this; // eslint-disable-line @typescript-eslint/no-this-alias -- capture the clicked anchor
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("packs generated files per language folder plus the Mermaid diagram and triggers the download", async () => {
    await baixarRepositorioZip(mockResultado);

    expect(clicked?.download).toBe("repositorio-gerado.zip");
    expect(clicked?.href).toContain("blob:mock-url");
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock-url");

    const zip = await JSZip.loadAsync(blob as unknown as Blob);
    expect(
      Object.keys(zip.files)
        .filter((f) => !zip.files[f]?.dir)
        .sort(),
    ).toEqual([
      "diagram.mmd",
      "python/create_task.py",
      "terraform/main.tf",
      "terraform/variables.tf",
    ]);
    expect(await zip.file("terraform/main.tf")?.async("string")).toBe(
      mockResultado.generated_code["terraform"]?.["main.tf"],
    );
    expect(await zip.file("diagram.mmd")?.async("string")).toBe(mockResultado.mermaid_diagram);
  });
});

describe("salvarConexaoGit", () => {
  const fetchMock = vi.fn<(url: string, init: RequestInit) => Promise<Response>>();

  beforeEach(() => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.com/dev/");
    vi.mocked(ensureValidSession).mockResolvedValue(makeSession({ idToken: "the-id-token" }));
    fetchMock.mockReset();
    fetchMock.mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("reads the base URL from VITE_API_BASE_URL without the trailing slash", () => {
    expect(getApiBaseUrl()).toBe("https://api.example.com/dev");
  });

  it("fails with a configuration error when VITE_API_BASE_URL is missing", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "");
    expect(() => getApiBaseUrl()).toThrow(/VITE_API_BASE_URL/);
    await expect(
      salvarConexaoGit({ provider: "github", serverUrl: "https://github.com", token: "t" }),
    ).rejects.toThrow(/VITE_API_BASE_URL/);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("posts the connection data to the backend with the Cognito bearer token", async () => {
    await salvarConexaoGit({
      provider: "gitlab",
      serverUrl: "https://gitlab.empresa.com/",
      username: "  meu-grupo ",
      token: "glpat-123",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("https://api.example.com/dev/integrations/git-provider");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({
      Authorization: "Bearer the-id-token",
      "Content-Type": "application/json",
    });
    expect(JSON.parse(String(init.body))).toEqual({
      provider: "gitlab",
      server_url: "https://gitlab.empresa.com",
      username: "meu-grupo",
      token: "glpat-123",
    });
  });

  it("omits the username when it is blank", async () => {
    await salvarConexaoGit({
      provider: "github",
      serverUrl: "https://github.com",
      username: "   ",
      token: "ghp_1",
    });
    expect(JSON.parse(String(fetchMock.mock.calls[0]![1].body))).toEqual({
      provider: "github",
      server_url: "https://github.com",
      token: "ghp_1",
    });
  });

  it("refuses to send anything without a valid session", async () => {
    vi.mocked(ensureValidSession).mockResolvedValue(null);
    await expect(
      salvarConexaoGit({ provider: "github", serverUrl: "https://github.com", token: "t" }),
    ).rejects.toMatchObject({ status: 401, message: /Sessão expirada/ });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("uses the backend's message on HTTP errors, with a fallback by status", async () => {
    const conexao = { provider: "github" as const, serverUrl: "https://github.com", token: "t" };

    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ message: "Token inválido para o provedor." }), { status: 422 }),
    );
    await expect(salvarConexaoGit(conexao)).rejects.toMatchObject({
      status: 422,
      message: "Token inválido para o provedor.",
    });

    fetchMock.mockResolvedValue(new Response("<html>Forbidden</html>", { status: 403 }));
    await expect(salvarConexaoGit(conexao)).rejects.toMatchObject({
      status: 403,
      message: /Sem permissão/,
    });

    fetchMock.mockResolvedValue(new Response("", { status: 500 }));
    await expect(salvarConexaoGit(conexao)).rejects.toMatchObject({
      status: 500,
      message: /HTTP 500/,
    });
  });

  it("reports network failures in plain words", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const error = await salvarConexaoGit({
      provider: "github",
      serverUrl: "https://github.com",
      token: "t",
    }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toMatch(/Não foi possível conectar/);
  });
});

describe("listarProjetos", () => {
  it("returns the mock projects with every status/git/provider combination used by the UI", async () => {
    const projetos = await listarProjetos();
    expect(projetos.length).toBeGreaterThan(0);
    expect(new Set(projetos.map((p) => p.id)).size).toBe(projetos.length);
    expect(new Set(projetos.map((p) => p.status))).toEqual(
      new Set(["local", "publicando", "producao"]),
    );
    expect(new Set(projetos.map((p) => p.git))).toEqual(
      new Set(["nao_sincronizado", "sincronizando", "sincronizado"]),
    );
    // A project without a repository has no provider either.
    for (const p of projetos) expect(p.repositorio === null).toBe(p.provider === null);
  });
});
