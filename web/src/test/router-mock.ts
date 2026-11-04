// Shared mock for `@tanstack/react-router` used by route component tests.
//
// `createFileRoute(path)(options)` normally wires the file into the generated
// route tree; here it simply returns the options plus the hooks the pages use,
// so a page component can be rendered in isolation as `Route.options.component`.
import { createElement, type ReactNode } from "react";
import { vi } from "vitest";

export const navigateMock = vi.fn();

export const routerState = {
  search: {} as Record<string, unknown>,
  context: {} as Record<string, unknown>,
  /** Current URL path, as seen by `useLocation`. */
  pathname: "/",
  /** Matched routes (root first), as seen by `useMatches`. */
  matches: [] as { staticData: Record<string, unknown> }[],
};

export function resetRouterMock() {
  navigateMock.mockReset();
  navigateMock.mockResolvedValue(undefined);
  routerState.search = {};
  routerState.context = {};
  routerState.pathname = "/";
  routerState.matches = [];
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
    useLocation: (opts?: { select?: (location: { pathname: string }) => unknown }) => {
      const location = { pathname: routerState.pathname };
      return opts?.select ? opts.select(location) : location;
    },
    useMatches: (opts?: { select?: (matches: typeof routerState.matches) => unknown }) =>
      opts?.select ? opts.select(routerState.matches) : routerState.matches,
    // Rendered as a plain anchor so links can be found by role/href in tests.
    // Like the real Link, it stops the browser's own navigation (jsdom cannot
    // load another document anyway).
    Link: ({
      to,
      children,
      onClick,
      ...rest
    }: { to?: string; children?: unknown; onClick?: (e: MouseEvent) => void } & Record<
      string,
      unknown
    >) =>
      createElement(
        "a",
        {
          href: to,
          ...rest,
          onClick: (e: MouseEvent) => {
            onClick?.(e);
            e.preventDefault();
          },
        },
        children as ReactNode,
      ),
    Outlet: () => null,
  };
}

/** Convenience: the page component registered with `createFileRoute`. */
export function pageOf(route: unknown): React.ComponentType {
  const component = (route as { options: { component: React.ComponentType } }).options.component;
  if (!component) throw new Error("Route has no component");
  return component;
}
