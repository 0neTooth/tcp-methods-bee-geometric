#!/usr/bin/env python3
"""Сводка совпадения методов покрытия с CIA-вероятностями."""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Dict


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lom-study"))

from tcp.data_loader import read_coverage_matrix, read_impact_probabilities  # type: ignore
from tcp.lom_algorithms import coverage_to_impact_mapping  # type: ignore


def analyze_project(project: str, bug: str) -> Dict[str, int]:
    base = ROOT / "data" / "raw" / project / bug
    coverage_path = base / "coverage" / "matrix.csv"
    impact_path = base / "cia" / "impact_probabilities.csv"
    if not coverage_path.is_file() or not impact_path.is_file():
        return {
            "project": project,
            "bug": bug,
            "coverage_methods": 0,
            "impact_entries": 0,
            "matched": 0,
        }

    coverage = read_coverage_matrix(coverage_path)
    impact = read_impact_probabilities(impact_path)
    mapping = coverage_to_impact_mapping(coverage, impact)
    return {
        "project": project,
        "bug": bug,
        "coverage_methods": len(coverage.methods),
        "impact_entries": len(impact.methods),
        "matched": len(mapping),
    }


def main() -> None:
    results = []
    with (ROOT / "config" / "projects.csv").open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            results.append(analyze_project(row["project"], row["bug_id"]))

    output = ROOT / "docs" / "lom_reports" / "alignment_summary.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["project", "bug", "coverage_methods", "impact_entries", "matched"],
        )
        writer.writeheader()
        writer.writerows(results)
    print(f"[done] Alignment summary -> {output}")


if __name__ == "__main__":
    main()
