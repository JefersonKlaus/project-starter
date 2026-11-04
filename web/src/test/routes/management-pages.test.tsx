import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { pageOf, resetRouterMock } from "@/test/router-mock";

// Hoisted above the imports, so the helper must be imported inside the factory.
vi.mock("@tanstack/react-router", async (importOriginal) => {
  const { mockReactRouterModule } = await import("@/test/router-mock");
  return mockReactRouterModule(importOriginal as () => Promise<Record<string, unknown>>);
});

import { Route as RepositoriesRoute } from "@/routes/_authenticated/repositories";

beforeEach(() => {
  resetRouterMock();
});

describe.each([
  {
    name: "repositories",
    route: RepositoriesRoute,
    title: "Repositórios",
    text: /repositórios vinculados/,
  },
])("$name page", ({ route, title, text }) => {
  it("declares the header title and shows the placeholder content", () => {
    expect(route.options.staticData).toEqual({ title });

    const Page = pageOf(route);
    render(<Page />);
    expect(screen.getByRole("heading", { level: 2, name: title })).toBeInTheDocument();
    expect(screen.getByText(text)).toBeInTheDocument();
    expect(screen.getByText("Em breve")).toBeInTheDocument();
  });
});
