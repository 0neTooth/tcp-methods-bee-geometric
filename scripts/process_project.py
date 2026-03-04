#!/usr/bin/env python3
"""Run coverage (GZoltar) and mutation (Major) for a single project/bug."""

from __future__ import annotations

import argparse

from run_gzoltar import run_gzoltar
from run_major import run_major


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run coverage + mutation pipeline for one Defects4J bug.")
    parser.add_argument("project", help="Defects4J project id (e.g., Jsoup)")
    parser.add_argument("bug_id", help="Bug identifier (e.g., 93)")
    return parser.parse_args()


def process_project(project: str, bug_id: str) -> None:
    run_gzoltar(project, bug_id)
    run_major(project, bug_id)
    print(f"[done] Pipeline completed for {project}-{bug_id}")


def main() -> None:
    args = parse_args()
    process_project(args.project, args.bug_id)


if __name__ == "__main__":
    main()

