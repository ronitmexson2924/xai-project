"use client";

import React from "react";

/**
 * A deliberately tiny renderer for explanation text: fenced code blocks, inline `code` and
 * **bold**. Everything is rendered as React text, never as HTML, so an LLM output or a card
 * containing markup cannot inject script into the page.
 */
export function Markdown({ text }: { text: string }) {
  const parts = text.split(/```[a-zA-Z0-9_-]*\n?/);
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <pre
            key={i}
            className="my-2 overflow-x-auto rounded-lg bg-slate-950 p-3 font-mono text-xs text-emerald-200 border border-slate-800"
          >
            <code>{part.replace(/\n$/, "")}</code>
          </pre>
        ) : (
          part
            .split(/\n{2,}/)
            .filter((p) => p.trim())
            .map((para, j) => (
              <p key={`${i}-${j}`} className="whitespace-pre-line">
                {inline(para)}
              </p>
            ))
        )
      )}
    </>
  );
}

function inline(text: string): React.ReactNode[] {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*)/).map((chunk, k) => {
    if (chunk.startsWith("`") && chunk.endsWith("`") && chunk.length > 2) {
      return (
        <code key={k} className="rounded bg-slate-800 px-1 font-mono text-[0.9em] text-indigo-200">
          {chunk.slice(1, -1)}
        </code>
      );
    }
    if (chunk.startsWith("**") && chunk.endsWith("**") && chunk.length > 4) {
      return <strong key={k}>{chunk.slice(2, -2)}</strong>;
    }
    return <React.Fragment key={k}>{chunk}</React.Fragment>;
  });
}
