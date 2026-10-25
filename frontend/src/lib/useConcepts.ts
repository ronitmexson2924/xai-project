"use client";

import { useEffect, useMemo, useState } from "react";
import { api, Concept, GraphResponse } from "./api";

let cache: Promise<GraphResponse> | null = null;

/** The concept graph, fetched once per page load and shared by every component. */
export function useGraph(): GraphResponse | null {
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  useEffect(() => {
    let alive = true;
    cache ??= api.graph.get();
    cache.then((g) => alive && setGraph(g)).catch(() => {
      cache = null; // retry on the next mount
    });
    return () => {
      alive = false;
    };
  }, []);
  return graph;
}

export function useConcepts(): Record<string, Concept> {
  const graph = useGraph();
  return useMemo(
    () => (graph ? Object.fromEntries(graph.concepts.map((c) => [c.id, c])) : {}),
    [graph]
  );
}
