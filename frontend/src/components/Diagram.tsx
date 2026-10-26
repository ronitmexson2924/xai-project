import React from "react";

/**
 * Renders the small Mermaid flowcharts used on concept cards (`flowchart TD`, `A["label"] --> B`,
 * `A --> B & C`) as a top-down tree, without shipping the Mermaid library. Anything it does not
 * understand falls back to showing the source, so a diagram is never silently lost.
 */

interface Graph {
  labels: Map<string, string>;
  children: Map<string, string[]>;
  roots: string[];
}

const NODE = /^([A-Za-z_][\w-]*)\s*(?:\[\s*"([^"]*)"\s*\]|\[([^\]"]*)\]|\(\s*"([^"]*)"\s*\)|\(([^)"]*)\))?$/;
const MAX_NODES = 40;

export function parseFlowchart(source: string): Graph | null {
  const lines = source
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith("%%"));
  if (!lines.length || !/^(flowchart|graph)\s+(TD|TB)\s*;?$/i.test(lines[0])) return null;

  const labels = new Map<string, string>();
  const children = new Map<string, string[]>();
  const hasParent = new Set<string>();
  const order: string[] = [];

  const node = (token: string): string | null => {
    const m = token.trim().match(NODE);
    if (!m) return null;
    const [, id, ...rest] = m;
    const label = rest.find((r) => r !== undefined);
    if (!labels.has(id)) order.push(id);
    if (label !== undefined || !labels.has(id)) labels.set(id, (label ?? labels.get(id) ?? id).trim());
    return id;
  };

  for (const line of lines.slice(1)) {
    const segments = line.replace(/;$/, "").split(/\s*-->\s*(?:\|[^|]*\|\s*)?/);
    let previous: string[] = [];
    for (const segment of segments) {
      const ids = segment.split(/\s*&\s*/).map(node);
      if (ids.some((id) => id === null)) return null;
      for (const parent of previous) {
        for (const child of ids as string[]) {
          const list = children.get(parent) ?? [];
          if (!list.includes(child)) list.push(child);
          children.set(parent, list);
          hasParent.add(child);
        }
      }
      previous = ids as string[];
    }
  }
  if (!labels.size || labels.size > MAX_NODES) return null;
  const roots = order.filter((id) => !hasParent.has(id));
  return roots.length ? { labels, children, roots } : null;
}

function describe(graph: Graph): string {
  const steps: string[] = [];
  for (const [parent, kids] of graph.children) {
    steps.push(`${graph.labels.get(parent)} leads to ${kids.map((k) => graph.labels.get(k)).join(" and ")}`);
  }
  return `Diagram: ${steps.join("; ")}.`;
}

function Subtree({ id, graph, path }: { id: string; graph: Graph; path: string[] }) {
  // a node already on this path would loop forever: stop there
  const kids = path.includes(id) ? [] : (graph.children.get(id) ?? []);
  return (
    <li>
      <span className="diagram-node">{graph.labels.get(id)}</span>
      {kids.length > 0 && (
        <ul>
          {kids.map((k, i) => (
            <Subtree key={`${k}-${i}`} id={k} graph={graph} path={[...path, id]} />
          ))}
        </ul>
      )}
    </li>
  );
}

export function Diagram({ source }: { source: string }) {
  const graph = parseFlowchart(source);
  if (!graph) {
    return (
      <figure className="my-3">
        <figcaption className="mb-1 text-xs font-medium text-subtle">Diagram</figcaption>
        <pre tabIndex={0} className="overflow-x-auto rounded-xl border border-line bg-surface-2 p-4 font-mono text-[13px] text-fg">
          <code>{source}</code>
        </pre>
      </figure>
    );
  }
  return (
    <figure tabIndex={0} className="my-4 overflow-x-auto rounded-xl border border-line bg-surface-2/50 p-4" data-testid="diagram">
      <div role="img" aria-label={describe(graph)} className="diagram-tree mx-auto w-max">
        <ul>
          {graph.roots.map((r) => (
            <Subtree key={r} id={r} graph={graph} path={[]} />
          ))}
        </ul>
      </div>
    </figure>
  );
}
