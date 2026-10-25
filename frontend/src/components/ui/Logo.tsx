import Link from "next/link";
import React from "react";

export const PRODUCT = "Concept";

/** Wordmark: a node-and-edge glyph (the concept graph) plus the product name. */
export function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="inline-flex items-center gap-2 font-semibold tracking-tight text-fg" aria-label={`${PRODUCT} home`}>
      <svg width="24" height="24" viewBox="0 0 24 24" aria-hidden className="text-accent">
        <circle cx="5" cy="6" r="3" fill="currentColor" />
        <circle cx="19" cy="6" r="3" fill="currentColor" opacity="0.55" />
        <circle cx="12" cy="18" r="3" fill="currentColor" opacity="0.8" />
        <path d="M5 6 12 18 19 6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" opacity="0.6" />
      </svg>
      <span className="text-[17px]">{PRODUCT}</span>
    </Link>
  );
}
