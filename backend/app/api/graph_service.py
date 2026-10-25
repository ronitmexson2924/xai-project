"""Curriculum Graph Service implementing GraphService Protocol.

Owner: Mit.
Serves full concept DAG, prerequisite edges, and loaded item bank.
"""

from collections import defaultdict
from pathlib import Path

import yaml

from app.contracts.fakes import _ITEMS as FAKE_ITEMS
from app.contracts.graph import Concept, ConceptEdge, Item
from app.items.curriculum import get_all_concepts

PREREQUISITES_MAP: dict[str, list[str]] = {
    # basics
    "nested-loops": ["loops"],
    "conditional-invariants": ["loops", "variables-and-scope"],
    "space-complexity-intro": ["time-complexity-intro"],
    # arrays-strings
    "array-indexing": ["loops", "variables-and-scope"],
    "two-pointers-technique": ["array-indexing"],
    "sliding-window": ["two-pointers-technique"],
    "prefix-sums": ["array-indexing"],
    "string-immutability": ["array-indexing"],
    "in-place-array-modification": ["two-pointers-technique"],
    # linked-structures
    "singly-linked-list-node": ["variables-and-scope"],
    "linked-list-traversal": ["singly-linked-list-node", "loops"],
    "linked-list-insertion": ["linked-list-traversal"],
    "linked-list-deletion": ["linked-list-traversal"],
    "fast-slow-pointers": ["linked-list-traversal", "two-pointers-technique"],
    "doubly-linked-list": ["linked-list-traversal"],
    # recursion
    "recursion-base-case": ["conditional-invariants"],
    "recursive-call-stack": ["recursion-base-case"],
    "divide-and-conquer": ["recursive-call-stack"],
    "tree-recursion": ["recursive-call-stack"],
    "backtracking-basics": ["tree-recursion"],
    "tail-recursion": ["recursive-call-stack"],
    # sorting-searching
    "linear-search": ["array-indexing", "loops"],
    "binary-search-bounds": ["linear-search", "two-pointers-technique"],
    "binary-search-midpoint": ["binary-search-bounds"],
    "bubble-sort-invariant": ["nested-loops", "in-place-array-modification"],
    "merge-sort-merge-step": ["divide-and-conquer", "two-pointers-technique"],
    "quick-sort-partition": ["divide-and-conquer", "two-pointers-technique"],
    # trees
    "binary-tree-traversal-preorder": ["tree-recursion", "singly-linked-list-node"],
    "binary-tree-traversal-inorder": ["binary-tree-traversal-preorder"],
    "binary-tree-traversal-postorder": ["binary-tree-traversal-preorder"],
    "bst-search-property": ["binary-tree-traversal-inorder", "binary-search-bounds"],
    "bst-insertion": ["bst-search-property"],
    "tree-height-depth": ["binary-tree-traversal-preorder"],
    # graphs
    "graph-adjacency-list": ["singly-linked-list-node", "array-indexing"],
    "breadth-first-search-queue": ["graph-adjacency-list"],
    "depth-first-search-visited": ["graph-adjacency-list", "recursive-call-stack"],
    "topological-sort": ["depth-first-search-visited"],
    "dijkstra-shortest-path": ["breadth-first-search-queue", "time-complexity-intro"],
    "cycle-detection-directed": ["depth-first-search-visited", "topological-sort"],
    # dp
    "overlapping-subproblems": ["recursive-call-stack"],
    "optimal-substructure": ["overlapping-subproblems"],
    "memoization-top-down": ["overlapping-subproblems", "tree-recursion"],
    "tabulation-bottom-up": ["memoization-top-down", "nested-loops"],
    "dp-state-transition-1d": ["tabulation-bottom-up", "prefix-sums"],
    "dp-state-transition-2d": ["dp-state-transition-1d"],
}


class CurriculumGraphService:
    """Read-only access to concepts, edges, and item bank."""

    def __init__(self) -> None:
        self._concepts = get_all_concepts()
        self._concepts_by_id = {c.id: c for c in self._concepts}
        self._edges: list[ConceptEdge] = []
        self._prereqs_by_dst: dict[str, list[str]] = defaultdict(list)
        self._items: dict[str, Item] = {}
        self._items_by_concept: dict[str, list[Item]] = defaultdict(list)

        self._build_edges()
        self._load_items()

    def _build_edges(self) -> None:
        root_dir = Path(__file__).resolve().parents[3]
        concepts_file = root_dir / "content" / "concepts.yaml"
        loaded_from_yaml = False
        if concepts_file.exists():
            try:
                with open(concepts_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                for c in data.get("concepts", []):
                    dst = c.get("id")
                    if dst in self._concepts_by_id:
                        for src in c.get("prerequisites", []):
                            if src in self._concepts_by_id:
                                self._edges.append(ConceptEdge(src=src, dst=dst, weight=0.8))
                                self._prereqs_by_dst[dst].append(src)
                loaded_from_yaml = True
            except Exception:
                pass

        if not loaded_from_yaml:
            for dst, srcs in PREREQUISITES_MAP.items():
                if dst in self._concepts_by_id:
                    for src in srcs:
                        if src in self._concepts_by_id:
                            self._edges.append(ConceptEdge(src=src, dst=dst, weight=0.8))
                            self._prereqs_by_dst[dst].append(src)

    def _load_items(self) -> None:
        # 1. First include any fake items as fallbacks
        for item in FAKE_ITEMS:
            self._items[item.id] = item
            self._items_by_concept[item.concept_id].append(item)

        # 2. Load YAML files from content/items/
        items_dir = Path(__file__).resolve().parents[3] / "content" / "items"
        if items_dir.exists():
            for yaml_file in items_dir.glob("*.yaml"):
                try:
                    with open(yaml_file, encoding="utf-8") as f:
                        loaded = yaml.safe_load(f) or []
                    items_list = loaded.get("items", []) if isinstance(loaded, dict) else loaded
                    for raw in items_list:
                        it = Item(**raw)
                        self._items[it.id] = it
                        # Avoid duplicates
                        existing_ids = {x.id for x in self._items_by_concept[it.concept_id]}
                        if it.id not in existing_ids:
                            self._items_by_concept[it.concept_id].append(it)
                except Exception:
                    pass

    def get_graph(self) -> tuple[list[Concept], list[ConceptEdge]]:
        return list(self._concepts), list(self._edges)

    def get_concept(self, concept_id: str) -> Concept:
        if concept_id in self._concepts_by_id:
            return self._concepts_by_id[concept_id]
        raise StopIteration(f"Concept '{concept_id}' not found")

    def prerequisites(self, concept_id: str) -> list[str]:
        return list(self._prereqs_by_dst.get(concept_id, []))

    def get_item(self, item_id: str) -> Item:
        if item_id in self._items:
            return self._items[item_id]
        raise StopIteration(f"Item '{item_id}' not found")

    def items_for_concept(self, concept_id: str, microcheck: bool = False) -> list[Item]:
        items = self._items_by_concept.get(concept_id, [])
        return [i for i in items if i.is_microcheck == microcheck]
