"""Review and approval CLI for items in content/items/*.yaml.

Owner: Mit.
Review flow supporting YAML inspection and status promotion.
"""

import argparse
from pathlib import Path

import yaml

from app.items.generate import get_items_dir


def load_cluster_file(file_path: Path) -> dict:
    with open(file_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"items": []}


def save_cluster_file(file_path: Path, data: dict) -> None:
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False, allow_unicode=True)


def review_items(approve_all: bool = False, target_status: str | None = None) -> dict[str, int]:
    """Scan all items and report / update status counts."""
    items_dir = get_items_dir()
    counts = {"approved": 0, "draft": 0, "rejected": 0, "total": 0}

    yaml_files = list(items_dir.glob("*.yaml"))
    for yf in sorted(yaml_files):
        data = load_cluster_file(yf)
        items = data.get("items", [])
        modified = False

        for it in items:
            status = it.get("review_status", "draft")
            if approve_all and status != "approved":
                it["review_status"] = "approved"
                status = "approved"
                modified = True
            elif target_status and it.get("review_status") != target_status:
                it["review_status"] = target_status
                status = target_status
                modified = True

            counts[status] = counts.get(status, 0) + 1
            counts["total"] += 1

        if modified:
            save_cluster_file(yf, data)

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Review and approve DSA items")
    parser.add_argument("--approve-all", action="store_true", help="Promote all items to approved")
    parser.add_argument(
        "--status", choices=["approved", "draft", "rejected"], help="Filter or update status"
    )
    args = parser.parse_args()

    counts = review_items(approve_all=args.approve_all)
    print("=== Item Bank Review Summary ===")
    print(f"Total items:    {counts['total']}")
    print(f"Approved items: {counts['approved']}")
    print(f"Draft items:    {counts['draft']}")
    print(f"Rejected items: {counts['rejected']}")


if __name__ == "__main__":
    main()
