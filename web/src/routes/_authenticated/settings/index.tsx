import { createFileRoute, redirect } from "@tanstack/react-router";

/** `/settings` has no content of its own: open the first settings page. */
export const Route = createFileRoute("/_authenticated/settings/")({
  beforeLoad: () => {
    throw redirect({ to: "/settings/git-provider", replace: true });
  },
});
