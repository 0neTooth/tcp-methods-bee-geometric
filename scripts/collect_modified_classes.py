#!/usr/bin/env python3
"""Copy Defects4J modified class lists into the CIA folder."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from pipeline_utils import ROOT_DIR, ensure_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect modified class lists for a given bug.")
    parser.add_argument("project", help="Defects4J project id (e.g., Jsoup)")
    parser.add_argument("bug_id", help="Bug identifier (e.g., 93)")
    return parser.parse_args()


def collect_modified_classes(project: str, bug_id: str) -> Path:
    source_dir = ROOT_DIR / "defects4j" / "framework" / "projects" / project / "modified_classes"
    src_list = source_dir / f"{bug_id}.src"
    test_list = source_dir / f"{bug_id}.test"

    output_dir = ROOT_DIR / "data" / "raw" / project / bug_id / "cia"
    ensure_dir(output_dir)

    if src_list.is_file():
        shutil.copy(src_list, output_dir / "modified_classes.src")
    if test_list.is_file():
        shutil.copy(test_list, output_dir / "modified_classes.test")

    print(f"[done] Modified class lists saved to {output_dir}")
    return output_dir


def main() -> None:
    args = parse_args()
    collect_modified_classes(args.project, args.bug_id)


if __name__ == "__main__":
    main()

