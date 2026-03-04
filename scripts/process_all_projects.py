#!/usr/bin/env python3
"""Run coverage + mutation for all projects listed in config/projects.csv."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from process_project import process_project


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT_DIR / "config" / "projects.csv"


def main(argv: list[str]) -> None:
    config_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_CONFIG
    if not config_path.is_file():
        raise SystemExit(f"Config file not found: {config_path}")

    with config_path.open(newline='', encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            project = row.get("project")
            bug_id = row.get("bug_id")
            if not project or not bug_id:
                continue
            print(f"=== Processing {project}-{bug_id} ===")
            process_project(project, bug_id)
            print(f"=== Done {project}-{bug_id} ===\n")


if __name__ == "__main__":
    main(sys.argv)
