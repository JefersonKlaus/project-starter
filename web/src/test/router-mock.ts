// Shared mock for `@tanstack/react-router` used by route component tests.
//
// `createFileRoute(path)(options)` normally wires the file into the generated
// route tree; here it simply returns the options plus the hooks the pages use,
// so a page component can be rendered in isolation as `Route.options.component`.
import { vi } from "vitest";

export const navigateMock = vi.fn();

export const routerState = {
  search: {} as Record<string, unknown>,
  context: {} as Record<string, unknown>,
};

export function resetRouterMock() {
  navigateMock.mockReset();
  navigateMock.mockResolvedValue(undefined);
  routerState.search = {};
  routerState.context = {};
}

export async function mockReactRouterModule(
  importOriginal: () => Promise<Record<string, unknown>>,
) {
  const actual = await importOriginal();
  return {
    ...actual,
    createFileRoute: () => (options: Record<string, unknown>) => ({
      options,
      useSearch: () => routerState.search,
      useRouteContext: () => routerState.context,
    }),
    useNavigate: () => navigateMock,
    Link: ({ children }: { children?: unknown }) => children,
    Outlet: () => null,
  };
}

/** Convenience: the page component registered with `createFileRoute`. */
export function pageOf(route: unknown): React.ComponentType {
  const component = (route as { options: { component: React.ComponentType } }).options.component;
  if (!component) throw new Error("Route has no component");
  return component;
}
