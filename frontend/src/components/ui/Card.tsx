import React from "react";
import { cn } from "./cn";

export function Card({
  className,
  children,
  as: Tag = "div",
  ...rest
}: React.HTMLAttributes<HTMLElement> & { as?: "div" | "section" | "article" }) {
  return (
    <Tag className={cn("rounded-xl border border-line bg-surface shadow-card", className)} {...rest}>
      {children}
    </Tag>
  );
}

export function SectionTitle({ title, hint, action }: { title: string; hint?: string; action?: React.ReactNode }) {
  return (
    <div className="flex items-end justify-between gap-4">
      <div>
        <h2 className="text-base font-semibold tracking-tight text-fg">{title}</h2>
        {hint && <p className="mt-0.5 text-sm text-muted">{hint}</p>}
      </div>
      {action}
    </div>
  );
}
