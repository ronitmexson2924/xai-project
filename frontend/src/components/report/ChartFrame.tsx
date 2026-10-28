"use client";

import React, { useEffect, useRef, useState } from "react";
import { cn } from "../ui/cn";

/** The width available to a chart, kept up to date as the layout changes (phones to desktops). */
function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T | null>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

/**
 * Every report chart sits in one of these: a title, the chart (drawn at the real pixel width, so
 * text stays readable on a phone), an optional legend, a one-line caption on how to read it, and
 * a table view of the same numbers, so nothing depends on seeing the picture.
 */
export function ChartFrame({
  id,
  title,
  caption,
  legend,
  table,
  className,
  testId,
  children,
}: {
  id: string;
  title: string;
  caption: string;
  legend?: React.ReactNode;
  table?: React.ReactNode;
  className?: string;
  testId?: string;
  children: (width: number) => React.ReactNode;
}) {
  const [asTable, setAsTable] = useState(false);
  const [ref, width] = useWidth<HTMLDivElement>();
  return (
    <figure
      aria-labelledby={`${id}-title`}
      data-testid={testId}
      className={cn("min-w-0 space-y-3 rounded-xl border border-line bg-surface p-4 shadow-card break-inside-avoid sm:p-5", className)}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 id={`${id}-title`} className="text-sm font-semibold text-fg">
          {title}
        </h3>
        {table && (
          <button type="button" onClick={() => setAsTable((t) => !t)} className="no-print text-xs font-medium text-primary hover:text-primary-hover">
            {asTable ? "Show chart" : "Show as table"}
          </button>
        )}
      </div>
      {legend && !asTable && <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">{legend}</div>}
      <div ref={ref} className="min-w-0">
        {asTable ? <div className="relative overflow-x-auto">{table}</div> : width > 0 ? children(width) : <div className="h-40" />}
      </div>
      <figcaption className="text-xs leading-relaxed text-muted">{caption}</figcaption>
    </figure>
  );
}

/** "▲ raises" / "▼ lowers": the one colour pair used for direction in every chart. */
export function DirectionLegend({ raises = "raises the prediction", lowers = "lowers it" }: { raises?: string; lowers?: string }) {
  return (
    <>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-3 rounded-sm bg-viz-raise" aria-hidden />
        <span aria-hidden className="text-[10px] text-viz-raise">▲</span> {raises}
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-3 rounded-sm bg-viz-lower" aria-hidden />
        <span aria-hidden className="text-[10px] text-viz-lower">▼</span> {lowers}
      </span>
    </>
  );
}

/** A small table used by the charts' table views. */
export function DataTable({ head, rows }: { head: string[]; rows: React.ReactNode[][] }) {
  return (
    <table className="w-full min-w-[420px] text-sm">
      <thead>
        <tr className="border-b border-line text-left text-xs text-subtle">
          {head.map((h, i) => (
            <th key={h} className={cn("py-1.5 pr-3 font-medium", i > 0 && "text-right")}>
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, r) => (
          <tr key={r} className="border-b border-line/60">
            {row.map((cell, c) => (
              <td key={c} className={cn("py-1.5 pr-3", c === 0 ? "text-fg" : "text-right tabular-nums text-muted")}>
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Truncate a label to fit `px` pixels, at about `charPx` per character (6.4 suits 12 px text). */
export function fit(label: string, px: number, charPx = 6.4): string {
  const max = Math.max(4, Math.floor(px / charPx));
  return label.length > max ? label.slice(0, max - 1) + "…" : label;
}
