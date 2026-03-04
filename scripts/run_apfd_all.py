#!/usr/bin/env python3
"""Запуск APFD для всех проектов из config/projects.csv."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from compute_apfd import (  # type: ignore
    compute_apfd,
    load_cov_map,
    load_killed_mutants,
    load_order,
    load_test_map,
)


def main() -> None:
    projects_path = ROOT / "config" / "projects.csv"
    results = []

    with projects_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            project = row["project"]
            bug = row["bug_id"]

            test_map_path = ROOT / "data" / "raw" / project / bug / "mutants" / "testMap.csv"
            kill_path = ROOT / "data" / "raw" / project / bug / "mutants" / "kill.csv"
            cov_map_path = ROOT / "data" / "raw" / project / bug / "mutants" / "covMap.csv"

            if not (test_map_path.is_file() and kill_path.is_file() and cov_map_path.is_file()):
                continue

            test_map = load_test_map(test_map_path)
            killed = load_killed_mutants(kill_path)
            cov_map = load_cov_map(cov_map_path)

            modes = [
                ("lom", "lom", "lom_scores.csv"),
                ("dis-lom", "dis_lom", "dis_lom_scores.csv"),
                ("cov-clustering", "cov_clustering", "cov_clustering_scores.csv"),
            ]
            for mode, subdir, filename in modes:
                order_path = ROOT / "data" / "results" / subdir / project / bug / filename
                if not order_path.is_file():
                    continue

                order = load_order(order_path, test_map)
                apfd = compute_apfd(order, test_map, killed, cov_map)
                results.append({
                    "project": project,
                    "bug": bug,
                    "mode": mode,
                    "apfd": apfd,
                })

    output = ROOT / "docs" / "lom_reports" / "apfd_results.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["project", "bug", "mode", "apfd"])
        writer.writeheader()
        for row in results:
            writer.writerow({
                "project": row["project"],
                "bug": row["bug"],
                "mode": row["mode"],
                "apfd": f"{row['apfd']:.4f}",
            })
    print(f"[done] APFD results saved to {output}")


if __name__ == "__main__":
    main()
