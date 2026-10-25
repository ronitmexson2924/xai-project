"""Review the item bank (S3): approve or reject draft items, and check the M5 bar.

    python -m app.graph.review                       # walk through every draft item
    python -m app.graph.review --cluster recursion   # only one cluster (or --concept ID)
    python -m app.graph.review --stats               # counts and the M5 readiness check
    python -m app.graph.review --set approved ID ...  # record decisions without prompting

Each item is shown with its answer and the misconception behind every wrong option, so the
reviewer can judge both the key and the diagnosis. Decisions are written straight into
content/items/*.yaml (only the item's `review_status:` line changes; comments and layout stay).
Then load them with `python -m app.graph.seed ../content`. Only `approved` items are served.
"""

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.graph.content import load_content
from app.graph.service import is_test_item

CONTENT = Path(__file__).resolve().parents[3] / "content"
STATUSES = ("draft", "approved", "rejected")
MIN_APPROVED = 180  # tasks/mit.md M5


@dataclass
class Readiness:
    counts: Counter
    approved_practice: int
    concepts_without_practice: list[str]
    concepts_without_microcheck: list[str]
    tests_ready: bool

    @property
    def ready(self) -> bool:
        return (
            self.approved_practice >= MIN_APPROVED
            and not self.concepts_without_practice
            and not self.concepts_without_microcheck
            and self.tests_ready
        )


def item_files(content: Path) -> list[Path]:
    return sorted((content / "items").glob("*.yaml"))


def load_items(content: Path) -> list[tuple[Path, dict]]:
    out = []
    for path in item_files(content):
        for item in (yaml.safe_load(path.read_text()) or {}).get("items", []):
            out.append((path, item))
    return out


def set_status(path: Path, item_id: str, status: str) -> None:
    """Rewrite the `review_status:` line of one item in place."""
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    lines = path.read_text().split("\n")
    start = next(
        (
            i
            for i, line in enumerate(lines)
            if re.fullmatch(rf"- id: ['\"]?{re.escape(item_id)}['\"]?", line)
        ),
        None,
    )
    if start is None:
        raise KeyError(f"{item_id} not in {path.name}")
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("- id:"):
            break
        if re.match(r"\s+review_status:", lines[i]):
            indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
            lines[i] = f"{indent}review_status: {status}"
            path.write_text("\n".join(lines))
            return
    raise KeyError(f"{item_id} has no review_status line")


def readiness(content: Path) -> Readiness:
    bundle = load_content(content)
    counts = Counter(i.review_status for i in bundle.items)
    approved = [i for i in bundle.items if i.review_status == "approved"]
    practice = [i for i in approved if not is_test_item(i.id)]
    concepts = [c.id for c in bundle.concepts]
    with_practice = {i.concept_id for i in practice if not i.is_microcheck}
    with_check = {i.concept_id for i in practice if i.is_microcheck}
    tests = Counter(i.id.split("-")[0] for i in approved if is_test_item(i.id))
    all_tests = Counter(i.id.split("-")[0] for i in bundle.items if is_test_item(i.id))
    return Readiness(
        counts=counts,
        approved_practice=len(practice),
        concepts_without_practice=[c for c in concepts if c not in with_practice],
        concepts_without_microcheck=[c for c in concepts if c not in with_check],
        tests_ready=bool(all_tests) and tests == all_tests,
    )


def print_stats(content: Path) -> None:
    r = readiness(content)
    print("items by status: " + ", ".join(f"{s} {r.counts.get(s, 0)}" for s in STATUSES))
    print(f"approved practice items: {r.approved_practice} (M5 needs {MIN_APPROVED})")
    print(f"concepts without an approved practice item: {len(r.concepts_without_practice)}")
    print(f"concepts without an approved micro-check: {len(r.concepts_without_microcheck)}")
    print(f"pre/post tests fully approved: {'yes' if r.tests_ready else 'no'}")
    print("READY for the pilot" if r.ready else "NOT READY: keep reviewing")


def show(item: dict, misconceptions: dict[str, str], concept_names: dict[str, str]) -> None:
    print("=" * 78)
    print(
        f"{item['id']}   [{concept_names.get(item['concept_id'], item['concept_id'])}]   "
        f"difficulty {item.get('difficulty', '?')}"
        f"{'   micro-check' if item.get('is_microcheck') else ''}"
    )
    print("-" * 78)
    print(item["stem"])
    print()
    tags = item.get("distractor_misconceptions") or {}
    for option in item.get("options", []):
        if option == item["answer"]:
            print(f"  ✓ {option}")
        else:
            mid = tags.get(option)
            why = f"  ← {misconceptions.get(mid, mid)}" if mid else "  (no misconception)"
            print(f"  ✗ {option}{why}")
    if not item.get("options"):
        print(f"  answer: {item['answer']}")


def interactive(content: Path, cluster: str | None, concept: str | None) -> int:
    bundle = load_content(content)
    misconceptions = {m.id: m.description for m in bundle.misconceptions}
    names = {c.id: c.name for c in bundle.concepts}
    queue = [
        (path, item)
        for path, item in load_items(content)
        if item.get("review_status", "draft") == "draft"
        and (cluster is None or path.stem == cluster)
        and (concept is None or item["concept_id"] == concept)
    ]
    print(f"{len(queue)} draft item(s) to review. a = approve, r = reject, s = skip, q = quit")
    decided = 0
    for path, item in queue:
        show(item, misconceptions, names)
        while True:
            choice = input("[a/r/s/q] > ").strip().lower()
            if choice in ("a", "r"):
                set_status(path, item["id"], "approved" if choice == "a" else "rejected")
                decided += 1
                break
            if choice == "s":
                break
            if choice == "q":
                print(f"{decided} decision(s) saved.")
                return 0
    print(f"Done: {decided} decision(s) saved. Load them with python -m app.graph.seed ../content")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review the item bank (S3)")
    parser.add_argument("--content", type=Path, default=CONTENT)
    parser.add_argument("--cluster", help="only this file, e.g. recursion")
    parser.add_argument("--concept", help="only this concept id")
    parser.add_argument("--stats", action="store_true", help="counts and M5 readiness")
    parser.add_argument("--set", nargs="+", metavar=("STATUS", "ID"), help="record decisions")
    args = parser.parse_args(argv)

    if args.stats:
        print_stats(args.content)
        return 0
    if args.set:
        status, ids = args.set[0], args.set[1:]
        where = {item["id"]: path for path, item in load_items(args.content)}
        missing = [i for i in ids if i not in where]
        if status not in STATUSES or missing or not ids:
            print(
                f"error: usage --set {{{','.join(STATUSES)}}} ID...; unknown: {missing}",
                file=sys.stderr,
            )
            return 1
        for item_id in ids:
            set_status(where[item_id], item_id, status)
        print(f"{len(ids)} item(s) set to {status}")
        return 0
    return interactive(args.content, args.cluster, args.concept)


if __name__ == "__main__":
    sys.exit(main())
