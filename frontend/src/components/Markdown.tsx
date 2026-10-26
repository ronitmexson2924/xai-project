import React from "react";
import { highlightLine, TokenKind } from "@/lib/highlight";
import { Diagram } from "./Diagram";

const TOKEN_CLASS: Record<TokenKind, string | undefined> = {
  keyword: "text-[var(--code-keyword)] font-medium",
  string: "text-[var(--code-string)]",
  number: "text-[var(--code-number)]",
  comment: "text-[var(--code-comment)] italic",
  plain: undefined,
};

/**
 * A small, safe Markdown renderer for explanation and card text: fenced code blocks, headings,
 * bullet lists, paragraphs, **bold** and `code`. Everything is rendered as React text nodes, never
 * as HTML, so text from the server (or an LLM) cannot inject markup or scripts.
 */
export function Markdown({ text, className = "" }: { text: string; className?: string }) {
  const blocks: React.ReactNode[] = [];
  const parts = text.split(/(```[\s\S]*?```)/g);
  parts.forEach((part, i) => {
    if (part.startsWith("```") && part.endsWith("```") && part.length >= 6) {
      const lines = part.slice(3, -3).replace(/^\n/, "").split("\n");
      if (lines[0].trim().toLowerCase() === "mermaid") {
        blocks.push(<Diagram key={`diagram-${i}`} source={lines.slice(1).join("\n")} />);
        return;
      }
      const lang = /^[a-z0-9+-]*$/i.test(lines[0]) && lines.length > 1 ? lines[0].trim().toLowerCase() : null;
      const code = (lang !== null ? lines.slice(1) : lines).join("\n").replace(/\n$/, "").split("\n");
      const python = lang === null || lang === "" || lang === "python" || lang === "py";
      const numbered = code.length > 1;
      blocks.push(
        <pre
          key={`code-${i}`}
          tabIndex={0} // wide code scrolls sideways: keyboard users must be able to reach it
          className="my-3 overflow-x-auto rounded-lg border border-line bg-surface-2 py-3.5 font-mono text-[13px] leading-relaxed text-fg"
        >
          <code className="grid min-w-max grid-cols-[auto_1fr]">
            {code.map((line, n) => (
              <React.Fragment key={n}>
                {/* line numbers: not selectable, not read out */}
                <span className={numbered ? "select-none pl-4 pr-4 text-right tabular-nums text-subtle" : "pl-4"} aria-hidden>
                  {numbered ? n + 1 : ""}
                </span>
                <span className="pr-4">
                  {python
                    ? highlightLine(line).map((t, k) =>
                        TOKEN_CLASS[t.kind] ? (
                          <span key={k} className={TOKEN_CLASS[t.kind]}>
                            {t.text}
                          </span>
                        ) : (
                          <React.Fragment key={k}>{t.text}</React.Fragment>
                        )
                      )
                    : line}
                  {"\n"}
                </span>
              </React.Fragment>
            ))}
          </code>
        </pre>
      );
      return;
    }
    let list: string[] = [];
    const flushList = (key: string) => {
      if (list.length) {
        blocks.push(
          <ul key={key} className="list-disc pl-5 space-y-1">
            {list.map((item, j) => (
              <li key={j}>{inline(item)}</li>
            ))}
          </ul>
        );
        list = [];
      }
    };
    part.split(/\n{2,}/).forEach((para, j) => {
      const lines = para.split("\n").filter((l) => l.trim() !== "");
      lines.forEach((line, k) => {
        const bullet = line.match(/^\s*[-*]\s+(.*)$/);
        if (bullet) {
          list.push(bullet[1]);
          return;
        }
        flushList(`list-${i}-${j}-${k}`);
        const heading = line.match(/^(#{1,4})\s+(.*)$/);
        if (heading) {
          blocks.push(
            <p key={`h-${i}-${j}-${k}`} className="pt-1 font-semibold text-fg">
              {inline(heading[2])}
            </p>
          );
        } else {
          blocks.push(<p key={`p-${i}-${j}-${k}`}>{inline(line)}</p>);
        }
      });
      flushList(`list-${i}-${j}-end`);
    });
  });
  return <div className={`space-y-2 ${className}`}>{blocks}</div>;
}

function inline(text: string): React.ReactNode[] {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).map((piece, i) => {
    if (piece.startsWith("`") && piece.endsWith("`") && piece.length > 2) {
      return (
        <code key={i} className="rounded-md border border-line bg-surface-2 px-1.5 py-0.5 font-mono text-[0.85em] text-fg">
          {piece.slice(1, -1)}
        </code>
      );
    }
    if (piece.startsWith("**") && piece.endsWith("**") && piece.length > 4) {
      return (
        <strong key={i} className="font-semibold text-fg">
          {piece.slice(2, -2)}
        </strong>
      );
    }
    return <React.Fragment key={i}>{piece}</React.Fragment>;
  });
}
