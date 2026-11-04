import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface ContentPageProps {
  icon: LucideIcon;
  title: string;
  description: ReactNode;
  /** `wide` for pages with tables; `default` for forms and short content. */
  size?: "default" | "wide";
  children?: ReactNode;
}

/**
 * Standard layout of a secondary page (management, settings): a single
 * centred card with icon + title, a short description and the page content.
 * Every such page must use it so they all share the same margins and spacing.
 */
export function ContentPage({
  icon: Icon,
  title,
  description,
  size = "default",
  children,
}: ContentPageProps) {
  return (
    <div className={cn("mx-auto w-full px-6 py-8", size === "wide" ? "max-w-6xl" : "max-w-3xl")}>
      <section className="rounded-xl border border-border bg-card p-6 shadow-sm">
        <div className="flex items-center gap-2">
          <Icon className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold text-card-foreground">{title}</h2>
        </div>
        <div className="mt-3 text-sm text-muted-foreground">{description}</div>
        {children && <div className="mt-4">{children}</div>}
      </section>
    </div>
  );
}
