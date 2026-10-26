/**
 * A tiny, line-by-line Python highlighter for the code in questions and explanations: keywords,
 * strings, numbers, comments. Hand-written (no highlighting library) and returns plain tokens,
 * which Markdown.tsx renders as React text nodes, so nothing can inject markup.
 */
export type TokenKind = "keyword" | "string" | "number" | "comment" | "plain";
export interface Token {
  kind: TokenKind;
  text: string;
}

const KEYWORDS = new Set(
  (
    "and as assert async await break class continue def del elif else except finally for from global if import in is " +
    "lambda nonlocal not or pass raise return try while with yield True False None"
  ).split(" ")
);

const PATTERN = /(#.*$)|([rbfu]{0,2}(?:"(?:[^"\\]|\\.)*"?|'(?:[^'\\]|\\.)*'?))|(\b\d+(?:\.\d+)?\b)|([A-Za-z_]\w*)/gi;

export function highlightLine(line: string): Token[] {
  const tokens: Token[] = [];
  let last = 0;
  const push = (kind: TokenKind, text: string) => {
    if (!text) return;
    const prev = tokens.at(-1);
    if (prev && prev.kind === kind) prev.text += text;
    else tokens.push({ kind, text });
  };
  for (const m of line.matchAll(PATTERN)) {
    push("plain", line.slice(last, m.index));
    const [text, comment, string, number, word] = m;
    if (comment) push("comment", text);
    else if (string && /["']/.test(string)) push("string", text);
    else if (number) push("number", text);
    else push(word && KEYWORDS.has(word) ? "keyword" : "plain", text);
    last = m.index + text.length;
  }
  push("plain", line.slice(last));
  return tokens;
}
