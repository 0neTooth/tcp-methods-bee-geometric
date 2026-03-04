#!/usr/bin/env python3
"""Run Major mutation analysis via defects4j mutation."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

from pipeline_utils import ROOT_DIR, ensure_dir, run_cmd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Major mutation for a Defects4J project/bug.")
    parser.add_argument("project", help="Defects4J project id (e.g., Jsoup)")
    parser.add_argument("bug_id", help="Bug identifier (e.g., 93)")
    return parser.parse_args()


def _apply_mml_filter(filter_file: Path, mml_file: Path) -> None:
    patterns = [line.strip() for line in filter_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not patterns:
        return
    lines = mml_file.read_text(encoding="utf-8").splitlines()
    def keep(line: str) -> bool:
        return not any(pat in line for pat in patterns)
    filtered = "\n".join(line for line in lines if keep(line)) + "\n"
    mml_file.write_text(filtered, encoding="utf-8")


def _copy_if_exists(src: Path, dst: Path) -> None:
    if src.is_file():
        ensure_dir(dst.parent)
        shutil.copy(src, dst)


def run_major(project: str, bug_id: str) -> Path:
    env = os.environ.copy()

    workdir = ROOT_DIR / "data" / "raw" / project / f"{bug_id}f"
    if not workdir.is_dir():
        raise FileNotFoundError(f"Fixed version directory not found: {workdir}")

    run_cmd(["defects4j", "compile"], cwd=workdir, env=env)

    output_dir = ensure_dir(ROOT_DIR / "data" / "raw" / project / bug_id / "mutants")

    exclude_file = ROOT_DIR / "config" / "major_excludes" / f"{project}-{bug_id}.txt"
    filter_file = ROOT_DIR / "config" / "mml_filters" / f"{project}-{bug_id}.txt"
    mml_file = workdir / ".mml" / "default.mml"
    if filter_file.is_file() and mml_file.is_file():
        _apply_mml_filter(filter_file, mml_file)

    mml_override = ROOT_DIR / "config" / "mml" / f"{project}-{bug_id}.mml"

    (output_dir / "context.txt").write_text(
        "\n".join(
            [
                f"project={project}",
                f"bug_id={bug_id}",
                f"workdir={workdir}",
                f"exclude_file={exclude_file if exclude_file.is_file() else ''}",
                f"filter_file={filter_file if filter_file.is_file() else ''}",
                f"mml_override={mml_override if mml_override.is_file() else ''}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    cmd = ["defects4j", "mutation", "-w", str(workdir)]
    if exclude_file.is_file():
        cmd.extend(["-e", str(exclude_file)])
    if mml_override.is_file():
        cmd.extend(["-m", str(mml_override)])
    env["JAVA_TOOL_OPTIONS"] = f"{env.get('JAVA_TOOL_OPTIONS', '')} -Duser.language=en -Duser.country=US".strip()

    run_cmd(cmd, cwd=workdir, env=env)

    _copy_if_exists(workdir / "mutants.log", output_dir / "mutants.log")
    _copy_if_exists(workdir / ".mutation.log", output_dir / "mutation.log")
    for name in ["covMap.csv", "testMap.csv", "kill.csv", "summary.csv"]:
        _copy_if_exists(workdir / name, output_dir / name)

    mutated_src = workdir / ".classes_mutated"
    mutated_dst = output_dir / "classes_mutated"
    if mutated_src.is_dir():
        if mutated_dst.exists():
            shutil.rmtree(mutated_dst)
        shutil.copytree(mutated_src, mutated_dst)

    print(f"[done] Major results saved to {output_dir}")
    return output_dir


def main() -> None:
    args = parse_args()
    run_major(args.project, args.bug_id)


if __name__ == "__main__":
    main()

