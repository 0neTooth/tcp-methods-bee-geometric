#!/usr/bin/env python3
"""Checkout buggy and fixed Defects4J revisions."""

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline_utils import ROOT_DIR, run_cmd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Checkout Defects4J buggy/fixed revisions.")
    parser.add_argument("project", help="Defects4J project id (e.g., Jsoup)")
    parser.add_argument("bug_id", help="Bug identifier (e.g., 93)")
    parser.add_argument(
        "--target-dir",
        default=None,
        help="Base directory to place checkouts (default: data/raw/<project>)",
    )
    return parser.parse_args()


def checkout_versions(project: str, bug_id: str, target_dir: Path | None = None) -> None:
    base = target_dir or ROOT_DIR / "data" / "raw" / project
    base.mkdir(parents=True, exist_ok=True)

    buggy_dir = base / f"{bug_id}b"
    fixed_dir = base / f"{bug_id}f"

    if not buggy_dir.is_dir():
        run_cmd(["defects4j", "checkout", "-p", project, "-v", f"{bug_id}b", "-w", buggy_dir])
    else:
        print(f"[skip] buggy version already exists: {buggy_dir}")

    if not fixed_dir.is_dir():
        run_cmd(["defects4j", "checkout", "-p", project, "-v", f"{bug_id}f", "-w", fixed_dir])
    else:
        print(f"[skip] fixed version already exists: {fixed_dir}")


def main() -> None:
    args = parse_args()
    target = Path(args.target_dir).resolve() if args.target_dir else None
    checkout_versions(args.project, args.bug_id, target)


if __name__ == "__main__":
    main()

