import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { ContentPage } from "./content-page";

export interface PlaceholderPageProps {
  icon: LucideIcon;
  title: string;
  description: ReactNode;
}

/** A page whose feature is not ready yet: the standard card with an "Em breve" badge. */
export function PlaceholderPage(props: PlaceholderPageProps) {
  return (
    <ContentPage {...props}>
      <p className="inline-block rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
        Em breve
      </p>
    </ContentPage>
  );
}
