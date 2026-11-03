import JSZip from "jszip";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { baixarRepositorioZip, buscarRegrasCorporativas } from "./infra-api";
import { mockResultado } from "@/test/fixtures";

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
