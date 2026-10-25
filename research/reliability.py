"""Cronbach's alpha per trait from a questionnaire-responses export (task R3; reported in R8).

    python research/reliability.py responses.csv [--questionnaire content/questionnaire.yaml]

responses.csv columns: user_id,item_id,value   (the admin export of `questionnaire_responses`)
Rule of thumb: alpha >= 0.7 acceptable; short 4-item scales often land around 0.6-0.7.
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from app.psychometrics.questionnaire import load_questionnaire
from app.psychometrics.reliability import alpha_per_trait


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("responses", type=Path)
    parser.add_argument(
        "--questionnaire",
        type=Path,
        default=Path(__file__).parents[1] / "content" / "questionnaire.yaml",
    )
    args = parser.parse_args()

    items = load_questionnaire(args.questionnaire)
    responses: dict[str, dict[str, int]] = defaultdict(dict)
    with args.responses.open() as f:
        for row in csv.DictReader(f):
            responses[row["user_id"]][row["item_id"]] = int(row["value"])

    print(f"{'trait':26} {'alpha':>6} {'n':>5}")
    for trait, (alpha, n) in alpha_per_trait(items, responses).items():
        print(f"{trait:26} {alpha:6.3f} {n:5d}")


if __name__ == "__main__":
    main()
