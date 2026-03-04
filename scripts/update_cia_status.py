#!/usr/bin/env python3
"""
Формирует сводку наличия артефактов CIA для всех проектов.
"""

from __future__ import annotations

import csv
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    config_path = root / "config" / "projects.csv"
    output_path = root / "data" / "cia_status.csv"

    with config_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    statuses = []
    for row in rows:
        project = row["project"]
        bug_id = row["bug_id"]
        base_dir = root / "data" / "raw" / project / bug_id / "cia"
        statuses.append(
            {
                "project": project,
                "bug_id": bug_id,
                "roc": "yes" if (base_dir / "roc.csv").is_file() else "no",
                "forward_slicing": "yes" if (base_dir / "forward_slicing.csv").is_file() else "no",
                "impact_probabilities": "yes" if (base_dir / "impact_probabilities.csv").is_file() else "no",
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["project", "bug_id", "roc", "forward_slicing", "impact_probabilities"],
        )
        writer.writeheader()
        writer.writerows(statuses)

    print(f"[done] Статус CIA сохранён в {output_path}")


if __name__ == "__main__":
    main()
