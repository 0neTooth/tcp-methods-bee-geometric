#!/usr/bin/env python3
"""Generate static call graph (callgraph.txt) using java-callgraph."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
from pathlib import Path

from pipeline_utils import ROOT_DIR, ensure_dir, defects4j_export, run_cmd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate callgraph.txt for a Defects4J project/bug.")
    parser.add_argument("project", help="Defects4J project id (e.g., Jsoup)")
    parser.add_argument("bug_id", help="Bug identifier (e.g., 93)")
    parser.add_argument(
        "--callgraph-jar",
        default=None,
        help="Path to javacg-*-static.jar (default: tools/java-callgraph/target/javacg-0.1-SNAPSHOT-static.jar)",
    )
    return parser.parse_args()


def generate_callgraph(project: str, bug_id: str, callgraph_jar: Path | None = None) -> Path:
    jar_path = callgraph_jar or ROOT_DIR / "tools" / "java-callgraph" / "target" / "javacg-0.1-SNAPSHOT-static.jar"
    jar_path = jar_path.resolve()
    if not jar_path.is_file():
        raise FileNotFoundError(f"Call graph jar not found: {jar_path}")

    workdir = ROOT_DIR / "data" / "raw" / project / f"{bug_id}f"
    if not workdir.is_dir():
        raise FileNotFoundError(f"Fixed version directory not found: {workdir}")

    env = os.environ.copy()
    run_cmd(["defects4j", "compile"], cwd=workdir, env=env)

    classes_rel = defects4j_export(workdir, "dir.bin.classes", env=env)
    classes_dir = (workdir / classes_rel).resolve()
    if not classes_dir.is_dir():
        raise FileNotFoundError(f"Compiled classes directory not found: {classes_dir}")

    cia_dir = ensure_dir(ROOT_DIR / "data" / "raw" / project / bug_id / "cia")
    jar_output = cia_dir / "classes.jar"
    callgraph_output = cia_dir / "callgraph.txt"

    run_cmd(["jar", "cf", str(jar_output), "-C", str(classes_dir), "."], cwd=workdir, env=env)

    cmd = ["java", "-jar", str(jar_path), str(jar_output)]
    printable = " ".join(shlex.quote(part) for part in cmd)
    print(f"[run] {printable} > {callgraph_output}")
    output = subprocess.check_output(cmd, cwd=str(ROOT_DIR), env=env)
    callgraph_output.write_bytes(output)
    print(f"[done] Call graph saved to {callgraph_output}")
    return callgraph_output


def main() -> None:
    args = parse_args()
    generate_callgraph(args.project, args.bug_id, Path(args.callgraph_jar).resolve() if args.callgraph_jar else None)


if __name__ == "__main__":
    main()
